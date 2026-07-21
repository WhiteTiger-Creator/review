#pragma once
#include <cstdint>

namespace forge {
constexpr std::uint64_t kDigestSeed = 1469598103934665603ull;
constexpr std::uint64_t kDigestStep = 1099511628211ull;
constexpr std::uint64_t kDigestMask = 0xffffffffffffffffull;
constexpr int kSchemaVersion = 1;
}
