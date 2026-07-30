#include "ShardLedger.hpp"
#include "CommonUtil.hpp"
#include <fstream>

// Decoy: writes operator scratch notes, never consumed by merge_epoch_rows.
void write_scratch_note(const std::string& path, const std::string& note) {
  std::ofstream out(path, std::ios::app);
  out << "# " << note << "\n";
  (void)cu::sha256_hex(note);
}
