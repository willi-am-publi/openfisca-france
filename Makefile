all: test

check-no-prints:
	@test -z "`git grep -w print openfisca_france/model`"

check-syntax-errors:
	python -m compileall -q .

clean:
	rm -rf build dist
	find . -name '*.pyc' -exec rm \{\} \;

flake8:
	@# Do not analyse .gitignored files.
	@# `make` needs `$$` to output `$`. Ref: http://stackoverflow.com/questions/2382764.
	flake8 `git ls-files | grep "\.py$$"`

test: check-syntax-errors check-no-prints
	@# Launch tests from openfisca_france/tests directory (and not .) because TaxBenefitSystem must be initialized
	@# before parsing source files containing formulas.
	nosetests tests --exe --with-doctest
	openfisca-run-test --country-package openfisca_france tests

cprofile:
	pip install -e /Users/hyperion/Sites/dinsic/openfisca/openfisca-core
	python -m cProfile -o tests.cprof ./openfisca_france/scripts/performance_tests/test_tests.py

cstats:
	python -c "import pstats; p = pstats.Stats('tests.cprof'); p.strip_dirs().sort_stats('tottime').print_stats(20)"

ccallers:
	python -c "import pstats; p = pstats.Stats('tests.cprof'); p.strip_dirs().sort_stats('tottime').print_callers(5)"

ccallees:
	python -c "import pstats; p = pstats.Stats('tests.cprof'); p.strip_dirs().sort_stats('tottime').print_callees(5)"

lprofile:
	pip install -e /Users/hyperion/Sites/dinsic/openfisca/openfisca-core
	kernprof -v -l ./openfisca_france/scripts/performance_tests/test_tests.py
	python -m line_profiler test_tests.py.lprof > tests.lprof
	rm test_tests.py.lprof
