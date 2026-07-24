ENV_ROOT ?= /app/environment
BUILD := $(ENV_ROOT)/build

.PHONY: build compile fixtures
build: compile
	@mkdir -p $(BUILD)
	@cd $(ENV_ROOT) && go build -o /app/admit-repo ./cmd/admit-repo

compile:
	@cd $(ENV_ROOT) && go mod tidy && go build ./...

fixtures:
	@bash $(ENV_ROOT)/scripts/build_fixtures.sh
