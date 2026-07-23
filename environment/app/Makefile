.PHONY: build run test tidy

build:
	go build -o bin/authgw ./cmd/authgw

run: build
	./bin/authgw

test:
	go test ./...

tidy:
	go mod tidy
