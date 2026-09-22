# Makefile for fltools development, installation, and FLDigi integration

PACKAGE       := fltools
SRC_DIR       := src/

# --- FLDIGI CONFIGURATION DIRECTORIES ---
# Where the fltools symlink gets placed. FLDigi defaults to ~/.fldigi, but a
# station running more than one rig launches an instance per configuration
# (fldigi --config-dir DIRECTORY), and each one needs its own link. List them
# all here, or override for a single run:
#     make link FLDIGI_DIRS="~/.fldigi-hf ~/.fldigi-vhf"
FLDIGI_DIRS   := ~/.fldigi
FLDIGI_SCRIPTS := $(addsuffix /scripts,$(FLDIGI_DIRS))
FLDIGI_LINKS  := $(addsuffix /fltools,$(FLDIGI_SCRIPTS))

# --- PYTHON FLOOR ---
# The oldest interpreter fltools supports. Kept in step with requires-python
# in pyproject.toml; vermin checks that the source has not drifted past it.
PY_TARGET     := 3.10

dev: ## Create or update the project venv, including the dev group
	@echo "=== SYNCING PROJECT ENVIRONMENT ==="
	uv sync
.PHONY: dev

install: ## Install fltools as a tool and link it into FLDigi's script dir
	@echo "=== INSTALLING TOOL ==="
	uv tool install . --reinstall
	@echo "=== LINKING INTO FLDIGI ==="
	$(PACKAGE) --link $(FLDIGI_SCRIPTS)
.PHONY: install

install-dev: ## Install as an editable tool so source edits take effect live
	@echo "=== INSTALLING TOOL (EDITABLE) ==="
	uv tool install --editable . --reinstall
	@echo "=== LINKING INTO FLDIGI ==="
	$(PACKAGE) --link $(FLDIGI_SCRIPTS)
.PHONY: install-dev

link: ## Re-point the FLDigi symlinks at the installed executable
	@echo "=== LINKING INTO FLDIGI ==="
	$(PACKAGE) --link $(FLDIGI_SCRIPTS)
.PHONY: link

uninstall: ## Remove the FLDigi symlinks and uninstall the tool
	@echo "=== REMOVING FLDIGI LINKS ==="
	rm -f $(FLDIGI_LINKS)
	@echo "=== UNINSTALLING TOOL ==="
	uv tool uninstall $(PACKAGE)
.PHONY: uninstall

hooks: ## Install the pre-commit hooks into this clone
	@echo "=== INSTALLING PRE-COMMIT HOOKS ==="
	uv run pre-commit install
.PHONY: hooks

format: ## Reformat the source with black
	@echo "=== FORMATTING ==="
	uv run black $(SRC_DIR)
.PHONY: format

lint: ## Lint the source with ruff, fixing what can be fixed
	@echo "=== LINTING ==="
	uv run ruff check --fix $(SRC_DIR)
.PHONY: lint

typecheck: ## Type check the source with mypy
	@echo "=== TYPE CHECKING ==="
	uv run mypy
.PHONY: typecheck

floor: ## Confirm the source needs nothing newer than PY_TARGET
	@echo "=== CHECKING PYTHON FLOOR ($(PY_TARGET)) ==="
	uv run vermin --target=$(PY_TARGET) --no-tips $(SRC_DIR)
.PHONY: floor

check: ## Run every check without modifying anything (what CI should run)
	@echo "=== CHECKING FORMAT ==="
	uv run black --check $(SRC_DIR)
	@echo "=== LINTING ==="
	uv run ruff check $(SRC_DIR)
	@echo "=== TYPE CHECKING ==="
	uv run mypy
	@echo "=== CHECKING PYTHON FLOOR ($(PY_TARGET)) ==="
	uv run vermin --target=$(PY_TARGET) --no-tips $(SRC_DIR)
	@echo "=== CHECKING LOCKFILE IS CURRENT ==="
	uv lock --check
.PHONY: check

build: ## Build the wheel and sdist into dist/
	@echo "=== BUILDING ==="
	uv build
.PHONY: build

paths: ## Show where fltools reads and writes its files
	@echo "=== RESOLVED PATHS ==="
	$(PACKAGE) --paths
.PHONY: paths

clean: ## Remove build artifacts and caches, but not the venv
	@echo "=== CLEANING BUILD ARTIFACTS ==="
	rm -rf dist/ build/ .ruff_cache/ .mypy_cache/
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +
.PHONY: clean

clean-all: clean ## Also remove the project venv, forcing a full rebuild
	@echo "=== REMOVING PROJECT ENVIRONMENT ==="
	rm -rf .venv/
.PHONY: clean-all

help: ## Show this help
	@egrep -h '\s##\s' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
.PHONY: help
.DEFAULT_GOAL = help
