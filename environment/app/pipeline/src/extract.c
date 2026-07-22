#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "common.h"
#include "pinsel.h"
#include <vercmp.h>

typedef struct {
    char *name;
    strlist versions;
    strlist files;
} pkg_t;

static pkg_t *pkgs;
static size_t npkgs, cappkgs;

static pkg_t *get_pkg(const char *name)
{
    size_t i;
    for (i = 0; i < npkgs; i++)
        if (strcmp(pkgs[i].name, name) == 0)
            return &pkgs[i];
    if (npkgs == cappkgs) {
        cappkgs = cappkgs ? cappkgs * 2 : 16;
        pkgs = xrealloc(pkgs, cappkgs * sizeof(*pkgs));
    }
    memset(&pkgs[npkgs], 0, sizeof(pkgs[npkgs]));
    pkgs[npkgs].name = xstrdup(name);
    return &pkgs[npkgs++];
}

static int name_char(char c)
{
    return isalnum((unsigned char)c) || c == '_' || c == '.' || c == '-';
}

static void scan_line(const char *line, const char *fname)
{
    size_t i = 0;
    while (line[i]) {
        if (name_char(line[i])) {
            size_t j = i;
            while (name_char(line[j]))
                j++;
            if (line[j] == '=' && line[j + 1] == '=' &&
                isdigit((unsigned char)line[j + 2])) {
                size_t k = j + 2;
                char name[128], ver[64];
                size_t n;
                pkg_t *p;
                while (isdigit((unsigned char)line[k]) || line[k] == '.')
                    k++;
                if (j - i < sizeof(name) && k - j - 2 < sizeof(ver)) {
                    for (n = 0; n < j - i; n++)
                        name[n] = (char)tolower((unsigned char)line[i + n]);
                    name[j - i] = '\0';
                    memcpy(ver, line + j + 2, k - j - 2);
                    ver[k - j - 2] = '\0';
                    p = get_pkg(name);
                    if (!strlist_contains(&p->versions, ver))
                        strlist_push(&p->versions, ver);
                    if (!strlist_contains(&p->files, fname))
                        strlist_push(&p->files, fname);
                }
                i = k;
                continue;
            }
            i = j;
            continue;
        }
        i++;
    }
}

static int fence_line(const char *line)
{
    while (*line == ' ' || *line == '\t')
        line++;
    return strncmp(line, "```", 3) == 0;
}

static void scan_file(const char *dir, const char *fname)
{
    char path[4096];
    char *text, *line, *next;
    int in_fence = 0;
    snprintf(path, sizeof(path), "%s/%s", dir, fname);
    text = read_file(path);
    for (line = text; line; line = next) {
        char *nl = strchr(line, '\n');
        if (nl) {
            *nl = '\0';
            next = nl + 1;
        } else {
            next = NULL;
        }
        if (fence_line(line)) {
            in_fence = !in_fence;
            continue;
        }
        if (in_fence)
            scan_line(line, fname);
    }
    free(text);
}

static int cmp_pkg(const void *a, const void *b)
{
    return strcmp(((const pkg_t *)a)->name, ((const pkg_t *)b)->name);
}

int main(int argc, char **argv)
{
    strlist files = {0};
    size_t i;
    FILE *out;

    if (argc != 3) {
        fprintf(stderr, "usage: extract <docs-dir> <out-tsv>\n");
        return 2;
    }
    if (list_dir_sorted(argv[1], ".md", &files) != 0)
        die("cannot read docs directory %s", argv[1]);
    if (files.len == 0)
        die("no .md pages in %s", argv[1]);
    for (i = 0; i < files.len; i++)
        scan_file(argv[1], files.items[i]);

    qsort(pkgs, npkgs, sizeof(*pkgs), cmp_pkg);
    out = fopen(argv[2], "w");
    if (!out)
        die("cannot write %s", argv[2]);
    for (i = 0; i < npkgs; i++) {
        const char *assessed =
            pin_select(pkgs[i].versions.items, pkgs[i].versions.len);
        if (!ver_ok(assessed))
            die("bad version %s for %s", assessed, pkgs[i].name);
        fprintf(out, "%s\t%s\t%zu\n", pkgs[i].name, assessed,
                pkgs[i].files.len);
    }
    if (fclose(out) != 0)
        die("cannot finish %s", argv[2]);
    fprintf(stderr, "extract: %zu packages from %zu pages\n", npkgs,
            files.len);
    return 0;
}
