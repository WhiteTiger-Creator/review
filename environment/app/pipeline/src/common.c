#include "common.h"

#include <dirent.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void die(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    fputs("error: ", stderr);
    vfprintf(stderr, fmt, ap);
    fputc('\n', stderr);
    va_end(ap);
    exit(1);
}

void *xmalloc(size_t n)
{
    void *p = malloc(n);
    if (!p)
        die("out of memory");
    return p;
}

void *xrealloc(void *p, size_t n)
{
    p = realloc(p, n);
    if (!p)
        die("out of memory");
    return p;
}

char *xstrdup(const char *s)
{
    char *p = xmalloc(strlen(s) + 1);
    strcpy(p, s);
    return p;
}

char *read_file(const char *path)
{
    FILE *f = fopen(path, "rb");
    long sz;
    char *buf;
    if (!f)
        die("cannot open %s", path);
    if (fseek(f, 0, SEEK_END) != 0)
        die("cannot seek %s", path);
    sz = ftell(f);
    if (sz < 0)
        die("cannot size %s", path);
    rewind(f);
    buf = xmalloc((size_t)sz + 1);
    if (fread(buf, 1, (size_t)sz, f) != (size_t)sz)
        die("cannot read %s", path);
    buf[sz] = '\0';
    fclose(f);
    return buf;
}

void strlist_push(strlist *l, const char *s)
{
    if (l->len == l->cap) {
        l->cap = l->cap ? l->cap * 2 : 8;
        l->items = xrealloc(l->items, l->cap * sizeof(*l->items));
    }
    l->items[l->len++] = xstrdup(s);
}

int strlist_contains(const strlist *l, const char *s)
{
    size_t i;
    for (i = 0; i < l->len; i++)
        if (strcmp(l->items[i], s) == 0)
            return 1;
    return 0;
}

static int cmp_str(const void *a, const void *b)
{
    return strcmp(*(char *const *)a, *(char *const *)b);
}

void strlist_sort(strlist *l)
{
    qsort(l->items, l->len, sizeof(*l->items), cmp_str);
}

void strlist_free(strlist *l)
{
    size_t i;
    for (i = 0; i < l->len; i++)
        free(l->items[i]);
    free(l->items);
    l->items = NULL;
    l->len = l->cap = 0;
}

int list_dir_sorted(const char *dir, const char *suffix, strlist *out)
{
    DIR *d = opendir(dir);
    struct dirent *ent;
    size_t slen = strlen(suffix);
    if (!d)
        return -1;
    while ((ent = readdir(d)) != NULL) {
        size_t n = strlen(ent->d_name);
        if (ent->d_name[0] == '.')
            continue;
        if (n < slen || strcmp(ent->d_name + n - slen, suffix) != 0)
            continue;
        strlist_push(out, ent->d_name);
    }
    closedir(d);
    strlist_sort(out);
    return 0;
}

void json_escape(const char *s, char *out, size_t outlen)
{
    size_t o = 0;
    for (; *s && o + 6 < outlen; s++) {
        unsigned char c = (unsigned char)*s;
        if (c == '"' || c == '\\') {
            out[o++] = '\\';
            out[o++] = (char)c;
        } else if (c < 0x20) {
            o += (size_t)snprintf(out + o, outlen - o, "\\u%04x", c);
        } else {
            out[o++] = (char)c;
        }
    }
    out[o] = '\0';
}
