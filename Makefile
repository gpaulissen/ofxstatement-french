## -*- mode: make -*-

# project specific
PROJECT        := ofxstatement-french
BRANCH 	 	     := master

GIT = git
PYTHON_EXECUTABLES = python python3
VERBOSE := 
PIP = $(PYTHON) -O -m pip $(VERBOSE)
MYPY = mypy
# Otherwise perl may complain on a Mac
LANG = C

# OS specific section
ifeq '$(findstring ;,$(PATH))' ';'
detected_OS := Windows
HOME = $(USERPROFILE)
DEVNUL := NUL
WHICH := where
GREP := find
EXE := .exe
else
detected_OS := $(shell uname 2>/dev/null || echo Unknown)
detected_OS := $(patsubst CYGWIN%,Cygwin,$(detected_OS))
detected_OS := $(patsubst MSYS%,MSYS,$(detected_OS))
detected_OS := $(patsubst MINGW%,MSYS,$(detected_OS))
DEVNUL := /dev/null
WHICH := which
GREP := grep
EXE := 
endif

ifdef CONDA_PREFIX
home = $(subst \,/,$(CONDA_PREFIX))
else
home = $(HOME)
endif

ifdef CONDA_PYTHON_EXE
# look no further
PYTHON := $(subst \,/,$(CONDA_PYTHON_EXE))
else
# On Windows those executables may exist but not functional yet (can be used to install) so use Python -V
$(foreach e,$(PYTHON_EXECUTABLES),$(if $(shell ${e}${EXE} -V 3>${DEVNUL}),$(eval PYTHON := ${e}${EXE}),))
endif

ifndef PYTHON
$(error Could not find any Python executable from ${PYTHON_EXECUTABLES}.)
endif

.PHONY: help clean install test dist distclean upload

help: ## This help.
	@perl -ne 'printf(qq(%-30s  %s\n), $$1, $$2) if (m/^((?:\w|[.%-])+):.*##\s*(.*)$$/)' $(MAKEFILE_LIST)

init: ## Fulfill the requirements
	$(PIP) install -r requirements.txt

clean: init ## Cleanup the mess
	$(PYTHON) setup.py clean --all
	$(GIT) clean -d -x -i

install: clean ## Install the module locally
	$(PIP) install -e .
	$(PIP) install -r test_requirements.txt

test: ## Test the module locally
	$(MYPY) --show-error-codes src
	$(PYTHON) -m pytest --exitfirst

dist: install test ## Distribute the module
	$(PYTHON) setup.py sdist bdist_wheel
	$(PYTHON) -m twine check dist/*

upload_test: dist ## Upload to PyPI test
	$(PYTHON) -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*

upload: dist ## Upload to PyPI
	$(PYTHON) -m twine upload dist/*

# This is GNU specific I guess
VERSION = $(shell $(PYTHON) __about__.py)

TAG = v$(VERSION)

tag: ## Tag the package on GitHub.
	$(GIT) tag -a $(TAG) -m "$(TAG)"
	$(GIT) push origin $(TAG)
	gh release create $(TAG) --target $(BRANCH) --title "Release $(TAG)" --notes "See CHANGELOG"
