NODE ?= node

dist/main.mjs: src/main.ts src/emd.ts build.mjs
	$(NODE) build.mjs

.PHONY: clean
clean:
	rm -rf dist
