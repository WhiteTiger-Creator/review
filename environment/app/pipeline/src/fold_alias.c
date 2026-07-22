#include "fold.h"

#include <string.h>

static int keys_shared(const qj_value *a, const qj_value *b)
{
    const qj_value *aa = qj_get(a, "aliases");
    const qj_value *ab = qj_get(b, "aliases");
    const char *ida = qj_str(qj_get(a, "id"));
    const char *idb = qj_str(qj_get(b, "id"));
    size_t i, j;
    if (strcmp(ida, idb) == 0)
        return 1;
    for (i = 0; i < qj_len(ab); i++)
        if (strcmp(ida, qj_str(qj_at(ab, i))) == 0)
            return 1;
    for (i = 0; i < qj_len(aa); i++) {
        const char *k = qj_str(qj_at(aa, i));
        if (strcmp(k, idb) == 0)
            return 1;
        for (j = 0; j < qj_len(ab); j++)
            if (strcmp(k, qj_str(qj_at(ab, j))) == 0)
                return 1;
    }
    return 0;
}

static int find_root(int *parent, int x)
{
    while (parent[x] != x)
        x = parent[x] = parent[parent[x]];
    return x;
}

static int is_pysec(const char *id)
{
    return strncmp(id, "PYSEC-", 6) == 0;
}

size_t vuln_fold(const qj_value *records, int *group_of, strlist *canonical)
{
    size_t n = qj_len(records);
    int parent[256];
    size_t i, j;
    size_t ngroups = 0;

    if (n > 256)
        die("too many records in one group fold");
    for (i = 0; i < n; i++)
        parent[i] = (int)i;
    for (i = 0; i < n; i++)
        for (j = i + 1; j < n; j++)
            if (keys_shared(qj_at(records, i), qj_at(records, j))) {
                int ra = find_root(parent, (int)i);
                int rb = find_root(parent, (int)j);
                if (ra != rb)
                    parent[rb] = ra;
            }
    for (i = 0; i < n; i++)
        group_of[i] = find_root(parent, (int)i);

    for (i = 0; i < n; i++) {
        const char *canon = NULL;
        int has_py = 0;
        if (group_of[i] != (int)i)
            continue;
        ngroups++;
        for (j = 0; j < n; j++) {
            const char *id;
            if (group_of[j] != (int)i)
                continue;
            id = qj_str(qj_get(qj_at(records, j), "id"));
            if (is_pysec(id)) {
                if (!has_py || strcmp(id, canon) < 0)
                    canon = id;
                has_py = 1;
            } else if (!has_py && (!canon || strcmp(id, canon) < 0)) {
                canon = id;
            }
        }
        strlist_push(canonical, canon);
    }
    return ngroups;
}
