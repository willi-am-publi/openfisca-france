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


performance:
	python openfisca_france/scripts/performance_tests/test_tests.py

cprof: clean check-syntax-errors
	python -m cProfile -o tests.cprof ./openfisca_france/scripts/test_runner.py --country-package openfisca_france tests

cplot:
	gprof2dot -z simulations:132:calculate -n 25.0 -e 0 -f pstats tests.cprof | dot -Tpng -o cprof.png

bprof: clean check-syntax-errors
	kernprof -v -b -o tests.bprof ./openfisca_france/scripts/test_runner.py --country-package openfisca_france tests

bplot:
	gprof2dot -n 25.0 -e 0 -f pstats tests.bprof | dot -Tpng -o bprof.png

lprof1: clean check-syntax-errors
	kernprof -v -l ./openfisca_france/scripts/test_runner.py --country-package openfisca_france tests
	python -m line_profiler test_runner.py.lprof > tests1.lprof
	rm test_runner.py.lprof

lprof2: clean check-syntax-errors
	kernprof -v -l ./openfisca_france/scripts/test_runner.py --country-package openfisca_france tests
	python -m line_profiler test_runner.py.lprof > tests2.lprof
	rm test_runner.py.lprof

lprof3: clean check-syntax-errors
	kernprof -v -l ./openfisca_france/scripts/test_runner.py --country-package openfisca_france tests
	python -m line_profiler test_runner.py.lprof > tests3.lprof
	rm test_runner.py.lprof
