#ifndef RISK_FOLD_H
#define RISK_FOLD_H

#include <stddef.h>

#include "common.h"
#include "qjson.h"

/* Assigns each matched record to a vulnerability group. group_of[i] gets the
 * group's root record index; canonical receives one reporting id per group,
 * in ascending root index order. Returns the number of groups. */
size_t vuln_fold(const qj_value *records, int *group_of, strlist *canonical);

#endif
