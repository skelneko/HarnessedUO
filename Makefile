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
	@if [ "$$(gh repo set-default --view 2>/dev/null)" = "skelneko/HarnessedUO" ]; then echo "hooks: gh default repo already skelneko/HarnessedUO"; else gh repo set-default skelneko/HarnessedUO && echo "hooks: set gh default repo to skelneko/HarnessedUO"; fi

.PHONY: deps
deps: ## Install Homebrew tools, .NET SDK, uv and Python, then print versions
	brew bundle install --file=Brewfile --no-upgrade
	uv python install
	@echo "dotnet $$(dotnet --version)"
	@echo "gitleaks $$(gitleaks version)"
	@uv --version
	@uv run python --version
