JAR := target/trivia-dungeon-1.0.0-SNAPSHOT.jar
ROOT := /app
CONFIG := $(ROOT)/config/dungeon.toml
DATASET := /data/trivia_qa_sample.parquet
CONTRACTS := /data/contracts
OUTPUT := /output
STATE := $(ROOT)/.state/audit-state.json
ANSWERS := $(ROOT)/config/verification-answers.toml
MVN := mvn -o -q

.PHONY: clean build test audit playthrough verify

# Authoring-only overlays may copy Java sources from JAVA_SOURCE_PATCHES before build.

clean:
	$(MVN) clean

build:
	$(MVN) package -DskipTests

test:
	$(MVN) test

audit: build
	./bin/trivia-dungeon audit \
		--root $(ROOT) \
		--config $(CONFIG) \
		--dataset $(DATASET) \
		--contracts $(CONTRACTS) \
		--output $(OUTPUT) \
		--state $(STATE)

playthrough: build
	./bin/trivia-dungeon playthrough \
		--root $(ROOT) \
		--config $(CONFIG) \
		--dataset $(DATASET) \
		--contracts $(CONTRACTS) \
		--answers $(ANSWERS) \
		--output $(OUTPUT) \
		--state $(STATE)

verify: clean build test audit playthrough
