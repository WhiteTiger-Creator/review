#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

typedef const char *(*text_fn)(void);
typedef const char *(*decision_fn)(const char *);
typedef int (*int_fn)(void);

static int read_request(const char *path, char *buf, size_t size, long *pause_ms) {
    FILE *fp = fopen(path, "r");
    if (fp == NULL) {
        fprintf(stderr, "cannot open request %s: %s\n", path, strerror(errno));
        return -1;
    }
    if (fgets(buf, (int)size, fp) == NULL) {
        fprintf(stderr, "cannot read request %s\n", path);
        fclose(fp);
        return -1;
    }
    buf[strcspn(buf, "\r\n")] = '\0';
    if (buf[0] == '\0') {
        fclose(fp);
        return -1;
    }
    char option[64] = {0};
    if (fgets(option, sizeof(option), fp) != NULL) option[strcspn(option, "\r\n")] = '\0';
    fclose(fp);
    if (strcmp(buf, "drain") == 0) {
        char *end = NULL;
        errno = 0;
        if (strncmp(option, "pause_ms=", 9) != 0) return -1;
        *pause_ms = strtol(option + 9, &end, 10);
        if (errno != 0 || end == option + 9 || *end != '\0' || *pause_ms < 1 || *pause_ms > 5000) return -1;
    } else if (option[0] != '\0') {
        return -1;
    }
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: ledger-gateway REQUEST_FILE\n");
        return 64;
    }
    char request[64];
    long pause_ms = 0;
    if (read_request(argv[1], request, sizeof(request), &pause_ms) != 0) return 65;

    void *handle = dlopen("libledger_policy.so.2", RTLD_NOW | RTLD_LOCAL);
    if (handle == NULL) {
        fprintf(stderr, "policy load failed: %s\n", dlerror());
        return 70;
    }
    dlerror();
    text_fn policy_name = (text_fn)dlvsym(handle, "ledger_policy_name", "LEDGER_POLICY_2.1");
    text_fn rules_name = (text_fn)dlvsym(handle, "ledger_policy_rules", "LEDGER_POLICY_2.1");
    text_fn audit_name = (text_fn)dlvsym(handle, "ledger_policy_audit", "LEDGER_POLICY_2.1");
    text_fn abi_name = (text_fn)dlvsym(handle, "ledger_policy_abi", "LEDGER_POLICY_2.1");
    decision_fn decision = (decision_fn)dlvsym(handle, "ledger_policy_decision", "LEDGER_POLICY_2.1");
    int_fn generation = (int_fn)dlvsym(handle, "ledger_policy_generation", "LEDGER_POLICY_2.1");
    const char *error = dlerror();
    if (error != NULL || policy_name == NULL || rules_name == NULL || audit_name == NULL ||
        abi_name == NULL || decision == NULL || generation == NULL) {
        fprintf(stderr, "policy interface failed: %s\n", error == NULL ? "missing symbol" : error);
        dlclose(handle);
        return 71;
    }
    const char *route_decision = decision(request);
    int selected_generation = generation();
    if (route_decision == NULL || selected_generation < 0) {
        fprintf(stderr, "policy stack rejected request or contains mixed generations\n");
        dlclose(handle);
        return 72;
    }
    if (pause_ms > 0) {
        struct timespec delay = { .tv_sec = pause_ms / 1000, .tv_nsec = (pause_ms % 1000) * 1000000L };
        while (nanosleep(&delay, &delay) != 0 && errno == EINTR) {}
    }
    printf("request=%s plugin=%s rules=%s audit=%s generation=%d abi=%s decision=%s\n",
           request, policy_name(), rules_name(), audit_name(), selected_generation,
           abi_name(), route_decision);
    dlclose(handle);
    return 0;
}
