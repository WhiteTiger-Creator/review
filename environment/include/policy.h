#ifndef LEDGER_POLICY_H
#define LEDGER_POLICY_H
const char *ledger_policy_name(void);
const char *ledger_policy_rules(void);
const char *ledger_policy_audit(void);
const char *ledger_policy_abi(void);
const char *ledger_policy_decision(const char *request);
int ledger_policy_generation(void);
#endif
