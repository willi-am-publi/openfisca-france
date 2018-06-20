# -*- coding: utf-8 -*-

"""
This files tests the performance of the test runner of openfisca-run-test on a subset of YAML tests.
It is placed in openfisca-france because it is the largest set we currently have.
"""
import argparse
import logging
import sys
import os
import collections
import copy
import glob
import unittest

import nose
import numpy as np
import yaml

from openfisca_core import conv, periods, scenarios
from openfisca_core.tools import assert_near
from openfisca_core.commons import unicode_type, to_unicode

from openfisca_core.scripts import add_tax_benefit_system_arguments, build_tax_benefit_system

log = logging.getLogger(__name__)


def _config_yaml(yaml):

    class folded_unicode(unicode_type):
        pass

    class literal_unicode(unicode_type):
        pass

    def dict_constructor(loader, node):
        return collections.OrderedDict(loader.construct_pairs(node))

    yaml.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, dict_constructor)

    yaml.add_representer(collections.OrderedDict, lambda dumper, data: dumper.represent_dict(
        (copy.deepcopy(key), value)
        for key, value in data.items()
        ))
    yaml.add_representer(dict, lambda dumper, data: dumper.represent_dict(
        (copy.deepcopy(key), value)
        for key, value in data.items()
        ))
    yaml.add_representer(folded_unicode, lambda dumper, data: dumper.represent_scalar(u'tag:yaml.org,2002:str',
        data, style='>'))
    yaml.add_representer(literal_unicode, lambda dumper, data: dumper.represent_scalar(u'tag:yaml.org,2002:str',
        data, style='|'))
    yaml.add_representer(np.ndarray, lambda dumper, data: dumper.represent_list(data.tolist()))
    yaml.add_representer(periods.Instant, lambda dumper, data: dumper.represent_scalar(u'tag:yaml.org,2002:str', str(data)))
    yaml.add_representer(periods.Period, lambda dumper, data: dumper.represent_scalar(u'tag:yaml.org,2002:str', str(data)))
    yaml.add_representer(tuple, lambda dumper, data: dumper.represent_list(data))
    yaml.add_representer(unicode_type, lambda dumper, data: dumper.represent_scalar(u'tag:yaml.org,2002:str', data))

    return yaml


_config_yaml(yaml)


# Exposed methods

def generate_tests(tax_benefit_system, paths, options = {}):
    """
    Generates a lazy iterator of all the YAML tests contained in a file or a directory.

    :parameters: Same as :meth:`run_tests`

    :return: a generator of YAML tests

    """

    if isinstance(paths, str):
        paths = [paths]

    for path in paths:
        if os.path.isdir(path):
            for test in list(_generate_tests_from_directory(tax_benefit_system, path, options)):
                yield test
        else:
            for test in list(_generate_tests_from_file(tax_benefit_system, path, options)):
                yield test


def run_tests(tax_benefit_system, paths, options = {}):
    """
    Runs all the YAML tests contained in a file or a directory.

    If `path` is a directory, subdirectories will be recursively explored.

    :param TaxBenefitSystem tax_benefit_system: the tax-benefit system to use to run the tests
    :param (str/list) paths: A path, or a list of paths, towards the files or directories containing the tests to run. If a path is a directory, subdirectories will be recursively explored.
    :param dict options: See more details below.

    :raises AssertionError: if a test does not pass

    :return: the number of sucessful tests excecuted

    **Testing options**:

    +-------------------------------+-----------+-------------------------------------------+
    | Key                           | Type      | Role                                      |
    +===============================+===========+===========================================+
    | verbose                       | ``bool``  |                                           |
    +-------------------------------+-----------+ See :any:`openfisca-run-test` options doc +
    | name_filter                   | ``str``   |                                           |
    +-------------------------------+-----------+-------------------------------------------+

    """
    argv = sys.argv[:1]  # Nose crashes if it gets any unexpected argument.
    if options.get('verbose'):
        argv.append('--nocapture')  # Do not capture output when verbose mode is activated
    return nose.run(
        # The suite argument must be a lambda for nose to run the tests lazily
        suite = lambda: generate_tests(tax_benefit_system, paths, options),
        argv = argv,
        )


# Internal methods

def _generate_tests_from_file(tax_benefit_system, path_to_file, options):
    filename = os.path.splitext(os.path.basename(path_to_file))[0]
    name_filter = options.get('name_filter')
    if isinstance(name_filter, str):
        name_filter = to_unicode(name_filter)
    verbose = options.get('verbose')
    only_variables = options.get('only_variables')
    ignore_variables = options.get('ignore_variables')

    tests = []

    for test_index, (path_to_file, name, period_str, test) in enumerate(_parse_test_file(tax_benefit_system, path_to_file), 1):
        if name_filter is not None and name_filter not in filename \
                and name_filter not in (test.get('name', u'')) \
                and name_filter not in (test.get('keywords', [])):
            continue

        keywords = test.get('keywords', [])
        title = "{}: {}{} - {}".format(
            os.path.basename(path_to_file),
            u'[{}] '.format(u', '.join(keywords)).encode('utf-8') if keywords else '',
            name.encode('utf-8'),
            period_str,
            )

        scenario = test['scenario']
        scenario.suggest()
        simulation = scenario.new_simulation(trace = verbose)


        def check():
            try:
                _run_test(period_str, test, simulation, verbose, only_variables, ignore_variables, options)
            except Exception:
                log.error(title)
                raise

        tests.append(unittest.FunctionTestCase(check))

    return tests


def _generate_tests_from_directory(tax_benefit_system, path_to_dir, options):
    yaml_paths = glob.glob(os.path.join(path_to_dir, "*.yaml"))
    subdirectories = glob.glob(os.path.join(path_to_dir, "*/"))

    for yaml_path in yaml_paths:
        for test in list(_generate_tests_from_file(tax_benefit_system, yaml_path, options)):
            yield test

    for subdirectory in subdirectories:
        for test in list(_generate_tests_from_directory(tax_benefit_system, subdirectory, options)):
            yield test


def _parse_test_file(tax_benefit_system, yaml_path):
    filename = os.path.splitext(os.path.basename(yaml_path))[0]
    with open(yaml_path) as yaml_file:
        try:
            tests = yaml.load(yaml_file, Loader=yaml.CLoader)
        except yaml.scanner.ScannerError:
            log.error("{} is not a valid YAML file".format(yaml_path).encode('utf-8'))
            raise

    tests, error = conv.pipe(
        conv.make_item_to_singleton(),
        conv.uniform_sequence(
            conv.noop,
            drop_none_items = True,
            ),
        )(tests)

    if error is not None:
        embedding_error = conv.embed_error(tests, u'errors', error)
        assert embedding_error is None, embedding_error
        raise ValueError("Error in test {}:\n{}".format(yaml_path, yaml.dump(tests, allow_unicode = True,
            default_flow_style = False, indent = 2, width = 120)))

    for test in tests:
        current_tax_benefit_system = tax_benefit_system
        if test.get('reforms'):
            reforms = test.pop('reforms')
            if not isinstance(reforms, list):
                reforms = [reforms]
            for reform_path in reforms:
                current_tax_benefit_system = current_tax_benefit_system.apply_reform(reform_path)

        try:
            test, error = scenarios.make_json_or_python_to_test(
                tax_benefit_system = current_tax_benefit_system
                )(test)
        except Exception:
            log.error("{} is not a valid OpenFisca test file".format(yaml_path).encode('utf-8'))
            raise

        if error is not None:
            embedding_error = conv.embed_error(test, u'errors', error)
            assert embedding_error is None, embedding_error
            raise ValueError("Error in test {}:\n{}\nYaml test content: \n{}\n".format(
                yaml_path, error, yaml.dump(test, allow_unicode = True,
                default_flow_style = False, indent = 2, width = 120)))

        yield yaml_path, test.get('name') or filename, to_unicode(test['scenario'].period), test


def _run_test(period_str, test, simulation, verbose = False, only_variables = None, ignore_variables = None, options = {}):
    absolute_error_margin = None
    relative_error_margin = None
    if test.get('absolute_error_margin') is not None:
        absolute_error_margin = test.get('absolute_error_margin')
    if test.get('relative_error_margin') is not None:
        relative_error_margin = test.get('relative_error_margin')

    output_variables = test.get(u'output_variables')
    if output_variables is not None:
        try:
            for variable_name, expected_value in output_variables.items():
                variable_ignored = ignore_variables is not None and variable_name in ignore_variables
                variable_not_tested = only_variables is not None and variable_name not in only_variables
                if variable_ignored or variable_not_tested:
                    continue  # Skip this variable
                if isinstance(expected_value, dict):
                    for requested_period, expected_value_at_period in expected_value.items():
                        assert_near(
                            simulation.calculate(variable_name, requested_period),
                            expected_value_at_period,
                            absolute_error_margin = absolute_error_margin,
                            message = u'{}@{}: '.format(variable_name, requested_period),
                            relative_error_margin = relative_error_margin,
                            )
                else:
                    assert_near(
                        simulation.calculate(variable_name),
                        expected_value,
                        absolute_error_margin = absolute_error_margin,
                        message = u'{}@{}: '.format(variable_name, period_str),
                        relative_error_margin = relative_error_margin,
                        )
        finally:
            if verbose:
                print("Computation log:")
                simulation.tracer.print_computation_log()

import os
import time
import logging
import pkg_resources

from openfisca_france import CountryTaxBenefitSystem


# Baselines for comparision - unit : seconds
BASELINE_TBS_LOAD_TIME = 9.10831403732
BASELINE_YAML_TESTS_TIME = 271.448431969


# Time tax benefit system loading
start_time_tbs = time.time()
tbs = CountryTaxBenefitSystem()
time_spent_tbs = time.time() - start_time_tbs


openfisca_france_dir = pkg_resources.get_distribution('OpenFisca-France').location
yaml_tests_dir = os.path.join(openfisca_france_dir, 'tests', 'mes-aides.gouv.fr')


# Time openfisca-run-test runner
start_time_tests = time.time()
run_tests(tbs, yaml_tests_dir)
time_spent_tests = time.time() - start_time_tests


def compare_performance(baseline, test_result):
    delta = (test_result - baseline) * 100 / baseline

    if test_result > baseline * 1.2:
        logging.warning("The perfomance seems to have worsen by {} %.".format(delta))
    elif test_result < baseline * 0.8:
        logging.info("The performance seems to have been improved by {} %.".format(delta))
    else:
        logging.info("The performance seems steady ({} %).".format(delta))


print("Generate Tax Benefit System: --- {}s seconds ---".format(time_spent_tbs))
compare_performance(BASELINE_TBS_LOAD_TIME, time_spent_tbs)

print("Pass Mes-aides tests: --- {}s seconds ---".format(time_spent_tests))
compare_performance(BASELINE_YAML_TESTS_TIME, time_spent_tests)
