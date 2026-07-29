BIN := handsettle

.PHONY: all build test clean

all: build

build:
	go build -o $(BIN) ./cmd/handsettle

test:
	go test ./...

clean:
	rm -f $(BIN)
