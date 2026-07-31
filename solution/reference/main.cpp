#include "hs_driver/bundle_stage.hpp"
#include "hs_driver/corpus_stage.hpp"
#include "hs_driver/lane_stage.hpp"
#include "j2n/pack_doc.hpp"
#include "r3k/handoff.hpp"
#include "s4d/bank.hpp"
#include "w7p/normalize.hpp"
#include <iostream>
#include <filesystem>
#include <fstream>
#include <nlohmann/json.hpp>
#include <openssl/evp.h>
#include <sstream>
#include <vector>

namespace fs = std::filesystem;
using json = nlohmann::json;

static const char* ENV_ROOT = "/app/environment";
static const char* OUT_JSON = "/app/output/proof_certificate_bundle.tar.json";
static const char* STAGE_DIR = "/app/output/stage";
static const char* BANK_CACHE = "/app/output/stage/bank_cache.txt";

static std::vector<std::uint8_t> read_bytes(const fs::path& path) {
    std::ifstream in(path, std::ios::binary);
    return std::vector<std::uint8_t>((std::istreambuf_iterator<char>(in)), {});
}

static j2n::Algebra load_algebra(const fs::path& path) {
    std::ifstream in(path);
    json j; in >> j;
    j2n::Algebra a;
    a.algebra_version = j.at("algebra_version").get<std::uint32_t>();
    a.stress_multiplier = j.at("stress_multiplier").get<std::uint32_t>();
    a.profile_mask = j.at("profile_mask").get<std::uint32_t>();
    for (const auto& p : j.at("instance_pairs")) {
        a.instance_pairs.push_back({p.at("key_a").get<std::string>(), p.at("key_b").get<std::string>(),
                                    p.at("cross_weight").get<std::uint32_t>()});
    }
    return a;
}

static std::uint32_t load_lim_u32(const char* key, std::uint32_t fallback) {
    std::ifstream in(std::string(ENV_ROOT) + "/k8m/lim_a763.toml");
    std::string line;
    while (std::getline(in, line)) {
        if (line.rfind(key, 0) == 0) {
            auto pos = line.find('=');
            auto raw = line.substr(pos + 1);
            while (!raw.empty() && raw[0] == ' ') raw.erase(raw.begin());
            if (raw.rfind("0x", 0) == 0) return std::stoul(raw, nullptr, 16);
            return std::stoul(raw);
        }
    }
    return fallback;
}

static void apply_od_margins(std::vector<j2n::RowItem>& rows) {
    for (auto& row : rows) {
        row.duty_cycles += s4d::od_margin(row.instance_key, row.corpus_tag);
    }
}

static std::vector<j2n::RowItem> build_duty_rows(const w7p::NormalizedSet& norm_a,
                                                 const w7p::NormalizedSet& norm_b,
                                                 std::uint32_t lane_phase) {
    std::vector<j2n::RowItem> rows;
    for (const auto& e : norm_a.entries) {
        rows.push_back({0, e.instance_key, e.duty_weight, "a", lane_phase});
    }
    for (const auto& e : norm_b.entries) {
        rows.push_back({0, e.instance_key, e.duty_weight, "b", lane_phase});
    }
    std::sort(rows.begin(), rows.end(), [](const j2n::RowItem& a, const j2n::RowItem& b) {
        return std::tie(a.instance_key, a.corpus_tag) < std::tie(b.instance_key, b.corpus_tag);
    });
    for (std::size_t i = 0; i < rows.size(); ++i) rows[i].row_seq = static_cast<std::uint32_t>(i + 1);
    return rows;
}

static std::vector<r3k::SortKeys> sort_keys_from_rows(const std::vector<j2n::RowItem>& rows) {
    std::vector<r3k::SortKeys> keys;
    for (const auto& r : rows) keys.push_back({r.row_seq, r.instance_key, r.corpus_tag});
    return keys;
}

static std::string witness_cache_digest(const std::vector<std::uint8_t>& payload) {
    unsigned char hash[EVP_MAX_MD_SIZE];
    unsigned int hash_len = 0;
    EVP_Digest(payload.data(), payload.size(), hash, &hash_len, EVP_sha256(), nullptr);
    char out[9];
    std::snprintf(out, sizeof(out), "%02x%02x%02x%02x", hash[0], hash[1], hash[2], hash[3]);
    return std::string(out);
}

static std::string duty_checksum(const std::vector<j2n::RowItem>& rows) {
    auto sorted = rows;
    std::sort(sorted.begin(), sorted.end(), [](const j2n::RowItem& a, const j2n::RowItem& b) {
        return std::tie(a.instance_key, a.corpus_tag) < std::tie(b.instance_key, b.corpus_tag);
    });
    std::ostringstream material;
    for (const auto& row : sorted) {
        material << row.instance_key << ':' << row.corpus_tag << ':' << row.duty_cycles << ';';
    }
    unsigned char hash[EVP_MAX_MD_SIZE];
    unsigned int hash_len = 0;
    auto s = material.str();
    EVP_Digest(s.data(), s.size(), hash, &hash_len, EVP_sha256(), nullptr);
    char out[9];
    std::snprintf(out, sizeof(out), "%02x%02x%02x%02x", hash[0], hash[1], hash[2], hash[3]);
    return std::string(out);
}

static void write_stage_summary(const std::string& pass, std::uint32_t lane, std::uint32_t seq,
                                const std::vector<j2n::RowItem>& rows, const std::string& digest) {
    fs::create_directories(STAGE_DIR);
    std::ostringstream body;
    body << "pass=" << pass << " lane=" << lane << " witness_seq=" << seq << " rows=" << rows.size()
         << " duty_checksum=" << duty_checksum(rows) << " status=" << digest << '\n';
    std::ofstream(std::string(STAGE_DIR) + "/lane_" + pass + ".txt") << body.str();
}

static void emit_json(const j2n::BundleDoc& doc) {
    fs::create_directories("/app/output");
    json j;
    j["arm_id"] = doc.arm_id;
    j["replay_digest"] = doc.replay_digest;
    j["bank_fingerprint"] = doc.bank_fingerprint;
    j["obligation_violations"] = doc.obligation_violations;
    j["rows"] = json::array();
    for (const auto& row : doc.rows) {
        j["rows"].push_back({{"row_seq", row.row_seq},
                             {"instance_key", row.instance_key},
                             {"duty_cycles", row.duty_cycles},
                             {"corpus_tag", row.corpus_tag},
                             {"lane_phase", row.lane_phase}});
    }
    std::ofstream out(OUT_JSON);
    out << j.dump(2) << '\n';
}

static int run_cycle(bool all_fixtures) {
    auto fixture_root = fs::path(ENV_ROOT) / "k8m";
    auto algebra = load_algebra(fixture_root / "pair_v7.json");
    auto profile_word = load_lim_u32("profile_word", 0x0763A7);
    auto od_bias = load_lim_u32("od_bias", 3);
    auto warm_epoch = load_lim_u32("bank_epoch_warm", 1);
    auto stress_epoch = load_lim_u32("bank_epoch_stress", 2);
    r3k::Arm0763 arm_ctx{"0763", profile_word};

    fs::create_directories(STAGE_DIR);
    for (const auto& entry : fs::directory_iterator(STAGE_DIR)) {
        auto name = entry.path().filename().string();
        if (name.rfind("lane_", 0) == 0 || name == "bank_cache.txt") fs::remove(entry.path());
    }
    s4d::bank_reset();

    auto corpus_a = read_bytes(fixture_root / "corpus_a.kidx");
    auto corpus_b = read_bytes(fixture_root / "corpus_b.kidx");
    auto norm_a = hs_driver::load_fixture_corpus(corpus_a.data(), corpus_a.size(), 20);
    w7p::NormalizedSet empty{20, {}};

    s4d::bank_set_epoch(warm_epoch);
    auto warm_rows = build_duty_rows(norm_a, empty, 1);
    apply_od_margins(warm_rows);
    auto warm_keys = sort_keys_from_rows(warm_rows);
    auto warm = hs_driver::advance_lane({1, profile_word}, arm_ctx, warm_keys);
    write_stage_summary("warm", warm.lane_token, 1, warm_rows, witness_cache_digest(warm.payload));
    s4d::bank_persist(BANK_CACHE);

    auto norm_b = all_fixtures ? hs_driver::load_fixture_corpus(corpus_b.data(), corpus_b.size(), 20) : empty;
    s4d::bank_set_epoch(stress_epoch);
    auto stress_rows = build_duty_rows(norm_a, norm_b, 2);
    apply_od_margins(stress_rows);
    stress_rows = j2n::handoff_lane_material(warm_rows, std::move(stress_rows), profile_word);
    auto stress_keys = sort_keys_from_rows(stress_rows);
    auto stress = hs_driver::advance_lane({2, profile_word}, arm_ctx, stress_keys);
    j2n::set_bank_fingerprint(s4d::bank_fingerprint(profile_word, od_bias));
    auto doc = hs_driver::finalize_bundle(algebra, stress_rows);
    write_stage_summary("stress", stress.lane_token, 2, doc.rows, witness_cache_digest(stress.payload));
    s4d::bank_persist(BANK_CACHE);
    emit_json(doc);
    return 0;
}

int main(int argc, char** argv) {
    bool all_fixtures = false;
    for (int i = 1; i < argc; ++i) {
        if (std::string(argv[i]) == "--all-fixtures") all_fixtures = true;
    }
    try {
        return run_cycle(all_fixtures);
    } catch (const std::exception& ex) {
        std::cerr << "hs_driver: " << ex.what() << '\n';
        return 1;
    }
}
