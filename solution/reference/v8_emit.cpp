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
    if (g_has_snap && g_snap.profile_stamp == profile_stamp) {
        g_has_snap = false;
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

std::uint32_t masked_cross_weight(const AlgebraPair& pair, const Algebra& algebra) {
    const auto profile_word = load_lim_u32("profile_word", 0x0763A7);
    const auto holdout_salt = load_lim_u32("holdout_salt", 0);
    return pair.cross_weight ^ (profile_word & algebra.profile_mask) ^ holdout_salt;
}

std::vector<RowItem> apply_cross_terms(const std::vector<RowItem>& rows, const Algebra& algebra) {
    auto out = rows;
    for (const auto& pair : algebra.instance_pairs) {
        std::uint32_t duty_a = 0;
        std::uint32_t duty_b = 0;
        for (const auto& row : out) {
            if (row.instance_key == pair.key_a && row.corpus_tag == "a") duty_a = row.duty_cycles;
            if (row.instance_key == pair.key_b && row.corpus_tag == "b") duty_b = row.duty_cycles;
        }
        const auto cross = duty_a * duty_b + masked_cross_weight(pair, algebra);
        for (auto& row : out) {
            if (row.instance_key == pair.key_a && row.corpus_tag == "a") row.duty_cycles = cross;
        }
    }
    const auto multiplier = std::max<std::uint32_t>(1, algebra.stress_multiplier);
    if (multiplier > 1) {
        for (auto& row : out) {
            if (row.lane_phase >= 2 && row.corpus_tag == "a") row.duty_cycles *= multiplier;
        }
    }
    return out;
}

std::uint32_t count_obligations(const std::vector<RowItem>& rows, const Algebra& algebra) {
    const auto tolerance = load_lim_u32("tolerance_band", 0);
    const auto multiplier = std::max<std::uint32_t>(1, algebra.stress_multiplier);
    std::uint32_t violations = 0;
    for (const auto& pair : algebra.instance_pairs) {
        std::uint32_t duty_a = 0;
        std::uint32_t duty_b = 0;
        std::uint32_t lane_phase = 0;
        bool have_a = false;
        bool have_b = false;
        for (const auto& row : rows) {
            if (row.instance_key == pair.key_a && row.corpus_tag == "a") {
                duty_a = row.duty_cycles;
                lane_phase = row.lane_phase;
                have_a = true;
            }
            if (row.instance_key == pair.key_b && row.corpus_tag == "b") {
                duty_b = row.duty_cycles;
                have_b = true;
            }
        }
        if (!have_a || !have_b || duty_b == 0) {
            violations += 1;
            continue;
        }
        const auto mc = masked_cross_weight(pair, algebra);
        const auto scale = (lane_phase >= 2) ? multiplier : 1u;
        if (duty_a % scale != 0) {
            violations += 1;
            continue;
        }
        const auto raw_a = duty_a / scale;
        const auto derived_raw_a = (raw_a >= mc ? raw_a - mc : 0) / std::max<std::uint32_t>(1, duty_b);
        const auto expected = (derived_raw_a * duty_b + mc) * scale;
        const auto delta = duty_a > expected ? duty_a - expected : expected - duty_a;
        if (delta > tolerance) violations += 1;
    }
    return violations;
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
        if (a.instance_key != b.instance_key) return a.instance_key < b.instance_key;
        return a.corpus_tag < b.corpus_tag;
    });
    for (std::size_t i = 0; i < merged.size(); ++i) merged[i].row_seq = static_cast<std::uint32_t>(i + 1);
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
    doc.obligation_violations = count_obligations(doc.rows, algebra);
    return doc;
}

}  // namespace j2n
