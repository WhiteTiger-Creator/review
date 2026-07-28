.PHONY: all clean

BINARY := build/trust_attest
PKG := ./cmd/trust-attest

all: $(BINARY)

$(BINARY): $(shell find . -name '*.go' -not -path './build/*')
	@mkdir -p build
	go build -o $(BINARY) $(PKG)

clean:
	rm -rf build
