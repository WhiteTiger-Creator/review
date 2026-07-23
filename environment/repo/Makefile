BIN ?= /app/hexverdict
FC = gfortran
FFLAGS = -O2 -std=f2008 -ffree-line-length-none
SRCS = src/judge.f90 src/main.f90

all: $(BIN)

$(BIN): $(SRCS)
	$(FC) $(FFLAGS) -J. -o $(BIN) $(SRCS)

clean:
	rm -f $(BIN) *.mod *.o

.PHONY: all clean
