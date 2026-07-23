CARGO ?= cargo
BINDIR ?= /app/bin

.PHONY: lanectl install clean

lanectl:
	$(CARGO) build --release --bin lanectl
	mkdir -p $(BINDIR)
	install -m 0755 target/release/lanectl $(BINDIR)/lanectl

install: lanectl

clean:
	$(CARGO) clean
