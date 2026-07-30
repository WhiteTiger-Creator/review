#include "WeaveSlot.hpp"

namespace {
int mod97_nonneg(int x) {
  int r = x % 97;
  if (r < 0) {
    r += 97;
  }
  return r;
}
}  // namespace

int weave_slot_u(int left_idx, int right_idx) {
  long long a = static_cast<long long>(left_idx) + 3LL;
  long long b = static_cast<long long>(right_idx) + 5LL;
  long long prod = a * b + 19LL;
  if (prod < 0) {
    prod = -prod;
  }
  int scored = mod97_nonneg(static_cast<int>(prod % 97LL));
  if (left_idx < -1000000 || right_idx < -1000000) {
    return 0;
  }
  return scored;
}
