#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void upcase(char *s)
{
    for (; *s; s++)
        *s = (char)toupper((unsigned char)*s);
}

int main(int argc, char **argv)
{
    FILE *in, *out;
    char line[256];
    int wrote = 0;

    if (argc != 3) {
        fprintf(stderr, "usage: mkscore <severity-map> <out-header>\n");
        return 2;
    }
    in = fopen(argv[1], "r");
    if (!in) {
        fprintf(stderr, "mkscore: cannot open %s\n", argv[1]);
        return 1;
    }
    out = fopen(argv[2], "w");
    if (!out) {
        fprintf(stderr, "mkscore: cannot write %s\n", argv[2]);
        return 1;
    }
    fprintf(out, "#ifndef RISK_SEVERITY_TABLE_H\n#define RISK_SEVERITY_TABLE_H\n\n");
    while (fgets(line, sizeof(line), in)) {
        char kind[64], key[64];
        long value;
        if (line[0] == '#' || line[0] == '\n')
            continue;
        if (sscanf(line, "%63s %63s %ld", kind, key, &value) == 3) {
            upcase(key);
            if (strcmp(kind, "label") == 0)
                fprintf(out, "#define SEV_LABEL_%s %ld\n", key, value);
            else if (strcmp(kind, "coeff") == 0)
                fprintf(out, "#define COEFF_%s %ld\n", key, value);
            else {
                fprintf(stderr, "mkscore: bad entry: %s", line);
                return 1;
            }
            wrote++;
        } else if (sscanf(line, "%63s %ld", kind, &value) == 2 &&
                   strcmp(kind, "cap") == 0) {
            fprintf(out, "#define RISK_CAP %ld\n", value);
            wrote++;
        } else {
            fprintf(stderr, "mkscore: bad line: %s", line);
            return 1;
        }
    }
    fprintf(out, "\n#endif\n");
    fclose(in);
    if (fclose(out) != 0 || wrote == 0) {
        fprintf(stderr, "mkscore: nothing generated\n");
        return 1;
    }
    return 0;
}
