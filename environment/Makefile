CXX ?= g++
CXXFLAGS ?= -O2 -std=c++17
SRCS := $(wildcard src/*.cpp)

retro: $(SRCS)
	$(CXX) $(CXXFLAGS) $(SRCS) -o retro

clean:
	rm -f retro
