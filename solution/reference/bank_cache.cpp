#include "s4d/bank.hpp"
#include <cstdio>
#include <fstream>
#include <map>
#include <mutex>
#include <openssl/evp.h>
#include <sstream>

namespace s4d {

namespace {

std::mutex g_mu;
std::uint32_t g_epoch = 1;
std::map<std::string, std::uint32_t> g_cache;

std::string cache_key(const std::string& instance_key, const std::string& corpus_tag,
                      std::uint32_t epoch) {
    return instance_key + "|" + corpus_tag + "|e" + std::to_string(epoch);
}

std::uint32_t parse_ikey_nibble(const std::string& instance_key) {
    if (instance_key.size() < 5 || instance_key[0] != 'i') return 1;
    try {
        return static_cast<std::uint32_t>(std::stoul(instance_key.substr(1), nullptr, 16) & 0xffu);
    } catch (...) {
        return 1;
    }
}

}  // namespace

void bank_reset() {
    std::lock_guard<std::mutex> lock(g_mu);
    g_cache.clear();
    g_epoch = 1;
}

void bank_set_epoch(std::uint32_t epoch) {
    std::lock_guard<std::mutex> lock(g_mu);
    g_epoch = epoch == 0 ? 1 : epoch;
}

std::uint32_t active_epoch() {
    std::lock_guard<std::mutex> lock(g_mu);
    return g_epoch;
}

std::uint32_t od_margin(const std::string& instance_key, const std::string& corpus_tag) {
    std::lock_guard<std::mutex> lock(g_mu);
    const auto key = cache_key(instance_key, corpus_tag, g_epoch);
    auto it = g_cache.find(key);
    if (it != g_cache.end()) return it->second;
    const auto nibble = parse_ikey_nibble(instance_key);
    const auto tag_bit = corpus_tag == "a" ? 1u : 0u;
    const auto margin = ((nibble + 3u) * g_epoch + tag_bit) & 0xffu;
    g_cache[key] = margin;
    return margin;
}

std::string bank_fingerprint(std::uint32_t profile_word, std::uint32_t od_bias) {
    std::lock_guard<std::mutex> lock(g_mu);
    std::ostringstream material;
    material << g_epoch << '|' << od_bias << '|' << std::hex << profile_word;
    unsigned char hash[EVP_MAX_MD_SIZE];
    unsigned int hash_len = 0;
    auto s = material.str();
    EVP_Digest(s.data(), s.size(), hash, &hash_len, EVP_sha256(), nullptr);
    char out[9];
    std::snprintf(out, sizeof(out), "%02x%02x%02x%02x", hash[0], hash[1], hash[2], hash[3]);
    return std::string(out);
}

void bank_persist(const std::string& path) {
    std::lock_guard<std::mutex> lock(g_mu);
    std::ofstream out(path, std::ios::binary | std::ios::trunc);
    out << g_epoch << '\n';
    for (const auto& [k, v] : g_cache) out << k << '=' << v << '\n';
}

void bank_load(const std::string& path) {
    std::lock_guard<std::mutex> lock(g_mu);
    std::ifstream in(path);
    if (!in) return;
    g_cache.clear();
    in >> g_epoch;
    std::string line;
    std::getline(in, line);
    while (std::getline(in, line)) {
        auto pos = line.find('=');
        if (pos == std::string::npos) continue;
        g_cache[line.substr(0, pos)] = static_cast<std::uint32_t>(std::stoul(line.substr(pos + 1)));
    }
}

}  // namespace s4d
