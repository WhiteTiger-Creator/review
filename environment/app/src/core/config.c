#include "qr_composer.h"

#include <stdlib.h>
#include <string.h>

/* Minimal TOML-subset reader for /app/config/composer.toml.
 * Recognised keys: inbox_dir (string), module_scale (int), quiet_modules (int). */

static int find_key(const char *text, const char *key, char *out, size_t cap) {
    const char *p = text;
    size_t klen = strlen(key);
    while ((p = strstr(p, key)) != NULL) {
        const char *line_start = p;
        while (line_start > text && line_start[-1] != '\n') line_start--;
        if (line_start[0] == '#') {
            p += klen;
            continue;
        }
        const char *eq = p + klen;
        while (*eq == ' ' || *eq == '\t') eq++;
        if (*eq != '=') {
            p += klen;
            continue;
        }
        eq++;
        while (*eq == ' ' || *eq == '\t') eq++;
        size_t n = 0;
        if (*eq == '"') {
            eq++;
            while (*eq && *eq != '"' && n + 1 < cap) out[n++] = *eq++;
        } else {
            while (*eq && *eq != '\n' && *eq != '\r' && *eq != '#' && n + 1 < cap) out[n++] = *eq++;
            while (n > 0 && (out[n - 1] == ' ' || out[n - 1] == '\t')) n--;
        }
        out[n] = '\0';
        return 1;
    }
    return 0;
}

static char *load_config(void) {
    static char *cached = NULL;
    static int loaded = 0;
    if (!loaded) {
        cached = qrt_read_file(QRT_CONFIG_PATH, NULL);
        loaded = 1;
    }
    return cached;
}

void qrt_config_inbox(char *out, size_t cap) {
    const char *env = getenv("TB3_SHIPBATCH_INBOX");
    if (env && env[0]) {
        if (env[0] != '/') qrt_die("TB3_SHIPBATCH_INBOX must be an absolute path");
        snprintf(out, cap, "%s", env);
        return;
    }
    char *cfg = load_config();
    if (cfg && find_key(cfg, "inbox_dir", out, cap)) return;
    snprintf(out, cap, "/app/fixtures/shipbatch-inbox");
}

int qrt_config_module_scale(void) {
    char buf[32];
    char *cfg = load_config();
    if (cfg && find_key(cfg, "module_scale", buf, sizeof(buf))) return atoi(buf);
    return 8;
}

int qrt_config_quiet_modules(void) {
    char buf[32];
    char *cfg = load_config();
    if (cfg && find_key(cfg, "quiet_modules", buf, sizeof(buf))) return atoi(buf);
    return 4;
}
