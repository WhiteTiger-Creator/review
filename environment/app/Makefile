CXX ?= g++
CPPFLAGS := -Iinclude
CXXFLAGS := -std=c++20 -O2 -Wall -Wextra -Wpedantic -Werror
LDFLAGS := -static-libstdc++ -static-libgcc

COMMON_OBJS := build/util.o
RELAY_OBJS := build/relay_main.o build/config.o build/http.o build/route.o $(COMMON_OBJS)

.PHONY: all clean
all: bin/harbor-relay bin/catalog-query

bin/harbor-relay: $(RELAY_OBJS) | bin
	$(CXX) $(LDFLAGS) -o $@ $(RELAY_OBJS)

bin/catalog-query: tools/catalog_query.cpp | bin
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $(LDFLAGS) -o $@ $< -lsqlite3

build/%.o: src/%.cpp | build
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -MMD -MP -c -o $@ $<

build bin:
	mkdir -p $@

clean:
	rm -rf build bin

-include $(wildcard build/*.d)
