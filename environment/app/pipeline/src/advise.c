#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "common.h"
#include "qjson.h"
#include <vercmp.h>

typedef struct {
    char *fname;
    qj_value *root;
} record_t;

static record_t *records;
static size_t nrecords;

static void load_mirror(const char *dir)
{
    strlist files = {0};
    size_t i;
    if (list_dir_sorted(dir, ".json", &files) != 0)
        die("cannot read advisory mirror %s", dir);
    if (files.len == 0)
        die("no advisory records in %s", dir);
    records = xmalloc(files.len * sizeof(*records));
    for (i = 0; i < files.len; i++) {
        char path[4096], err[128];
        char *text;
        snprintf(path, sizeof(path), "%s/%s", dir, files.items[i]);
        text = read_file(path);
        records[i].fname = xstrdup(files.items[i]);
        records[i].root = qj_parse(text, err, sizeof(err));
        if (!records[i].root)
            die("invalid OSV record %s: %s", path, err);
        free(text);
        nrecords++;
    }
    strlist_free(&files);
}

static int range_matches(const qj_value *rng, const char *version)
{
    const char *intro = NULL, *fixed = NULL, *last = NULL;
    const qj_value *events = qj_get(rng, "events");
    size_t i;
    if (!events || qj_type(events) != QJ_ARR)
        return 0;
    for (i = 0; i < qj_len(events); i++) {
        const qj_value *ev = qj_at(events, i);
        const qj_value *f;
        if ((f = qj_get(ev, "introduced")) != NULL)
            intro = qj_str(f);
        if ((f = qj_get(ev, "fixed")) != NULL)
            fixed = qj_str(f);
        if ((f = qj_get(ev, "last_affected")) != NULL)
            last = qj_str(f);
    }
    if (!intro)
        return 0;
    if (strcmp(intro, "0") != 0 && vercmp(version, intro) < 0)
        return 0;
    if (fixed && vercmp(version, fixed) >= 0)
        return 0;
    if (last && vercmp(version, last) > 0)
        return 0;
    return 1;
}

static int record_matches(const qj_value *root, const char *name,
                          const char *version)
{
    const qj_value *affected;
    size_t i, j;
    if (qj_get(root, "withdrawn"))
        return 0;
    affected = qj_get(root, "affected");
    if (!affected || qj_type(affected) != QJ_ARR)
        return 0;
    for (i = 0; i < qj_len(affected); i++) {
        const qj_value *aff = qj_at(affected, i);
        const qj_value *pkg = qj_get(aff, "package");
        const qj_value *eco, *pname, *versions, *ranges;
        if (!pkg)
            continue;
        eco = qj_get(pkg, "ecosystem");
        pname = qj_get(pkg, "name");
        if (!eco || !pname || strcmp(qj_str(eco), "PyPI") != 0 ||
            strcmp(qj_str(pname), name) != 0)
            continue;
        versions = qj_get(aff, "versions");
        if (versions && qj_type(versions) == QJ_ARR) {
            for (j = 0; j < qj_len(versions); j++)
                if (strcmp(qj_str(qj_at(versions, j)), version) == 0)
                    return 1;
            continue;
        }
        ranges = qj_get(aff, "ranges");
        if (!ranges || qj_type(ranges) != QJ_ARR)
            continue;
        for (j = 0; j < qj_len(ranges); j++)
            if (range_matches(qj_at(ranges, j), version))
                return 1;
    }
    return 0;
}

static void emit_record(FILE *out, const qj_value *root, int first)
{
    const qj_value *aliases = qj_get(root, "aliases");
    const qj_value *sev = qj_get(root, "severity");
    const qj_value *dbs = qj_get(root, "database_specific");
    char esc[512];
    size_t i;

    fprintf(out, "%s        {", first ? "" : ",\n");
    json_escape(qj_str(qj_get(root, "id")), esc, sizeof(esc));
    fprintf(out, "\"id\": \"%s\", \"aliases\": [", esc);
    if (aliases && qj_type(aliases) == QJ_ARR) {
        for (i = 0; i < qj_len(aliases); i++) {
            json_escape(qj_str(qj_at(aliases, i)), esc, sizeof(esc));
            fprintf(out, "%s\"%s\"", i ? ", " : "", esc);
        }
    }
    fprintf(out, "]");
    if (sev && qj_type(sev) == QJ_ARR) {
        for (i = 0; i < qj_len(sev); i++) {
            const qj_value *entry = qj_at(sev, i);
            const qj_value *type = qj_get(entry, "type");
            const qj_value *score = qj_get(entry, "score");
            if (type && score && strcmp(qj_str(type), "CVSS_V3") == 0) {
                json_escape(qj_str(score), esc, sizeof(esc));
                fprintf(out, ", \"vector\": \"%s\"", esc);
                break;
            }
        }
    }
    if (dbs) {
        const qj_value *label = qj_get(dbs, "severity");
        if (label && qj_type(label) == QJ_STR) {
            json_escape(qj_str(label), esc, sizeof(esc));
            fprintf(out, ", \"label\": \"%s\"", esc);
        }
    }
    fprintf(out, "}");
}

int main(int argc, char **argv)
{
    char *tsv, *line, *next;
    FILE *out;
    int first_pkg = 1;

    if (argc != 4) {
        fprintf(stderr, "usage: advise <packages-tsv> <mirror-dir> <out-json>\n");
        return 2;
    }
    tsv = read_file(argv[1]);
    load_mirror(argv[2]);
    out = fopen(argv[3], "w");
    if (!out)
        die("cannot write %s", argv[3]);
    fprintf(out, "{\n    \"packages\": [");
    for (line = tsv; line && *line; line = next) {
        char *nl = strchr(line, '\n');
        char *name, *version, *pages, *tab1, *tab2;
        size_t i;
        int any = 0;
        if (nl) {
            *nl = '\0';
            next = nl + 1;
        } else {
            next = NULL;
        }
        tab1 = strchr(line, '\t');
        tab2 = tab1 ? strchr(tab1 + 1, '\t') : NULL;
        if (!tab1 || !tab2)
            die("malformed package line: %s", line);
        *tab1 = '\0';
        *tab2 = '\0';
        name = line;
        version = tab1 + 1;
        pages = tab2 + 1;
        for (i = 0; i < nrecords; i++) {
            if (!record_matches(records[i].root, name, version))
                continue;
            if (!any) {
                char esc[512];
                json_escape(name, esc, sizeof(esc));
                fprintf(out, "%s\n      {", first_pkg ? "" : ",");
                fprintf(out, "\"name\": \"%s\", ", esc);
                json_escape(version, esc, sizeof(esc));
                fprintf(out, "\"version\": \"%s\", \"pages\": %s, ", esc,
                        pages);
                fprintf(out, "\"records\": [\n");
                first_pkg = 0;
                any = 1;
            }
            emit_record(out, records[i].root, any == 1);
            any = 2;
        }
        if (any)
            fprintf(out, "\n      ]}");
    }
    fprintf(out, "\n    ]\n}\n");
    if (fclose(out) != 0)
        die("cannot finish %s", argv[3]);
    free(tsv);
    return 0;
}
