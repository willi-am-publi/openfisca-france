# -*- coding: utf-8 -*-

from openfisca_france.model.base import *  # noqa analysis:ignore
import functools

DEFAULT_ROUND_BASE_DECIMALS = 2


def memoize(func):
    cache = func.cache = {}

    @functools.wraps(func)
    def memoized_func(*args, **kwargs):
        key = str(args) + str(kwargs)
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]
    return memoized_func


@profile
def apply_bareme_for_relevant_type_sal(
        bareme_by_type_sal_name,
        bareme_name,
        categorie_salarie,
        base,
        plafond_securite_sociale,
        round_base_decimals=DEFAULT_ROUND_BASE_DECIMALS):
    assert bareme_by_type_sal_name is not None
    assert bareme_name is not None
    assert categorie_salarie is not None
    assert base is not None
    assert plafond_securite_sociale is not None
    cotisations = gen_cotisations(list_types_sal(categorie_salarie),
                                  bareme_by_type_sal_name,
                                  bareme_name,
                                  base,
                                  plafond_securite_sociale,
                                  round_base_decimals)

    return - sum(cotisations)


@profile
def apply_bareme(individu,
                 period,
                 parameters,
                 cotisation_type=None,
                 bareme_name=None,
                 variable_name=None):
    cotisation_mode_recouvrement = individu('cotisation_sociale_mode_recouvrement', period)
    TypesCotisationSocialeModeRecouvrement = cotisation_mode_recouvrement.possible_values
    cotisation = (
        # anticipé (mensuel avec recouvrement en fin d'année)
        cotisation_mode_recouvrement == TypesCotisationSocialeModeRecouvrement.mensuel) * (
            compute_cotisation_anticipee(
                individu,
                period,
                parameters,
                cotisation_type = cotisation_type,
                bareme_name = bareme_name,
                variable_name = variable_name,
                )
            ) + (
        # en fin d'année
        cotisation_mode_recouvrement == TypesCotisationSocialeModeRecouvrement.annuel) * (
            compute_cotisation_annuelle(
                individu,
                period,
                parameters,
                cotisation_type = cotisation_type,
                bareme_name = bareme_name,
                )
            ) + (
        # mensuel stricte
        cotisation_mode_recouvrement == TypesCotisationSocialeModeRecouvrement.mensuel_strict) * (
            compute_cotisation(
                individu,
                period,
                parameters,
                cotisation_type = cotisation_type,
                bareme_name = bareme_name,
                )
            )
    return cotisation


@profile
def compute_cotisation(individu,
                       period,
                       parameters,
                       cotisation_type=None,
                       bareme_name=None):
    assert cotisation_type is not None
    law = parameters(period)
    if cotisation_type == "employeur":
        bareme_by_type_sal_name = law.cotsoc.cotisations_employeur
    elif cotisation_type == "salarie":
        bareme_by_type_sal_name = law.cotsoc.cotisations_salarie
    assert bareme_name is not None

    assiette_cotisations_sociales = individu('assiette_cotisations_sociales',
                                             period,
                                             options=[ADD])

    plafond_securite_sociale = individu('plafond_securite_sociale',
                                        period,
                                        options=[ADD])

    categorie_salarie = individu('categorie_salarie', period.first_month)

    cotisation = apply_bareme_for_relevant_type_sal(bareme_by_type_sal_name=bareme_by_type_sal_name,
                                                    bareme_name=bareme_name,
                                                    base=assiette_cotisations_sociales,
                                                    plafond_securite_sociale=plafond_securite_sociale,
                                                    categorie_salarie=categorie_salarie)

    return cotisation


@profile
def compute_cotisation_annuelle(individu,
                                period,
                                parameters,
                                cotisation_type=None,
                                bareme_name=None):

    if period.start.month < 12:
        return 0

    return compute_cotisation(individu,
                              period.this_year,
                              parameters,
                              cotisation_type=cotisation_type,
                              bareme_name=bareme_name)


@profile
def compute_cotisation_anticipee(individu,
                                 period,
                                 parameters,
                                 cotisation_type=None,
                                 bareme_name=None,
                                 variable_name=None):

    if period.start.month < 12:
        return compute_cotisation(individu,
                                  period.first_month,
                                  parameters,
                                  cotisation_type=cotisation_type,
                                  bareme_name=bareme_name)

    cumul = individu(variable_name,
                     period.start.offset('first-of', 'month').offset(-11, 'month').period('month', 11),
                     max_nb_cycles=1,
                     options=[ADD])
    # December variable_name depends on variable_name in the past 11 months
    # We need to explicitely allow this recursion.

    return compute_cotisation(individu,
                              period.this_year,
                              parameters,
                              cotisation_type=cotisation_type,
                              bareme_name=bareme_name) - cumul


@memoize
@profile
def list_types_sal(categorie_salarie):
    return [(type_sal, type_sal.name, type_sal == categorie_salarie)
            for type_sal
            in categorie_salarie.possible_values]


@profile
def gen_cotisations(types_sal,
                    bareme_by_type_sal_name,
                    bareme_name,
                    base,
                    plafond_securite_sociale,
                    round_base_decimals):
    for (type_sal, type_sal_name, is_type_sal) in types_sal:
        try:
            bareme = bareme_by_type_sal_name[type_sal_name][bareme_name]
        except KeyError:
            continue  # to deal with public_titulaire_militaire
        yield bareme.calc(base * is_type_sal,
                          factor=plafond_securite_sociale,
                          round_base_decimals=round_base_decimals)
