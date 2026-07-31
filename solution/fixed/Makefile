CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -Werror -fPIC
BUILD_ID := -Wl,--build-id=sha1
BUILD := build

.PHONY: all clean
all: \
	$(BUILD)/ledger-gateway \
	$(BUILD)/libledger_rules.so.1.0 \
	$(BUILD)/libledger_rules.so.1.1 \
	$(BUILD)/libledger_audit.so.1.0 \
	$(BUILD)/libledger_audit.so.1.1 \
	$(BUILD)/libledger_policy.so.2.0 \
	$(BUILD)/libledger_policy.so.2.1

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/ledger-gateway: src/gateway.c | $(BUILD)
	$(CC) $(CFLAGS) $(BUILD_ID) -Iinclude -o $@ src/gateway.c -ldl

$(BUILD)/libledger_rules.so.1.0: src/rules_baseline.c include/rules.h maps/rules_v1.map | $(BUILD)
	$(CC) $(CFLAGS) $(BUILD_ID) -Iinclude -shared -Wl,-soname,libledger_rules.so.1 \
		-Wl,--version-script=maps/rules_v1.map -o $@ src/rules_baseline.c

$(BUILD)/libledger_rules.so.1.1: src/rules_v3.c include/rules.h maps/rules_v2.map | $(BUILD)
	$(CC) $(CFLAGS) $(BUILD_ID) -Iinclude -shared -Wl,-soname,libledger_rules.so.1 \
		-Wl,--version-script=maps/rules_v2.map -o $@ src/rules_v3.c

$(BUILD)/libledger_audit.so.1.0: src/audit_baseline.c include/audit.h maps/audit_v1.map | $(BUILD)
	$(CC) $(CFLAGS) $(BUILD_ID) -Iinclude -shared -Wl,-soname,libledger_audit.so.1 \
		-Wl,--version-script=maps/audit_v1.map -o $@ src/audit_baseline.c

$(BUILD)/libledger_audit.so.1.1: src/audit_v3.c include/audit.h maps/audit_v2.map | $(BUILD)
	$(CC) $(CFLAGS) $(BUILD_ID) -Iinclude -shared -Wl,-soname,libledger_audit.so.1 \
		-Wl,--version-script=maps/audit_v2.map -o $@ src/audit_v3.c

$(BUILD)/libledger_policy.so.2.0: src/policy_baseline.c include/policy.h include/rules.h include/audit.h maps/policy.map $(BUILD)/libledger_rules.so.1.0 $(BUILD)/libledger_audit.so.1.0 | $(BUILD)
	ln -sfn libledger_rules.so.1.0 $(BUILD)/libledger_rules.so
	ln -sfn libledger_audit.so.1.0 $(BUILD)/libledger_audit.so
	$(CC) $(CFLAGS) $(BUILD_ID) -Iinclude -shared -Wl,-soname,libledger_policy.so.2 \
		-Wl,--version-script=maps/policy.map -Wl,-rpath,'$$ORIGIN' \
		-L$(BUILD) -o $@ src/policy_baseline.c -lledger_rules -lledger_audit

$(BUILD)/libledger_policy.so.2.1: src/policy_v3.c include/policy.h include/rules.h include/audit.h maps/policy.map $(BUILD)/libledger_rules.so.1.1 $(BUILD)/libledger_audit.so.1.1 | $(BUILD)
	ln -sfn libledger_rules.so.1.1 $(BUILD)/libledger_rules.so
	ln -sfn libledger_audit.so.1.1 $(BUILD)/libledger_audit.so
	$(CC) $(CFLAGS) $(BUILD_ID) -Iinclude -shared -Wl,-soname,libledger_policy.so.2 \
		-Wl,--version-script=maps/policy.map -Wl,-rpath,'$$ORIGIN' \
		-L$(BUILD) -o $@ src/policy_v3.c -lledger_rules -lledger_audit

clean:
	rm -rf $(BUILD)
