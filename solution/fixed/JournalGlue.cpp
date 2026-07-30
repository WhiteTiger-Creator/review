#include "JournalGlue.hpp"
#include "ShardLedger.hpp"
#include "CommonUtil.hpp"
#include <map>
#include <fstream>

nlohmann::json assemble_emit_bundle(const std::vector<nlohmann::json>& built_rows,
                                    const std::string& journal_root,
                                    const std::string& stamp_path) {
  cu::ensure_dir(journal_root);
  int epoch = bump_epoch_stamp(stamp_path);

  for (const auto& row : built_rows) {
    std::string shard = journal_root + "/suite_a.jsonl";
    if (row.contains("suite")) {
      std::string suite = row.at("suite").get<std::string>();
      shard = journal_root + "/" + suite + ".jsonl";
    } else if (row.contains("omitted_arm") ||
               (row.contains("edge_arms") && row.at("edge_arms").size() == 2)) {
      shard = journal_root + "/arm_omit.jsonl";
    }
    write_shard_line(shard, row, epoch);
  }

  auto merged = merge_epoch_rows(journal_root, epoch);
  nlohmann::json out;
  out["journal_epoch"] = epoch;
  out["dossier_rows"] = merged;
  out["shard_manifest"] =
      nlohmann::json::array({"suite_a", "suite_b", "suite_c", "arm_omit"});
  return out;
}
