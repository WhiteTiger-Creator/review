CXX = g++
CXXFLAGS = -std=c++17 -Wall -O2

SRCDIR = src
INCDIR = include
BINDIR = bin

TARGET = $(BINDIR)/symlink-health

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRCDIR)/engine.cpp
	@mkdir -p $(BINDIR)
	$(CXX) $(CXXFLAGS) -I$(INCDIR) -o $@ $<

clean:
	rm -rf $(BINDIR)
