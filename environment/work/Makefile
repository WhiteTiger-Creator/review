CXX ?= g++
CXXFLAGS ?= -std=c++20 -O2 -Wall -Wextra -Werror

all: bin/backfill-governance

bin/backfill-governance: src/backfill_governance.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) $< -o $@

clean:
	rm -f bin/backfill-governance

.PHONY: all clean
