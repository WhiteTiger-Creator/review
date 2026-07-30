#include "CommonUtil.hpp"
#include <nlohmann/json.hpp>
#include <sstream>
#include <vector>
#include <string>
#include <algorithm>

using json = nlohmann::json;

namespace {

constexpr uint32_t kNestContinuityScale = (0x0D & 0x1F);
constexpr uint8_t kUnitSeparator = static_cast<uint8_t>(0x1F);

int mod97(int x) {
  int r = x % 97;
  return r < 0 ? r + 97 : r;
}

int expected_gap_of(int gap_a, int gap_b, int depth) {
  return mod97(gap_a * 3 + gap_b * 5 + depth * 7);
}

int schedule_boosted_of(int slot_score, int depth, int boost) {
  return mod97(slot_score + depth * 7 + boost);
}

std::string probe_binding(const std::string& graph_id, int depth) {
  uint32_t tag = cu::fnv1a32(graph_id);
  tag = (tag + static_cast<uint32_t>(depth) * kNestContinuityScale) % 100000u;
  std::ostringstream oss;
  oss << "G:" << graph_id << "|D:" << depth << "|C:N" << tag;
  return oss.str();
}

std::string probe_digest(const std::string& row_utf8, const std::string& ctx_tag) {
  std::vector<uint8_t> buf;
  buf.reserve(row_utf8.size() + 1 + ctx_tag.size());
  buf.insert(buf.end(), row_utf8.begin(), row_utf8.end());
  buf.push_back(kUnitSeparator);
  buf.insert(buf.end(), ctx_tag.begin(), ctx_tag.end());
  return cu::sha256_hex(buf);
}

}  // namespace

json run_ext_probe(const json& dossier, const json& closed) {
  json out;
  out["instances"] = json::array();
  bool all_ok = true;
  std::vector<std::string> replay_list;
  for (const auto& inst : closed.at("instances")) {
    std::string iid = inst.at("instance_id").get<std::string>();
    json row;
    for (const auto& r : dossier.at("dossier_rows")) {
      if (r.at("instance_id").get<std::string>() == iid) {
        row = r;
        break;
      }
    }
    json rec;
    rec["instance_id"] = iid;
    if (row.is_null() || row.empty()) {
      rec["fuzz_margin_vector"] = json::array({-1.0, -1.0, -1.0});
      rec["obligation_ids_satisfied"] = json::array();
      rec["replay_digest"] = "";
      all_ok = false;
      out["instances"].push_back(rec);
      continue;
    }
    int depth = inst.at("nest_depth").get<int>();
    int boost = inst.at("boost").get<int>();
    int gap_a = inst.at("gap_a").get<int>();
    int gap_b = inst.at("gap_b").get<int>();
    int reported = row.at("boosted_score").get<int>();
    int slot = row.at("slot_score").get<int>();
    int want_gap = expected_gap_of(gap_a, gap_b, depth);
    int want_sched = schedule_boosted_of(slot, depth, boost);
    double m0 = static_cast<double>(reported - want_gap);
    double m1 = static_cast<double>(reported - want_sched);
    std::string frag_exp = probe_binding(inst.at("graph").get<std::string>(), depth);
    std::string frag_got = row.at("fragment_line").get<std::string>();
    double m2 = (frag_got == frag_exp) ? 0.0 : -1.0;
    std::string payload = row.at("row_payload").get<std::string>();
    std::string ctx = row.at("ctx_tag").get<std::string>();
    std::string seal_exp = probe_digest(payload, ctx);
    std::string seal_got = row.at("seal_hex").get<std::string>();
    if (seal_got != seal_exp) {
      m2 = -1.0;
    }
    std::ostringstream payload_exp;
    payload_exp << iid << "|" << reported << "|" << frag_got;
    if (payload != payload_exp.str()) {
      m2 = -1.0;
    }
    std::string ctx_exp = inst.at("graph").get<std::string>() + ":" + std::to_string(depth);
    if (ctx != ctx_exp) {
      m2 = -1.0;
    }
    if (!row.contains("edge_arms") || !row.at("edge_arms").is_array() ||
        row.at("edge_arms").empty()) {
      m2 = -1.0;
    }
    rec["fuzz_margin_vector"] = json::array({m0, m1, m2});
    json obs = json::array();
    if (m0 == 0.0 && m1 == 0.0 && m2 == 0.0) {
      obs = json::array({"OBL-11", "OBL-11a", "OBL-11b", "OBL-11c"});
    } else {
      all_ok = false;
    }
    rec["obligation_ids_satisfied"] = obs;
    std::string replay_src = iid + "|" + seal_got + "|" + frag_got;
    std::string replay = cu::sha256_hex(replay_src);
    rec["replay_digest"] = replay;
    replay_list.push_back(replay);
    out["instances"].push_back(rec);
  }
  std::sort(replay_list.begin(), replay_list.end());
  out["recovery_digest"] = cu::sha256_hex(json(replay_list).dump());
  out["all_margins_clean"] = all_ok;
  return out;
}
