GO  ?= go
BIN := bin/slate

.PHONY: all clean vet

all:
	@mkdir -p bin
	$(GO) build -o $(BIN) ./cmd/console

vet:
	$(GO) vet ./...

clean:
	rm -rf bin
