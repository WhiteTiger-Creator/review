#ifndef QJSON_H
#define QJSON_H

#include <stddef.h>

typedef enum {
    QJ_NULL,
    QJ_BOOL,
    QJ_NUM,
    QJ_STR,
    QJ_ARR,
    QJ_OBJ
} qj_type_t;

typedef struct qj_value qj_value;

qj_value *qj_parse(const char *text, char *errbuf, size_t errlen);
void qj_free(qj_value *v);

qj_type_t qj_type(const qj_value *v);
int qj_bool(const qj_value *v);
double qj_num(const qj_value *v);
const char *qj_str(const qj_value *v);

size_t qj_len(const qj_value *v);
qj_value *qj_at(const qj_value *v, size_t i);
const char *qj_key(const qj_value *v, size_t i);
qj_value *qj_get(const qj_value *v, const char *key);

#endif
