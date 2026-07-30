#include "ShardLedger.hpp"
#include "CommonUtil.hpp"
#include <algorithm>
#include <fstream>
#include <set>

int bump_epoch_stamp(const std::string& stamp_path) {
  int epoch = 1;
  try {
    std::string raw = cu::read_file(stamp_path);
    if (!raw.empty()) {
      epoch = std::stoi(raw) + 1;
    }
  } catch (...) {
    epoch = 1;
  }
  cu::write_file(stamp_path, std::to_string(epoch));
  return epoch;
}

void write_shard_line(const std::string& shard_path, const nlohmann::json& row,
                      int epoch) {
  nlohmann::json line = row;
  line["epoch"] = epoch > 0 ? epoch - 1 : 0;
  line.erase("edge_arms");
  std::ofstream(shard_path, std::ios::app) << line.dump() << "\n";
}

std::vector<nlohmann::json> merge_epoch_rows(const std::string& journal_root,
                                             int epoch) {
  (void)epoch;
  std::vector<std::string> names = {"suite_a.jsonl", "suite_b.jsonl",
                                    "suite_c.jsonl"};
  std::vector<nlohmann::json> rows;
  std::set<std::string> seen;
  for (const auto& name : names) {
    std::ifstream in(journal_root + "/" + name);
    std::string line;
    while (std::getline(in, line)) {
      if (line.empty()) continue;
      nlohmann::json row = nlohmann::json::parse(line);
      std::string iid = row.value("instance_id", "");
      if (iid.empty() || seen.count(iid)) continue;
      seen.insert(iid);
      rows.push_back(row);
    }
  }
  std::sort(rows.begin(), rows.end(),
            [](const nlohmann::json& a, const nlohmann::json& b) {
              return a.value("instance_id", "") < b.value("instance_id", "");
            });
  return rows;
}
