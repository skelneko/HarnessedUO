# HarnessedUO entry points. Write each target as "name: ## description" so make help lists it.
.DEFAULT_GOAL := help
.PHONY: help

help: ## List make targets
	@grep -E '^[a-zA-Z0-9_-]+:.*## ' Makefile | sed 's/:.*## /: /'

.PHONY: hooks
hooks: ## Per-clone git setup: hooks path, fetch-only upstream, gh default repo
	@if [ "$$(git config core.hooksPath)" = ".githooks" ]; then echo "hooks: core.hooksPath already .githooks"; else git config core.hooksPath .githooks && echo "hooks: set core.hooksPath to .githooks"; fi
	@chmod +x .githooks/pre-commit .githooks/pre-push
	@if git remote get-url upstream >/dev/null 2>&1; then echo "hooks: upstream remote already present"; else git remote add --no-tags -t main upstream https://github.com/ClassicUO/ClassicUO.git && echo "hooks: added upstream remote (main only, no tags)"; fi
	@if [ "$$(git remote get-url --push upstream)" = "DISABLED" ]; then echo "hooks: upstream push already DISABLED"; else git remote set-url --push upstream DISABLED && echo "hooks: set upstream push URL to DISABLED"; fi
	@if [ "$$(git config remote.origin.gh-resolved)" = "base" ]; then echo "hooks: gh default repo already skelneko/HarnessedUO"; else git config remote.origin.gh-resolved base && echo "hooks: set gh default repo to skelneko/HarnessedUO (origin)"; fi

.PHONY: deps
deps: ## Install Homebrew tools, .NET SDK, uv and Python, then print versions
	@if [ -w "$$(brew --prefix)" ]; then brew bundle install --file=Brewfile --no-upgrade; else echo "deps: Homebrew belongs to $$(stat -f %Su "$$(brew --prefix)"), so this only checks; install as that user (P0.04 step 7)"; HOMEBREW_NO_AUTO_UPDATE=1 brew bundle check --file=Brewfile --no-upgrade --verbose; fi
	uv python install
	@echo "dotnet $$(dotnet --version)"
	@echo "gitleaks $$(gitleaks version)"
	@uv --version
	@uv run python --version

.PHONY: doctor
doctor: ## Check tools, git setup, .env and host role (never prints secrets)
	@uv run python huo/tools/doctor.py
