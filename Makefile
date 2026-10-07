# HarnessedUO entry points. Write each target as "name: ## description" so make help lists it.
.DEFAULT_GOAL := help
.PHONY: help

help: ## List make targets
	@grep -E '^[a-zA-Z0-9_-]+:.*## ' Makefile | sed 's/:.*## /: /'
