#include "qr_composer.h"

#include <dirent.h>
#include <stdlib.h>
#include <string.h>

/* Ingest stage: read every *.shipbatch.json batch from the inbox and persist
 * the payload staging table /app/state/payloads.tsv per staging-schema.md.
 * Rows are sorted by (batch_id, payload_id); text is hex-encoded. */

typedef struct {
    char batch_id[QRT_MAX_ID];
    char payload_id[QRT_MAX_ID];
    char ecc_level;
    char text[QRT_MAX_TEXT];
} row_t;

static int cmp_rows(const void *a, const void *b) {
    const row_t *ra = a;
    const row_t *rb = b;
    int c = strcmp(ra->batch_id, rb->batch_id);
    if (c) return c;
    return strcmp(ra->payload_id, rb->payload_id);
}

static const char *skip_ws(const char *p) {
    while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') p++;
    return p;
}

static const char *parse_string(const char *p, char *out, size_t cap) {
    p = skip_ws(p);
    if (*p != '"') qrt_die("shipbatch parse error: expected string near: %.16s", p);
    p++;
    size_t n = 0;
    while (*p && *p != '"') {
        if (n + 1 >= cap) qrt_die("shipbatch string too long");
        out[n++] = *p++;
    }
    if (*p != '"') qrt_die("shipbatch parse error: unterminated string");
    out[n] = '\0';
    return p + 1;
}

static const char *expect_key(const char *p, const char *key) {
    char buf[QRT_MAX_ID];
    p = parse_string(p, buf, sizeof(buf));
    if (strcmp(buf, key) != 0) qrt_die("shipbatch parse error: expected key %s got %s", key, buf);
    p = skip_ws(p);
    if (*p != ':') qrt_die("shipbatch parse error: expected ':' after %s", key);
    return p + 1;
}

static int parse_batch(const char *text, row_t *rows, int max, int count) {
    char batch_id[QRT_MAX_ID];
    const char *p = skip_ws(text);
    if (*p != '{') qrt_die("shipbatch parse error: expected object");
    p++;
    p = expect_key(p, "batch_id");
    p = parse_string(p, batch_id, sizeof(batch_id));
    p = skip_ws(p);
    if (*p != ',') qrt_die("shipbatch parse error: expected ',' after batch_id");
    p = expect_key(p + 1, "payloads");
    p = skip_ws(p);
    if (*p != '[') qrt_die("shipbatch parse error: expected payload array");
    p++;
    for (;;) {
        p = skip_ws(p);
        if (*p == ']') break;
        if (*p != '{') qrt_die("shipbatch parse error: expected payload object");
        p++;
        if (count >= max) qrt_die("too many payloads (max %d)", max);
        row_t *r = &rows[count];
        snprintf(r->batch_id, sizeof(r->batch_id), "%s", batch_id);
        p = expect_key(p, "payload_id");
        p = parse_string(p, r->payload_id, sizeof(r->payload_id));
        p = skip_ws(p);
        if (*p != ',') qrt_die("shipbatch parse error: expected ',' after payload_id");
        char level[8];
        p = expect_key(p + 1, "ecc_level");
        p = parse_string(p, level, sizeof(level));
        if (strlen(level) != 1 || qrt_ecc_index(level[0]) < 0)
            qrt_die("shipbatch parse error: bad ecc_level %s", level);
        r->ecc_level = level[0];
        p = skip_ws(p);
        if (*p != ',') qrt_die("shipbatch parse error: expected ',' after ecc_level");
        p = expect_key(p + 1, "text");
        p = parse_string(p, r->text, sizeof(r->text));
        if (r->text[0] == '\0') qrt_die("shipbatch parse error: empty text for %s", r->payload_id);
        count++;
        p = skip_ws(p);
        if (*p != '}') qrt_die("shipbatch parse error: expected '}' closing payload");
        p = skip_ws(p + 1);
        if (*p == ',') p++;
    }
    return count;
}

int qrt_cmd_ingest(void) {
    char inbox[512];
    qrt_config_inbox(inbox, sizeof(inbox));
    DIR *dir = opendir(inbox);
    if (!dir) qrt_die("cannot open inbox %s", inbox);

    char names[QRT_MAX_PAYLOADS][256];
    int nfiles = 0;
    struct dirent *ent;
    while ((ent = readdir(dir)) != NULL) {
        const char *dot = strstr(ent->d_name, ".shipbatch.json");
        if (!dot || strcmp(dot, ".shipbatch.json") != 0) continue;
        if (nfiles >= QRT_MAX_PAYLOADS) qrt_die("too many batch files");
        snprintf(names[nfiles++], sizeof(names[0]), "%s", ent->d_name);
    }
    closedir(dir);
    if (nfiles == 0) qrt_die("no shipbatch files found in %s", inbox);
    for (int i = 0; i < nfiles; i++)
        for (int j = i + 1; j < nfiles; j++)
            if (strcmp(names[j], names[i]) < 0) {
                char tmp[256];
                memcpy(tmp, names[i], sizeof(tmp));
                memcpy(names[i], names[j], sizeof(tmp));
                memcpy(names[j], tmp, sizeof(tmp));
            }

    static row_t rows[QRT_MAX_PAYLOADS];
    int count = 0;
    for (int i = 0; i < nfiles; i++) {
        char path[800];
        snprintf(path, sizeof(path), "%s/%s", inbox, names[i]);
        char *text = qrt_read_file(path, NULL);
        if (!text) qrt_die("cannot read %s", path);
        count = parse_batch(text, rows, QRT_MAX_PAYLOADS, count);
        free(text);
    }
    qsort(rows, (size_t)count, sizeof(row_t), cmp_rows);

    size_t cap = (size_t)count * (QRT_MAX_TEXT * 2 + 160) + 64;
    char *out = malloc(cap);
    if (!out) qrt_die("out of memory");
    size_t off = 0;
    for (int i = 0; i < count; i++) {
        char hex[QRT_MAX_TEXT * 2 + 1];
        qrt_hex_encode((const uint8_t *)rows[i].text, (int)strlen(rows[i].text), hex);
        off += (size_t)snprintf(out + off, cap - off, "%s\t%s\t%c\t%s\n",
                                rows[i].batch_id, rows[i].payload_id, rows[i].ecc_level, hex);
    }
    qrt_ensure_dir(QRT_STATE_DIR);
    qrt_write_file(QRT_PAYLOADS_TSV, out, off);
    free(out);
    printf("ingested %d payloads from %d batches\n", count, nfiles);
    return 0;
}

int qrt_load_payloads(qrt_payload *out, int max) {
    size_t len = 0;
    char *data = qrt_read_file(QRT_PAYLOADS_TSV, &len);
    if (!data) qrt_die("missing %s (run ingest-shipbatches first)", QRT_PAYLOADS_TSV);
    int count = 0;
    char *save = NULL;
    for (char *line = strtok_r(data, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        if (!line[0]) continue;
        if (count >= max) qrt_die("too many payload rows");
        char *fields[4];
        if (qrt_split_tsv(line, fields, 4) != 4) qrt_die("bad payloads.tsv row");
        qrt_payload *p = &out[count];
        snprintf(p->batch_id, sizeof(p->batch_id), "%s", fields[0]);
        snprintf(p->payload_id, sizeof(p->payload_id), "%s", fields[1]);
        p->ecc_level = fields[2][0];
        int n = qrt_hex_decode(fields[3], (uint8_t *)p->text, QRT_MAX_TEXT - 1);
        if (n < 0) qrt_die("bad payload text hex");
        p->text[n] = '\0';
        p->text_len = n;
        count++;
    }
    free(data);
    return count;
}
