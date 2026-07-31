#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "policy.h"

typedef const char *(*text_fn)(void);
typedef int (*int_fn)(void);

static int read_request(const char *path, char *buf, size_t size) {
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
    fclose(fp);
    buf[strcspn(buf, "\r\n")] = '\0';
    return buf[0] == '\0' ? -1 : 0;
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: ledger-gateway REQUEST_FILE\n");
        return 64;
    }

    char request[64];
    if (read_request(argv[1], request, sizeof(request)) != 0) {
        return 65;
    }

    void *handle = dlopen("libledger_policy.so.2", RTLD_NOW | RTLD_LOCAL);
    if (handle == NULL) {
        fprintf(stderr, "policy load failed: %s\n", dlerror());
        return 70;
    }

    dlerror();
    text_fn policy_name = (text_fn)dlsym(handle, "ledger_policy_name");
    text_fn rules_name = (text_fn)dlsym(handle, "ledger_policy_rules");
    int_fn generation = (int_fn)dlsym(handle, "ledger_policy_generation");
    const char *error = dlerror();
    if (error != NULL || policy_name == NULL || rules_name == NULL || generation == NULL) {
        fprintf(stderr, "policy interface failed: %s\n", error == NULL ? "missing symbol" : error);
        dlclose(handle);
        return 71;
    }

    printf("request=%s plugin=%s rules=%s generation=%d\n",
           request, policy_name(), rules_name(), generation());
    dlclose(handle);
    return 0;
}
