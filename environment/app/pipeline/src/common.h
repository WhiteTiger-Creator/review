#ifndef RISK_COMMON_H
#define RISK_COMMON_H

#include <stddef.h>

void die(const char *fmt, ...);
void *xmalloc(size_t n);
void *xrealloc(void *p, size_t n);
char *xstrdup(const char *s);
char *read_file(const char *path);

typedef struct {
    char **items;
    size_t len;
    size_t cap;
} strlist;

void strlist_push(strlist *l, const char *s);
int strlist_contains(const strlist *l, const char *s);
void strlist_sort(strlist *l);
void strlist_free(strlist *l);

int list_dir_sorted(const char *dir, const char *suffix, strlist *out);

void json_escape(const char *s, char *out, size_t outlen);

#endif
