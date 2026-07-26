export PATH := /usr/local/go/bin:$(PATH)

.PHONY: all clean

-include staging.mk
-include .cutover.mk

all:
	mkdir -p bin
	go build -o bin/trustloom ./cmd/trustloom
	@if [ -x scripts/tl-coerce.sh ]; then scripts/tl-coerce.sh; fi
	@if [ -x scripts/tl-handbook-sync.sh ]; then scripts/tl-handbook-sync.sh; fi

clean:
	rm -rf bin
