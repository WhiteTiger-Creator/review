SRC_DIR := src/main/java
OUT_DIR := build/classes
JAR := build/emberline-game.jar
SOURCES := $(shell find $(SRC_DIR) -name '*.java' | sort)

.PHONY: all clean jar classes

all: jar

classes: $(OUT_DIR)/.compiled

$(OUT_DIR)/.compiled: $(SOURCES)
	mkdir -p $(OUT_DIR)
	javac --release 21 -d $(OUT_DIR) $(SOURCES)
	@touch $@

jar: $(OUT_DIR)/.compiled
	mkdir -p build
	jar cf $(JAR) -C $(OUT_DIR) .

clean:
	rm -rf build
