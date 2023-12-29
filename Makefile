## -*- mode: make -*-

# project specific
PROJECT        := ofxstatement-french
BRANCH 	 	     := master
PYTHON_VERSION := 3.6

CONDA          := conda
GIT 			     := git
# Otherwise perl may complain on a Mac
LANG           := C
# Must be invoked dynamic, i.e. the environment may not be ready yet
VERSION         = $(shell poetry version -s)
# Idem
TAG 	          = v$(VERSION)

# Goals not needing a Mamba (Conda) environment
GOALS_ENV_NO   := help env-bootstrap env-create env-update env-remove clean tag
# Goals needing a Mamba (Conda) environment (all the poetry commands)
GOALS_ENV_YES  := init install test dist upload_test upload 

ifneq '$(filter $(GOALS_ENV_YES),$(MAKECMDGOALS))' ''

ifneq '$(CONDA_DEFAULT_ENV)' '$(PROJECT)'
$(error Set up Conda environment ($(CONDA) activate $(PROJECT)))
endif

endif

.PHONY: $(GOALS_ENV_NO) $(GOALS_ENV_YES)

help: ## This help.
	@perl -ne 'printf(qq(%-30s  %s\n), $$1, $$2) if (m/^((?:\w|[.%-])+):.*##\s*(.*)$$/)' $(MAKEFILE_LIST)

env-bootstrap: ## Bootstrap an environment
	$(CONDA) create --name $(PROJECT) python
	$(CONDA) env export --from-history > environment.yml

env-create: ## Create Mamba (Conda) environment (only once)
	$(CONDA) env create --name $(PROJECT) --file environment.yml

env-update: ## Update Mamba (Conda) environment
	$(CONDA) env update --name $(PROJECT) --file environment.yml --prune

env-remove: ## Remove Mamba (Conda) environment
	-$(CONDA) env remove --name $(PROJECT)

init: ## Fulfill the requirements
	poetry build

clean: ## Cleanup the environment
	$(GIT) clean -d -x -i

install: init ## Install the package to the Python installation path.
	poetry install
	poetry lock

test: install ## Test the package.
	poetry check
	poetry run pytest

dist: install test ## Prepare the distribution the package by installing and testing it.

upload_test: dist ## Upload the package to PyPI test.
	poetry publish -r test-pypi

upload: dist ## Upload the package to PyPI.
	poetry publish

tag: ## Tag the package on GitHub.
	$(GIT) tag -a $(TAG) -m "$(TAG)"
	$(GIT) push origin $(TAG)
	gh release create $(TAG) --target $(BRANCH) --title "Release $(TAG)" --notes "See CHANGELOG"
