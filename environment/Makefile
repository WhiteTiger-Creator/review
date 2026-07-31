CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -Werror -fPIC
LDFLAGS ?=
BUILD := build

.PHONY: all clean
all: \
	$(BUILD)/ledger-gateway \
	$(BUILD)/libledger_rules.so.1.0 \
	$(BUILD)/libledger_rules.so.1.1 \
	$(BUILD)/libledger_policy.so.2.0 \
	$(BUILD)/libledger_policy.so.2.1

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/ledger-gateway: src/gateway.c include/policy.h | $(BUILD)
	$(CC) $(CFLAGS) -Iinclude -o $@ src/gateway.c -ldl

$(BUILD)/libledger_rules.so.1.0: src/rules_baseline.c include/rules.h maps/rules_v1.map | $(BUILD)
	$(CC) $(CFLAGS) -Iinclude -shared -Wl,-soname,libledger_rules.so.1 \
		-Wl,--version-script=maps/rules_v1.map -o $@ src/rules_baseline.c

$(BUILD)/libledger_rules.so.1.1: src/rules_v3.c include/rules.h maps/rules_v2.map | $(BUILD)
	$(CC) $(CFLAGS) -Iinclude -shared -Wl,-soname,libledger_rules.so.1 \
		-Wl,--version-script=maps/rules_v2.map -o $@ src/rules_v3.c

$(BUILD)/libledger_policy.so.2.0: src/policy_baseline.c include/policy.h include/rules.h maps/policy.map $(BUILD)/libledger_rules.so.1.0 | $(BUILD)
	ln -sfn libledger_rules.so.1.0 $(BUILD)/libledger_rules.so
	$(CC) $(CFLAGS) -Iinclude -shared -Wl,-soname,libledger_policy.so.2 \
		-Wl,--version-script=maps/policy.map -Wl,-rpath,'$$ORIGIN' \
		-L$(BUILD) -o $@ src/policy_baseline.c -lledger_rules

$(BUILD)/libledger_policy.so.2.1: src/policy_v3.c include/policy.h include/rules.h maps/policy.map $(BUILD)/libledger_rules.so.1.1 | $(BUILD)
	ln -sfn libledger_rules.so.1.1 $(BUILD)/libledger_rules.so
	$(CC) $(CFLAGS) -Iinclude -shared -Wl,-soname,libledger_policy.so.2 \
		-Wl,--version-script=maps/policy.map -Wl,-rpath,'$$ORIGIN' \
		-L$(BUILD) -o $@ src/policy_v3.c -lledger_rules

clean:
	rm -rf $(BUILD)
