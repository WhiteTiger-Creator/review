#include "qr_composer.h"

#include <stdlib.h>
#include <string.h>

/* Plan stage: joint segmentation DP + version fixpoint per segmentation-dp.md.
 * Writes /app/state/plans.tsv and /app/state/segments.tsv. */

static const int GROUP_SIZE[3] = {3, 2, 1};
static const int FIRST_CHAR_BITS[3] = {4, 6, 8};
static const int INC_BITS[3][3] = {{4, 3, 3}, {6, 5, 0}, {8, 0, 0}};

static const char ALNUM_CHARSET[] = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:";

int qrt_alnum_index(int ch) {
    const char *hit = strchr(ALNUM_CHARSET, ch);
    if (!hit || ch == '\0') return -1;
    return (int)(hit - ALNUM_CHARSET);
}

int qrt_cci_width(int mode, int cci_class) {
    static const int width[3][2] = {{10, 12}, {9, 11}, {8, 16}};
    return width[mode][cci_class];
}

static int header_bits(int mode, int cci_class) { return 4 + qrt_cci_width(mode, cci_class); }

int qrt_segment_data_bits(int mode, int count) {
    if (mode == QRT_MODE_NUMERIC) {
        static const int tail[3] = {0, 4, 7};
        return 10 * (count / 3) + tail[count % 3];
    }
    if (mode == QRT_MODE_ALNUM) {
        static const int tail[2] = {0, 6};
        return 11 * (count / 2) + tail[count % 2];
    }
    return 8 * count;
}

static int char_mode_set(unsigned char ch) {
    int set = 0;
    if (ch >= '0' && ch <= '9') set |= 1 << QRT_MODE_NUMERIC;
    if (qrt_alnum_index(ch) >= 0) set |= 1 << QRT_MODE_ALNUM;
    set |= 1 << QRT_MODE_BYTE;
    return set;
}

typedef struct {
    long bits;
    int nsegs;
    signed char pm, pr;
    int used;
} dp_state;

/* dp[mode][r]: best (bits, nsegs) with parent pointer for reconstruction. */
static int run_dp(const char *text, int n, int cci_class, int *out_bits, int *out_nsegs,
                  qrt_segment *segs, int max_segs) {
    static dp_state hist[QRT_MAX_TEXT][3][3];
    memset(hist, 0, sizeof(dp_state) * (size_t)n * 9);

    int set0 = char_mode_set((unsigned char)text[0]);
    for (int m = 0; m < 3; m++) {
        if (!(set0 & (1 << m))) continue;
        int r = 1 % GROUP_SIZE[m];
        dp_state *st = &hist[0][m][r];
        long bits = header_bits(m, cci_class) + FIRST_CHAR_BITS[m];
        if (!st->used || bits < st->bits || (bits == st->bits && 1 < st->nsegs)) {
            st->used = 1;
            st->bits = bits;
            st->nsegs = 1;
            st->pm = -1;
            st->pr = -1;
        }
    }
    for (int i = 1; i < n; i++) {
        int set = char_mode_set((unsigned char)text[i]);
        for (int pm = 0; pm < 3; pm++) {
            for (int pr = 0; pr < 3; pr++) {
                dp_state *prev = &hist[i - 1][pm][pr];
                if (!prev->used) continue;
                for (int m = 0; m < 3; m++) {
                    if (!(set & (1 << m))) continue;
                    long nb;
                    int nr, nseg;
                    if (m == pm) {
                        nb = prev->bits + INC_BITS[m][pr];
                        nr = (pr + 1) % GROUP_SIZE[m];
                        nseg = prev->nsegs;
                    } else {
                        nb = prev->bits + header_bits(m, cci_class) + FIRST_CHAR_BITS[m];
                        nr = 1 % GROUP_SIZE[m];
                        nseg = prev->nsegs + 1;
                    }
                    dp_state *st = &hist[i][m][nr];
                    if (!st->used || nb < st->bits || (nb == st->bits && nseg < st->nsegs)) {
                        st->used = 1;
                        st->bits = nb;
                        st->nsegs = nseg;
                        st->pm = (signed char)pm;
                        st->pr = (signed char)pr;
                    }
                }
            }
        }
    }
    int bm = -1, br = -1;
    for (int m = 0; m < 3; m++) {
        for (int r = 0; r < 3; r++) {
            dp_state *st = &hist[n - 1][m][r];
            if (!st->used) continue;
            if (bm < 0 || st->bits < hist[n - 1][bm][br].bits ||
                (st->bits == hist[n - 1][bm][br].bits && st->nsegs < hist[n - 1][bm][br].nsegs)) {
                bm = m;
                br = r;
            }
        }
    }
    if (bm < 0) return -1;
    *out_bits = (int)hist[n - 1][bm][br].bits;
    *out_nsegs = hist[n - 1][bm][br].nsegs;

    static signed char per_char[QRT_MAX_TEXT];
    int m = bm, r = br;
    for (int i = n - 1; i >= 0; i--) {
        per_char[i] = (signed char)m;
        dp_state *st = &hist[i][m][r];
        if (st->pm < 0) break;
        int nm = st->pm, nr = st->pr;
        m = nm;
        r = nr;
    }
    int nsegs = 0;
    for (int i = 0; i < n; i++) {
        if (nsegs > 0 && segs[nsegs - 1].mode == per_char[i]) {
            segs[nsegs - 1].char_count++;
        } else {
            if (nsegs >= max_segs) return -1;
            segs[nsegs].mode = per_char[i];
            segs[nsegs].char_count = 1;
            segs[nsegs].bit_count = 0;
            nsegs++;
        }
    }
    for (int i = 0; i < nsegs; i++)
        segs[i].bit_count = header_bits(segs[i].mode, cci_class) +
                            qrt_segment_data_bits(segs[i].mode, segs[i].char_count);
    return nsegs;
}

int qrt_plan_symbol(const qrt_payload *p, qrt_plan *out) {
    int best_version = -1;
    static const int class_lo[2] = {1, 10};
    static const int class_hi[2] = {9, QRT_MAX_VERSION};
    for (int cls = 0; cls < 2; cls++) {
        qrt_segment segs[QRT_MAX_SEGMENTS];
        int bits, nsegs;
        int count = run_dp(p->text, p->text_len, cls, &bits, &nsegs, segs, QRT_MAX_SEGMENTS);
        if (count < 0) continue;
        for (int v = class_lo[cls]; v <= class_hi[cls]; v++) {
            if (qrt_data_capacity_bits(v, p->ecc_level) >= bits) {
                if (best_version < 0 || v < best_version) {
                    best_version = v;
                    out->version = v;
                    out->cci_class = cls;
                    out->total_bits = bits;
                    out->segment_count = count;
                    memcpy(out->segments, segs, sizeof(qrt_segment) * (size_t)count);
                }
                break;
            }
        }
    }
    if (best_version < 0) qrt_die("payload %s/%s exceeds version %d capacity", p->batch_id, p->payload_id, QRT_MAX_VERSION);
    return 0;
}

int qrt_cmd_plan(void) {
    static qrt_payload payloads[QRT_MAX_PAYLOADS];
    int count = qrt_load_payloads(payloads, QRT_MAX_PAYLOADS);

    size_t cap = (size_t)count * 256 + 64;
    size_t seg_cap = (size_t)count * QRT_MAX_SEGMENTS * 96 + 64;
    char *plans = malloc(cap);
    char *segments = malloc(seg_cap);
    if (!plans || !segments) qrt_die("out of memory");
    size_t poff = 0, soff = 0;
    for (int i = 0; i < count; i++) {
        qrt_plan plan;
        qrt_plan_symbol(&payloads[i], &plan);
        poff += (size_t)snprintf(plans + poff, cap - poff, "%s\t%s\t%c\t%d\t%d\t%d\t%d\n",
                                 payloads[i].batch_id, payloads[i].payload_id,
                                 payloads[i].ecc_level, plan.version, plan.cci_class,
                                 plan.total_bits, plan.segment_count);
        static const char *mode_names[3] = {"numeric", "alphanumeric", "byte"};
        for (int s = 0; s < plan.segment_count; s++) {
            soff += (size_t)snprintf(segments + soff, seg_cap - soff, "%s\t%s\t%d\t%s\t%d\t%d\n",
                                     payloads[i].batch_id, payloads[i].payload_id, s,
                                     mode_names[plan.segments[s].mode],
                                     plan.segments[s].char_count, plan.segments[s].bit_count);
        }
    }
    qrt_write_file(QRT_PLANS_TSV, plans, poff);
    qrt_write_file(QRT_SEGMENTS_TSV, segments, soff);
    free(plans);
    free(segments);
    printf("planned %d symbols\n", count);
    return 0;
}

int qrt_load_plan(const char *batch_id, const char *payload_id, qrt_plan *out) {
    size_t len = 0;
    char *data = qrt_read_file(QRT_PLANS_TSV, &len);
    if (!data) qrt_die("missing %s (run plan-symbols first)", QRT_PLANS_TSV);
    int found = 0;
    char *save = NULL;
    for (char *line = strtok_r(data, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        if (!line[0]) continue;
        char *fields[7];
        if (qrt_split_tsv(line, fields, 7) != 7) qrt_die("bad plans.tsv row");
        if (strcmp(fields[0], batch_id) != 0 || strcmp(fields[1], payload_id) != 0) continue;
        out->version = atoi(fields[3]);
        out->cci_class = atoi(fields[4]);
        out->total_bits = atoi(fields[5]);
        out->segment_count = atoi(fields[6]);
        found = 1;
        break;
    }
    free(data);
    if (!found) return -1;

    data = qrt_read_file(QRT_SEGMENTS_TSV, &len);
    if (!data) qrt_die("missing %s (run plan-symbols first)", QRT_SEGMENTS_TSV);
    int seg_seen = 0;
    save = NULL;
    for (char *line = strtok_r(data, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        if (!line[0]) continue;
        char *fields[6];
        if (qrt_split_tsv(line, fields, 6) != 6) qrt_die("bad segments.tsv row");
        if (strcmp(fields[0], batch_id) != 0 || strcmp(fields[1], payload_id) != 0) continue;
        int idx = atoi(fields[2]);
        if (idx < 0 || idx >= QRT_MAX_SEGMENTS) qrt_die("segment index out of range");
        int mode = -1;
        if (strcmp(fields[3], "numeric") == 0) mode = QRT_MODE_NUMERIC;
        else if (strcmp(fields[3], "alphanumeric") == 0) mode = QRT_MODE_ALNUM;
        else if (strcmp(fields[3], "byte") == 0) mode = QRT_MODE_BYTE;
        else qrt_die("unknown segment mode %s", fields[3]);
        out->segments[idx].mode = mode;
        out->segments[idx].char_count = atoi(fields[4]);
        out->segments[idx].bit_count = atoi(fields[5]);
        seg_seen++;
    }
    free(data);
    if (seg_seen != out->segment_count) qrt_die("segments.tsv row count mismatch for %s/%s", batch_id, payload_id);
    return 0;
}
