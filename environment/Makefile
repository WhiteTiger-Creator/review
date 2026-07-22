CC = gcc
CFLAGS = -O2 -Iinclude
LDLIBS = -ldmumps_seq -lmumps_common_seq -lpord_seq -lmpiseq_seq -llapack -lblas -lgfortran -lm

SRC = src/main.c src/mtxread.c src/vecgen.c src/query.c src/counter.c

spectral_count: $(SRC)
	$(CC) $(CFLAGS) $(SRC) -o spectral_count $(LDLIBS)

clean:
	rm -f spectral_count
