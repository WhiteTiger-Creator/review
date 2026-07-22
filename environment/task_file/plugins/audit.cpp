#include "router/router.h"
#include "router/policy.h"

extern "C" const char* routekit_audit_mode() { return router::expected_mode(); }

extern "C" int routekit_audit_accepts(const char* id, const char* mode) {
  return router::policy_accepts(id, mode, router::expected_mode()) ? 1 : 0;
}
