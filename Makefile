.DEFAULT_GOAL := help

# The project's one Makefile. Everything runs through the project virtualenv, which
# `make install` builds with uv from pyproject.toml + uv.lock. See docs/SDLC.md.
#
# Agents run targets as `bobp make <target>` (captures output, posts status). Team tooling such
# as chat and TL;DR summaries is provided by bobp itself (`bobp chat`, `bobp tldr`), not here.
PYTHON := .venv/bin/python
PYTHONS := 3.14 3.15
# The command the package installs (docs/SDLC.md section 7).
CLI := .venv/bin/fingerprint

# First line of any recipe that needs the environment.
define need_venv
	@test -x $(PYTHON) || { echo "No .venv - run 'make install' first"; exit 1; }
endef

define need_uv
	@command -v uv >/dev/null || { echo "uv is not installed - run 'pipx install uv' (see docs/SDLC.md)"; exit 1; }
endef

.PHONY: help install install-hooks check test test-all smoke lint quality format secrets build release-check run gharchive clean distclean via_index

help: ## Show available make targets
	@echo ""
	@echo "  Project targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "    \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""

install: install-hooks ## Build .venv from uv.lock (package + dev tools) and install the git hooks
	$(need_uv)
	@uv sync --all-extras --quiet
	@echo "Installed into .venv"

install-hooks: ## Point git at .githooks/ (gitleaks pre-commit scan)
	@git config core.hooksPath .githooks

check: ## Byte-compile all sources (fast syntax check, no tests run)
	$(need_venv)
	@$(PYTHON) -m compileall -q src tests smoke

test: ## Run the test suite (ARGS=test_cli runs one module)
	$(need_venv)
	@$(PYTHON) -m unittest discover -s tests $(if $(ARGS),-p "$(ARGS).py")

test-all: ## Run the test suite on every supported Python (3.14, 3.15) in throwaway environments
	$(need_uv)
	@for v in $(PYTHONS); do \
		echo "== Python $$v =="; \
		out=$$(uv run --isolated --all-extras --quiet --python $$v python -m unittest discover -s tests 2>&1) \
			|| { echo "$$out" | tail -n 40; exit 1; }; \
		echo "$$out" | grep -E '^(Ran|OK|FAILED)'; \
	done

lint: ## Static checks: ruff lint + format check (changes nothing)
	$(need_venv)
	@.venv/bin/ruff check .
	@.venv/bin/ruff format --check .

quality: ## Report smells: extended ruff, dead code, complexity (never fails)
	$(need_venv)
	@echo "== ruff (extended rules)"; .venv/bin/ruff check src --select C90,SIM,PL,RET,ARG,PIE,FBT --output-format concise --exit-zero
	@echo "== vulture (dead code)"; .venv/bin/vulture src --min-confidence 60 || true
	@echo "== radon (complexity grade C or worse)"; .venv/bin/radon cc -s -nc src

format: ## Rewrite files to the project style (ruff format + import sorting)
	$(need_venv)
	@.venv/bin/ruff check --select I --fix .
	@.venv/bin/ruff format .

secrets: ## Scan the git history and working tree for leaked secrets (gitleaks)
	@command -v gitleaks >/dev/null || { echo "gitleaks is not installed - see docs/SDLC.md"; exit 1; }
	@gitleaks detect --source .

build: ## Build the wheel + sdist into dist/ and check the built command runs in a clean environment
	$(need_uv)
	@rm -rf dist
	@uv build --out-dir dist --quiet
	@uv run --isolated --no-project --quiet --with dist/*.whl $(notdir $(CLI)) --version
	@ls dist

smoke: build ## Install the built wheel in a throwaway environment and run the smoke suite against it
	@uv run --isolated --no-project --quiet --with dist/*.whl python -m unittest discover -s smoke -t smoke

release-check: ## Fail unless TAG (e.g. TAG=v0.3.0) matches the package version
	$(need_uv)
	@version=$$(uv version --short); \
	test "v$$version" = "$(TAG)" \
		|| { echo "Tag '$(TAG)' does not match package version '$$version' (expected v$$version)"; exit 1; }
	@echo "Tag $(TAG) matches version $$(uv version --short)"

run: ## Run the CLI (ARGS="merge --help")
	$(need_venv)
	@$(CLI) $(ARGS)

GH_HOUR ?= 2024-01-01-15
GH_DIR := data/gharchive

gharchive: ## Merge one hour of GitHub events from GH Archive (GH_HOUR=YYYY-MM-DD-H); downloads it once into data/
	$(need_venv)
	@mkdir -p $(GH_DIR)
	@test -s $(GH_DIR)/$(GH_HOUR).json.gz || curl -sSfL -o $(GH_DIR)/$(GH_HOUR).json.gz https://data.gharchive.org/$(GH_HOUR).json.gz
	@gunzip -c $(GH_DIR)/$(GH_HOUR).json.gz | $(CLI) merge -p examples/gharchive.yaml -s $(GH_DIR)/gh.fingerprints.yaml -

clean: ## Remove caches, build output and downloaded test data in data/ (keeps .venv)
	@find . -name __pycache__ -type d -not -path './.venv/*' -prune -exec rm -rf {} +
	@rm -rf .ruff_cache dist data

distclean: clean ## Also remove the virtualenv
	@rm -rf .venv

via_index: ## Build the via index required by the via MCP server
	@via index "$(CURDIR)"
