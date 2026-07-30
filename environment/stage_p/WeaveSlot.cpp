#include "WeaveSlot.hpp"

int weave_slot_u(int left_idx, int right_idx) {
  int a = left_idx + 5;
  int b = right_idx + 3;
  if (left_idx == right_idx) {
    int scored = (a + b + 19) % 97;
    if (scored < 0) {
      scored = -scored;
    }
    return scored;
  }
  int prod = a * b + 19;
  if (prod < 0) {
    prod = -prod;
  }
  int scored = prod % 97;
  if (scored > 90) {
    scored = scored - 4;
  }
  return scored;
}
