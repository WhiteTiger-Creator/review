#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int cmp_str(const void *a, const void *b) {
    return strcmp(*(const char **)a, *(const char **)b);
}

static int has_suffix(const char *s, const char *suf) {
    size_t ls = strlen(s), lf = strlen(suf);
    return ls >= lf && strcmp(s + ls - lf, suf) == 0;
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: %s <input_dir> <output_path>\n", argv[0]);
        return 2;
    }
    DIR *d = opendir(argv[1]);
    if (!d) { fprintf(stderr, "cannot open input dir\n"); return 2; }
    char **names = NULL;
    size_t count = 0, cap = 0;
    struct dirent *e;
    while ((e = readdir(d)) != NULL) {
        if (!has_suffix(e->d_name, ".txt")) continue;
        if (has_suffix(e->d_name, ".expected.txt")) continue;
        if (count == cap) { cap = cap ? cap * 2 : 16; names = realloc(names, cap * sizeof(char *)); }
        names[count++] = strdup(e->d_name);
    }
    closedir(d);
    qsort(names, count, sizeof(char *), cmp_str);
    FILE *out = fopen(argv[2], "w");
    if (!out) { fprintf(stderr, "cannot open output\n"); return 2; }
    for (size_t i = 0; i < count; i++) {
        char path[4096];
        snprintf(path, sizeof(path), "%s/%s", argv[1], names[i]);
        FILE *in = fopen(path, "r");
        if (!in) { free(names[i]); continue; }
        int n = 0, k = 0;
        if (fscanf(in, "%d %d", &n, &k) != 2) { fclose(in); free(names[i]); continue; }
        fclose(in);
        /* Starter: emit a placeholder. Replace this with a real computation of
         * the n Lyapunov exponents of the ordered product, in decreasing order. */
        fprintf(out, "%s", names[i]);
        for (int j = 0; j < n; j++) fprintf(out, " %.17g", 0.0);
        fprintf(out, "\n");
        free(names[i]);
    }
    fclose(out);
    free(names);
    return 0;
}
