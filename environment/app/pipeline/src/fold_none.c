#include "fold.h"

size_t vuln_fold(const qj_value *records, int *group_of, strlist *canonical)
{
    size_t n = qj_len(records);
    size_t i;
    for (i = 0; i < n; i++) {
        group_of[i] = (int)i;
        strlist_push(canonical, qj_str(qj_get(qj_at(records, i), "id")));
    }
    return n;
}
