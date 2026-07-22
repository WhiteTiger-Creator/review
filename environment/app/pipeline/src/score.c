#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "common.h"
#include "cvss.h"
#include "fold.h"
#include "order.h"
#include "qjson.h"
#include "report_row.h"
#include "sevagg.h"
#include <severity_table.h>

#ifndef RISK_SCHEMA_VERSION
#error "RISK_SCHEMA_VERSION must be defined by the build"
#endif

static double record_score(const qj_value *rec)
{
    const qj_value *vector = qj_get(rec, "vector");
    const qj_value *label = qj_get(rec, "label");
    if (vector)
        return cvss31_base(qj_str(vector));
    if (label) {
        const char *l = qj_str(label);
        if (strcmp(l, "CRITICAL") == 0)
            return SEV_LABEL_CRITICAL / 10.0;
        if (strcmp(l, "HIGH") == 0)
            return SEV_LABEL_HIGH / 10.0;
        if (strcmp(l, "MODERATE") == 0)
            return SEV_LABEL_MODERATE / 10.0;
        if (strcmp(l, "LOW") == 0)
            return SEV_LABEL_LOW / 10.0;
        die("unknown severity label %s", l);
    }
    return 0.0;
}

static void build_row(row_t *row, const qj_value *pkg)
{
    const qj_value *records = qj_get(pkg, "records");
    size_t n = qj_len(records);
    double *scores = xmalloc(n * sizeof(*scores));
    const char **ids = xmalloc(n * sizeof(*ids));
    int *group_of = xmalloc(n * sizeof(*group_of));
    double gscores[256];
    const char *gids[256];
    size_t i, j, ngroups;
    double max_sev = 0.0;

    row->name = xstrdup(qj_str(qj_get(pkg, "name")));
    row->version = xstrdup(qj_str(qj_get(pkg, "version")));
    row->pages = (long)qj_num(qj_get(pkg, "pages"));
    memset(&row->advisories, 0, sizeof(row->advisories));

    for (i = 0; i < n; i++) {
        scores[i] = record_score(qj_at(records, i));
        ids[i] = qj_str(qj_get(qj_at(records, i), "id"));
    }
    ngroups = vuln_fold(records, group_of, &row->advisories);
    strlist_sort(&row->advisories);
    row->count = (long)ngroups;

    for (i = 0; i < n; i++) {
        size_t members = 0;
        double gsev;
        if (group_of[i] != (int)i)
            continue;
        for (j = 0; j < n; j++) {
            if (group_of[j] != (int)i)
                continue;
            if (members >= 256)
                die("group too large");
            gscores[members] = scores[j];
            gids[members] = ids[j];
            members++;
        }
        gsev = sev_aggregate(gscores, gids, members);
        if (gsev > max_sev)
            max_sev = gsev;
    }

    row->sev_t = lround(max_sev * 10.0);
    row->risk_t = row->sev_t + COEFF_EXTRA_GROUP * (row->count - 1) +
                  COEFF_PAGE * row->pages;
    if (row->risk_t > RISK_CAP)
        row->risk_t = RISK_CAP;
    free(scores);
    free(ids);
    free(group_of);
}

int main(int argc, char **argv)
{
    char *text, err[128];
    qj_value *root;
    const qj_value *pkgs;
    row_t *rows;
    size_t i, j, n;
    FILE *out;

    if (argc != 3) {
        fprintf(stderr, "usage: score <matches-json> <out-json>\n");
        return 2;
    }
    text = read_file(argv[1]);
    root = qj_parse(text, err, sizeof(err));
    if (!root)
        die("invalid matches file %s: %s", argv[1], err);
    free(text);
    pkgs = qj_get(root, "packages");
    if (!pkgs || qj_type(pkgs) != QJ_ARR)
        die("matches file %s has no packages array", argv[1]);
    n = qj_len(pkgs);
    rows = xmalloc((n ? n : 1) * sizeof(*rows));
    for (i = 0; i < n; i++)
        build_row(&rows[i], qj_at(pkgs, i));
    qsort(rows, n, sizeof(*rows), order_cmp);

    out = fopen(argv[2], "w");
    if (!out)
        die("cannot write %s", argv[2]);
    fprintf(out, "{\n  \"schema_version\": \"%s\",\n  \"packages\": [",
            RISK_SCHEMA_VERSION);
    for (i = 0; i < n; i++) {
        char esc[512];
        json_escape(rows[i].name, esc, sizeof(esc));
        fprintf(out, "%s\n    {\n      \"name\": \"%s\",\n",
                i ? "," : "", esc);
        json_escape(rows[i].version, esc, sizeof(esc));
        fprintf(out, "      \"assessed_version\": \"%s\",\n", esc);
        fprintf(out, "      \"pages_referenced\": %ld,\n", rows[i].pages);
        fprintf(out, "      \"advisory_count\": %ld,\n", rows[i].count);
        fprintf(out, "      \"max_severity\": %ld.%ld,\n",
                rows[i].sev_t / 10, rows[i].sev_t % 10);
        fprintf(out, "      \"risk_score\": %ld.%ld,\n",
                rows[i].risk_t / 10, rows[i].risk_t % 10);
        fprintf(out, "      \"advisories\": [");
        for (j = 0; j < rows[i].advisories.len; j++) {
            json_escape(rows[i].advisories.items[j], esc, sizeof(esc));
            fprintf(out, "%s\"%s\"", j ? ", " : "", esc);
        }
        fprintf(out, "]\n    }");
    }
    fprintf(out, "\n  ]\n}\n");
    if (fclose(out) != 0)
        die("cannot finish %s", argv[2]);
    fprintf(stderr, "score: %zu packages ranked\n", n);
    return 0;
}
