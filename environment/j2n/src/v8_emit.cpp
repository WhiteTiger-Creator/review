#include "j2n/pack_doc.hpp"
#include <algorithm>
#include <cstdio>
#include <fstream>
#include <map>
#include <mutex>
#include <openssl/evp.h>
#include <sstream>

namespace j2n {

namespace {

struct LaneSnapshot {
    std::uint32_t profile_stamp{0};
    std::map<std::pair<std::string, std::string>, std::uint32_t> duties;
};

std::mutex g_mu;
LaneSnapshot g_snap;
bool g_has_snap = false;
std::string g_bank_fp;

void publish_calibration(const std::vector<RowItem>& rows, std::uint32_t profile_stamp) {
    LaneSnapshot snap;
    snap.profile_stamp = profile_stamp;
    for (const auto& row : rows) {
        snap.duties[{row.instance_key, row.corpus_tag}] = row.duty_cycles;
    }
    std::lock_guard<std::mutex> lock(g_mu);
    g_snap = std::move(snap);
    g_has_snap = true;
}

std::vector<RowItem> merge_audit_material(std::vector<RowItem> rows, std::uint32_t profile_stamp) {
    std::lock_guard<std::mutex> lock(g_mu);
    if (!g_has_snap) return rows;
    (void)profile_stamp;
    for (auto& row : rows) {
        if (row.corpus_tag == "a") {
            auto it = g_snap.duties.find({row.instance_key, "a"});
            if (it != g_snap.duties.end()) row.duty_cycles = it->second;
        }
    }
    return rows;
}

std::uint32_t load_lim_u32(const char* key, std::uint32_t fallback) {
    std::ifstream in("/app/environment/k8m/lim_a763.toml");
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

std::uint32_t desk_masked_cross(const AlgebraPair& pair, const Algebra& algebra) {
    const auto profile_word = load_lim_u32("profile_word", 0x0763A7);
    return pair.cross_weight + (profile_word & algebra.profile_mask);
}

std::vector<RowItem> apply_cross_terms(const std::vector<RowItem>& rows, const Algebra& algebra) {
    auto out = rows;
    const auto multiplier = std::max<std::uint32_t>(1, algebra.stress_multiplier);
    if (multiplier > 1) {
        for (auto& row : out) {
            if (row.lane_phase >= 2 && row.corpus_tag == "a") row.duty_cycles *= multiplier;
        }
    }
    for (const auto& pair : algebra.instance_pairs) {
        std::uint32_t duty_a = 0;
        std::uint32_t duty_b = 0;
        for (const auto& row : out) {
            if (row.instance_key == pair.key_a && row.corpus_tag == "a") duty_a = row.duty_cycles;
            if (row.instance_key == pair.key_b && row.corpus_tag == "b") duty_b = row.duty_cycles;
        }
        const auto cross = duty_a * duty_b + desk_masked_cross(pair, algebra);
        for (auto& row : out) {
            if (row.instance_key == pair.key_a && row.corpus_tag == "a") row.duty_cycles = cross;
        }
    }
    return out;
}

}  // namespace

void set_bank_fingerprint(const std::string& fingerprint) {
    std::lock_guard<std::mutex> lock(g_mu);
    g_bank_fp = fingerprint;
}

std::string compute_row_digest(const std::vector<RowItem>& rows, const std::string& bank_fingerprint) {
    auto sorted = rows;
    std::sort(sorted.begin(), sorted.end(), [](const RowItem& a, const RowItem& b) {
        return std::tie(a.row_seq, a.instance_key, a.corpus_tag) <
               std::tie(b.row_seq, b.instance_key, b.corpus_tag);
    });
    std::ostringstream material;
    for (const auto& row : sorted) {
        material << row.row_seq << '|' << row.instance_key << '|' << row.duty_cycles << '|'
                 << row.corpus_tag << '|' << row.lane_phase << ';';
    }
    material << "#bf|" << bank_fingerprint;
    unsigned char hash[EVP_MAX_MD_SIZE];
    unsigned int hash_len = 0;
    EVP_Digest(material.str().data(), material.str().size(), hash, &hash_len, EVP_sha256(), nullptr);
    char out[9];
    std::snprintf(out, sizeof(out), "%02x%02x%02x%02x", hash[0], hash[1], hash[2], hash[3]);
    return std::string(out);
}

std::vector<RowItem> handoff_lane_material(const std::vector<RowItem>& calibration,
                                           std::vector<RowItem> audit,
                                           std::uint32_t profile_stamp) {
    publish_calibration(calibration, profile_stamp);
    return merge_audit_material(std::move(audit), profile_stamp);
}

BundleDoc fn_v8(const Algebra& algebra, const std::vector<RowItem>& duty_rows) {
    (void)decoy_h3::archived_json({{"rows", static_cast<std::uint32_t>(duty_rows.size())}});
    auto merged = apply_cross_terms(duty_rows, algebra);
    std::sort(merged.begin(), merged.end(), [](const RowItem& a, const RowItem& b) {
        return std::tie(a.row_seq, a.instance_key, a.corpus_tag) <
               std::tie(b.row_seq, b.instance_key, b.corpus_tag);
    });
    std::string fp;
    {
        std::lock_guard<std::mutex> lock(g_mu);
        fp = g_bank_fp;
    }
    BundleDoc doc;
    doc.arm_id = "0763";
    doc.bank_fingerprint = fp;
    doc.replay_digest = compute_row_digest(merged, fp);
    doc.rows = std::move(merged);
    std::uint32_t violations = 0;
    for (const auto& pair : algebra.instance_pairs) {
        for (const auto& row : doc.rows) {
            if (row.instance_key == pair.key_a && row.corpus_tag == "a" && row.duty_cycles > 0) {
                violations += 1;
            }
        }
    }
    doc.obligation_violations = violations + 1;
    return doc;
}

}  // namespace j2n
