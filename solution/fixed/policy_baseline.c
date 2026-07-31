#include <string.h>
#include "audit.h"
#include "policy.h"
#include "rules.h"

static int valid_stack(void) {
    return ledger_rule_generation() == 2 && ledger_audit_generation() == 2;
}
const char *ledger_policy_name(void) { return "baseline"; }
const char *ledger_policy_rules(void) { return ledger_rule_profile(); }
const char *ledger_policy_audit(void) { return ledger_audit_profile(); }
const char *ledger_policy_abi(void) { return "LEDGER_2.1"; }
int ledger_policy_generation(void) { return valid_stack() ? 2 : -1; }
const char *ledger_policy_decision(const char *request) {
    if (!valid_stack()) return NULL;
    if (strcmp(request, "settlement") == 0) return "accept";
    if (strcmp(request, "refund") == 0) return "review";
    if (strcmp(request, "reconcile") == 0) return "hold";
    if (strcmp(request, "drain") == 0) return "quiesce";
    return NULL;
}
