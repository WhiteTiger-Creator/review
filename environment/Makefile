.PHONY: build run clean

GO := /usr/local/go/bin/go
BINARY := /app/build/gridknit

build:
	@mkdir -p /app/build
	cd /app && $(GO) build -o build/gridknit ./gridknit

run: build
	/app/build/gridknit

clean:
	rm -f /app/build/gridknit /app/build/gradle_stabilization_report.json
