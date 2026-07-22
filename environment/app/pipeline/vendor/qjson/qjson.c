#include "qjson.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct qj_value {
    qj_type_t type;
    int boolean;
    double num;
    char *str;
    struct qj_value **items;
    char **keys;
    size_t len;
    size_t cap;
};

typedef struct {
    const char *p;
    char *errbuf;
    size_t errlen;
    int depth;
} qj_parser;

static qj_value *parse_value(qj_parser *ps);

static void set_err(qj_parser *ps, const char *msg)
{
    if (ps->errbuf && ps->errlen > 0)
        snprintf(ps->errbuf, ps->errlen, "%s near '%.16s'", msg, ps->p);
}

static qj_value *new_value(qj_type_t t)
{
    qj_value *v = calloc(1, sizeof(*v));
    if (!v)
        abort();
    v->type = t;
    return v;
}

void qj_free(qj_value *v)
{
    size_t i;
    if (!v)
        return;
    free(v->str);
    for (i = 0; i < v->len; i++) {
        qj_free(v->items[i]);
        if (v->keys)
            free(v->keys[i]);
    }
    free(v->items);
    free(v->keys);
    free(v);
}

static void push_item(qj_value *v, char *key, qj_value *item)
{
    if (v->len == v->cap) {
        size_t ncap = v->cap ? v->cap * 2 : 8;
        v->items = realloc(v->items, ncap * sizeof(*v->items));
        if (!v->items)
            abort();
        if (v->type == QJ_OBJ) {
            v->keys = realloc(v->keys, ncap * sizeof(*v->keys));
            if (!v->keys)
                abort();
        }
        v->cap = ncap;
    }
    v->items[v->len] = item;
    if (v->type == QJ_OBJ)
        v->keys[v->len] = key;
    v->len++;
}

static void skip_ws(qj_parser *ps)
{
    while (*ps->p == ' ' || *ps->p == '\t' || *ps->p == '\n' || *ps->p == '\r')
        ps->p++;
}

static int utf8_encode(unsigned long cp, char *out)
{
    if (cp < 0x80) {
        out[0] = (char)cp;
        return 1;
    }
    if (cp < 0x800) {
        out[0] = (char)(0xC0 | (cp >> 6));
        out[1] = (char)(0x80 | (cp & 0x3F));
        return 2;
    }
    if (cp < 0x10000) {
        out[0] = (char)(0xE0 | (cp >> 12));
        out[1] = (char)(0x80 | ((cp >> 6) & 0x3F));
        out[2] = (char)(0x80 | (cp & 0x3F));
        return 3;
    }
    out[0] = (char)(0xF0 | (cp >> 18));
    out[1] = (char)(0x80 | ((cp >> 12) & 0x3F));
    out[2] = (char)(0x80 | ((cp >> 6) & 0x3F));
    out[3] = (char)(0x80 | (cp & 0x3F));
    return 4;
}

static int hex4(const char *s, unsigned long *out)
{
    unsigned long v = 0;
    int i;
    for (i = 0; i < 4; i++) {
        char c = s[i];
        v <<= 4;
        if (c >= '0' && c <= '9')
            v |= (unsigned long)(c - '0');
        else if (c >= 'a' && c <= 'f')
            v |= (unsigned long)(c - 'a' + 10);
        else if (c >= 'A' && c <= 'F')
            v |= (unsigned long)(c - 'A' + 10);
        else
            return 0;
    }
    *out = v;
    return 1;
}

static char *parse_string_raw(qj_parser *ps)
{
    size_t cap = 32, len = 0;
    char *buf;
    if (*ps->p != '"') {
        set_err(ps, "expected string");
        return NULL;
    }
    ps->p++;
    buf = malloc(cap);
    if (!buf)
        abort();
    while (*ps->p && *ps->p != '"') {
        char tmp[4];
        int n = 0;
        if (*ps->p == '\\') {
            ps->p++;
            switch (*ps->p) {
            case '"': tmp[0] = '"'; n = 1; ps->p++; break;
            case '\\': tmp[0] = '\\'; n = 1; ps->p++; break;
            case '/': tmp[0] = '/'; n = 1; ps->p++; break;
            case 'b': tmp[0] = '\b'; n = 1; ps->p++; break;
            case 'f': tmp[0] = '\f'; n = 1; ps->p++; break;
            case 'n': tmp[0] = '\n'; n = 1; ps->p++; break;
            case 'r': tmp[0] = '\r'; n = 1; ps->p++; break;
            case 't': tmp[0] = '\t'; n = 1; ps->p++; break;
            case 'u': {
                unsigned long cp, lo;
                if (!hex4(ps->p + 1, &cp)) {
                    set_err(ps, "bad unicode escape");
                    free(buf);
                    return NULL;
                }
                ps->p += 5;
                if (cp >= 0xD800 && cp <= 0xDBFF && ps->p[0] == '\\' &&
                    ps->p[1] == 'u' && hex4(ps->p + 2, &lo) &&
                    lo >= 0xDC00 && lo <= 0xDFFF) {
                    cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
                    ps->p += 6;
                }
                n = utf8_encode(cp, tmp);
                break;
            }
            default:
                set_err(ps, "bad escape");
                free(buf);
                return NULL;
            }
        } else {
            tmp[0] = *ps->p++;
            n = 1;
        }
        if (len + (size_t)n + 1 > cap) {
            cap *= 2;
            buf = realloc(buf, cap);
            if (!buf)
                abort();
        }
        memcpy(buf + len, tmp, (size_t)n);
        len += (size_t)n;
    }
    if (*ps->p != '"') {
        set_err(ps, "unterminated string");
        free(buf);
        return NULL;
    }
    ps->p++;
    buf[len] = '\0';
    return buf;
}

static qj_value *parse_object(qj_parser *ps)
{
    qj_value *v = new_value(QJ_OBJ);
    ps->p++;
    skip_ws(ps);
    if (*ps->p == '}') {
        ps->p++;
        return v;
    }
    for (;;) {
        char *key;
        qj_value *item;
        skip_ws(ps);
        key = parse_string_raw(ps);
        if (!key) {
            qj_free(v);
            return NULL;
        }
        skip_ws(ps);
        if (*ps->p != ':') {
            set_err(ps, "expected ':'");
            free(key);
            qj_free(v);
            return NULL;
        }
        ps->p++;
        item = parse_value(ps);
        if (!item) {
            free(key);
            qj_free(v);
            return NULL;
        }
        push_item(v, key, item);
        skip_ws(ps);
        if (*ps->p == ',') {
            ps->p++;
            continue;
        }
        if (*ps->p == '}') {
            ps->p++;
            return v;
        }
        set_err(ps, "expected ',' or '}'");
        qj_free(v);
        return NULL;
    }
}

static qj_value *parse_array(qj_parser *ps)
{
    qj_value *v = new_value(QJ_ARR);
    ps->p++;
    skip_ws(ps);
    if (*ps->p == ']') {
        ps->p++;
        return v;
    }
    for (;;) {
        qj_value *item = parse_value(ps);
        if (!item) {
            qj_free(v);
            return NULL;
        }
        push_item(v, NULL, item);
        skip_ws(ps);
        if (*ps->p == ',') {
            ps->p++;
            continue;
        }
        if (*ps->p == ']') {
            ps->p++;
            return v;
        }
        set_err(ps, "expected ',' or ']'");
        qj_free(v);
        return NULL;
    }
}

static qj_value *parse_value(qj_parser *ps)
{
    qj_value *v;
    if (++ps->depth > 64) {
        set_err(ps, "nesting too deep");
        return NULL;
    }
    skip_ws(ps);
    switch (*ps->p) {
    case '{':
        v = parse_object(ps);
        break;
    case '[':
        v = parse_array(ps);
        break;
    case '"': {
        char *s = parse_string_raw(ps);
        if (!s)
            return NULL;
        v = new_value(QJ_STR);
        v->str = s;
        break;
    }
    case 't':
        if (strncmp(ps->p, "true", 4) != 0) {
            set_err(ps, "bad literal");
            return NULL;
        }
        ps->p += 4;
        v = new_value(QJ_BOOL);
        v->boolean = 1;
        break;
    case 'f':
        if (strncmp(ps->p, "false", 5) != 0) {
            set_err(ps, "bad literal");
            return NULL;
        }
        ps->p += 5;
        v = new_value(QJ_BOOL);
        break;
    case 'n':
        if (strncmp(ps->p, "null", 4) != 0) {
            set_err(ps, "bad literal");
            return NULL;
        }
        ps->p += 4;
        v = new_value(QJ_NULL);
        break;
    default: {
        char *end;
        double d = strtod(ps->p, &end);
        if (end == ps->p) {
            set_err(ps, "unexpected token");
            return NULL;
        }
        ps->p = end;
        v = new_value(QJ_NUM);
        v->num = d;
        break;
    }
    }
    ps->depth--;
    return v;
}

qj_value *qj_parse(const char *text, char *errbuf, size_t errlen)
{
    qj_parser ps;
    qj_value *v;
    ps.p = text;
    ps.errbuf = errbuf;
    ps.errlen = errlen;
    ps.depth = 0;
    if (errbuf && errlen)
        errbuf[0] = '\0';
    v = parse_value(&ps);
    if (!v)
        return NULL;
    skip_ws(&ps);
    if (*ps.p != '\0') {
        set_err(&ps, "trailing data");
        qj_free(v);
        return NULL;
    }
    return v;
}

qj_type_t qj_type(const qj_value *v)
{
    return v->type;
}

int qj_bool(const qj_value *v)
{
    return v->boolean;
}

double qj_num(const qj_value *v)
{
    return v->num;
}

const char *qj_str(const qj_value *v)
{
    return v->str;
}

size_t qj_len(const qj_value *v)
{
    if (v->type != QJ_ARR && v->type != QJ_OBJ)
        return 0;
    return v->len;
}

qj_value *qj_at(const qj_value *v, size_t i)
{
    if (i >= v->len)
        return NULL;
    return v->items[i];
}

const char *qj_key(const qj_value *v, size_t i)
{
    if (v->type != QJ_OBJ || i >= v->len)
        return NULL;
    return v->keys[i];
}

qj_value *qj_get(const qj_value *v, const char *key)
{
    size_t i;
    if (v->type != QJ_OBJ)
        return NULL;
    for (i = 0; i < v->len; i++)
        if (strcmp(v->keys[i], key) == 0)
            return v->items[i];
    return NULL;
}
