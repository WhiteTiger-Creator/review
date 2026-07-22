#ifndef RISK_REPORT_ROW_H
#define RISK_REPORT_ROW_H

#include "common.h"

typedef struct {
    char *name;
    char *version;
    long pages;
    long count;
    long sev_t;
    long risk_t;
    strlist advisories;
} row_t;

#endif
