CXX ?= g++
CXXFLAGS ?= -O2 -std=c++17 -Wall

plucker: plucker.cpp
	$(CXX) $(CXXFLAGS) -o plucker plucker.cpp -lgmp -lgmpxx

.PHONY: clean
clean:
	rm -f plucker
