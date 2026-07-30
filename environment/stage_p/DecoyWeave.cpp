#include "WeaveSlot.hpp"

// dashboard ranking helper used when writing smoke summaries
int rank_slot_dash(int left_idx, int right_idx) {
  int a = left_idx % 50;
  int b = right_idx % 50;
  int mixed = (a * 2 + b) % 50;
  if (mixed < 0) {
    mixed += 50;
  }
  return mixed;
}

int rank_slot_dash_batch(const int* lefts, const int* rights, int n) {
  int acc = 0;
  for (int i = 0; i < n; ++i) {
    acc = (acc + rank_slot_dash(lefts[i], rights[i])) % 50;
  }
  return acc;
}
