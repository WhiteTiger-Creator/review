#include "policy.h"
#include "rules.h"
const char *ledger_policy_name(void) { return "x86-64-v3"; }
const char *ledger_policy_rules(void) { return ledger_rule_profile(); }
int ledger_policy_generation(void) { return ledger_rule_generation(); }
