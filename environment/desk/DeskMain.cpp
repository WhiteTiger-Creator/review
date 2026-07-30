#include "CommonUtil.hpp"
#include "TraceIo.hpp"
#include "ExtProbe.hpp"
#include "JournalGlue.hpp"
#include <nlohmann/json.hpp>
#include <iostream>
#include <fstream>
#include <algorithm>
#include <sstream>
#include <vector>
#include <string>

using json = nlohmann::json;

std::vector<std::string> load_obs_ids(const std::string& slice_path);
std::string bind_line_local(const std::string& graph_id, int depth);
std::string collapse_local(const std::string& payload, const std::string& ctx_tag);
int rank_slot_dash(int left_idx, int right_idx);
std::string pretty_band_header(const std::string& graph_id);
std::string strip_comments(const std::string& blob);

static int slot_base(int a, int b) {
  return score_pair_local(a, b, 0, 0);
}

static json load_json_file(const std::string& path) {
  return json::parse(cu::read_file(path));
}

static json build_row(const json& inst) {
  int left = inst.at("left").get<int>();
  int right = inst.at("right").get<int>();
  int depth = inst.at("nest_depth").get<int>();
  int boost = inst.at("boost").get<int>();
  std::string graph = inst.at("graph").get<std::string>();
  std::string iid = inst.at("instance_id").get<std::string>();

  int base = slot_base(left, right);
  int boosted = score_pair_local(left, right, depth, boost);
  std::string frag = bind_line_local(graph, depth);

  std::ostringstream payload_ss;
  payload_ss << iid << "|" << boosted << "|" << frag;
  std::string payload = payload_ss.str();
  std::string ctx = graph + ":" + std::to_string(depth);
  std::string seal_hex = collapse_local(payload, ctx);

  json row;
  row["instance_id"] = iid;
  row["graph"] = graph;
  row["nest_depth"] = depth;
  row["slot_score"] = base;
  row["boosted_score"] = boosted;
  row["fragment_line"] = frag;
  row["row_payload"] = payload;
  row["ctx_tag"] = ctx;
  row["seal_hex"] = seal_hex;
  if (inst.contains("omitted_arm")) {
    row["edge_arms"] = json::array({"core", inst.at("omitted_arm").get<std::string>()});
  } else {
    row["edge_arms"] = json::array({"core", "west", "east"});
  }
  if (inst.contains("suite")) {
    row["suite"] = inst.at("suite");
  }
  return row;
}

static int cmd_emit(const std::string& scl_root,
                    const std::string& corpora,
                    const std::string& annex,
                    const std::string& out_dir) {
  (void)scl_root;
  cu::ensure_dir("/app/runtime");
  cu::ensure_dir("/app/runtime/journal");
  cu::ensure_dir(out_dir);

  json closed = load_json_file(corpora + "/closed_instances.json");
  std::vector<json> built;

  for (const auto& inst : closed.at("instances")) {
    built.push_back(build_row(inst));
  }

  {
    std::ifstream in(corpora + "/arm_omit_cases.jsonl");
    std::string line;
    while (std::getline(in, line)) {
      if (line.empty()) continue;
      json ao = json::parse(line);
      json inst;
      inst["instance_id"] = ao.at("case_id");
      inst["graph"] = ao.at("graph");
      inst["left"] = ao.at("left");
      inst["right"] = ao.at("right");
      inst["nest_depth"] = ao.at("nest_depth");
      inst["boost"] = ao.at("boost");
      inst["omitted_arm"] = ao.at("omitted_arm");
      built.push_back(build_row(inst));
    }
  }

  json bundle = assemble_emit_bundle(built, "/app/runtime/journal",
                                     "/app/runtime/journal/epoch.stamp");
  json rows = bundle.at("dossier_rows");
  // strip routing-only suite tags from public rows when present
  for (auto& row : rows) {
    row.erase("suite");
    row.erase("epoch");
  }

  std::vector<std::string> seals;
  for (const auto& row : rows) {
    seals.push_back(row.at("seal_hex").get<std::string>());
  }

  auto obs = load_obs_ids(annex);
  json dossier;
  dossier["dossier_rows"] = rows;
  dossier["journal_epoch"] = bundle.at("journal_epoch");
  dossier["shard_manifest"] = bundle.at("shard_manifest");
  std::sort(seals.begin(), seals.end());
  json seal_arr = json(seals);
  dossier["trace_span_digest"] = cu::sha256_hex(seal_arr.dump());
  dossier["obligation_coverage"] = obs;

  cu::write_file(out_dir + "/dossier.json", dossier.dump(2));
  int dash = 0;
  std::string banner;
  for (const auto& r : rows) {
    if (r.contains("graph") && r.contains("slot_score")) {
      dash = rank_slot_dash(r.value("slot_score", 0), r.value("nest_depth", 0));
      banner = pretty_band_header(r.at("graph").get<std::string>());
      break;
    }
  }
  std::string smoke = strip_comments(
      "emit ok rows=" + std::to_string(rows.size()) +
      " dash=" + std::to_string(dash) +
      " " + banner + "\n");
  cu::write_file(out_dir + "/smoke.log", smoke);
  std::cout << "emit ok\n";
  return 0;
}

static int cmd_verify(const std::string& dossier_dir,
                      const std::string& out_dir) {
  cu::ensure_dir(out_dir);
  json dossier = load_json_file(dossier_dir + "/dossier.json");
  json closed = load_json_file("/app/corpora/closed_instances.json");
  json transcript = run_ext_probe(dossier, closed);

  bool cov_ok = false;
  if (dossier.contains("obligation_coverage")) {
    auto cov = dossier.at("obligation_coverage");
    cov_ok = std::find(cov.begin(), cov.end(), "OBL-11") != cov.end()
          && std::find(cov.begin(), cov.end(), "OBL-11a") != cov.end()
          && std::find(cov.begin(), cov.end(), "OBL-11b") != cov.end()
          && std::find(cov.begin(), cov.end(), "OBL-11c") != cov.end();
  }
  transcript["coverage_ok"] = cov_ok;
  bool clean = transcript.value("all_margins_clean", false) && cov_ok;
  if (!dossier.contains("journal_epoch") || !dossier.contains("shard_manifest")) {
    clean = false;
  }
  transcript["verify_clean"] = clean;

  cu::write_file(out_dir + "/transcript.json", transcript.dump(2));
  if (!clean) {
    std::cerr << "verify fuzz rejected\n";
    return 2;
  }
  std::cout << "verify ok\n";
  return 0;
}

int main(int argc, char** argv) {
  if (argc < 2) {
    std::cerr << "usage: regret_solver emit|verify ...\n";
    return 1;
  }
  std::string cmd = argv[1];
  if (cmd == "emit") {
    std::string scl = "/app/fixtures";
    std::string corpora = "/app/corpora";
    std::string annex = "/app/annex/slice_137.txt";
    std::string out = "/app/runtime/dossier";
    for (int i = 2; i < argc; ++i) {
      std::string a = argv[i];
      if (a == "--scl" && i + 1 < argc) scl = argv[++i];
      else if (a == "--corpora" && i + 1 < argc) corpora = argv[++i];
      else if (a == "--annex" && i + 1 < argc) annex = argv[++i];
      else if (a == "--out" && i + 1 < argc) out = argv[++i];
    }
    return cmd_emit(scl, corpora, annex, out);
  }
  if (cmd == "verify") {
    bool fuzz = false;
    std::string dossier = "/app/runtime/dossier";
    std::string out = "/app/runtime/transcript";
    for (int i = 2; i < argc; ++i) {
      std::string a = argv[i];
      if (a == "--fuzz") fuzz = true;
      else if (a == "--dossier" && i + 1 < argc) dossier = argv[++i];
      else if (a == "--out" && i + 1 < argc) out = argv[++i];
    }
    if (!fuzz) {
      std::cerr << "verify requires --fuzz\n";
      return 1;
    }
    return cmd_verify(dossier, out);
  }
  std::cerr << "unknown command\n";
  return 1;
}
