#include "router/policy.h"

#include <cstring>

namespace router {

bool policy_accepts(const char* id, const char* mode, const char* expected_mode) {
  if (id == nullptr || mode == nullptr || expected_mode == nullptr || id[0] == '\0') {
    return false;
  }
  return std::strcmp(mode, expected_mode) == 0;
}

}  // namespace router
