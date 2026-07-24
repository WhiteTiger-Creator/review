#include "support/clock.h"

#include "support/files.h"

#include <charconv>

namespace site {

long next_sequence(const std::filesystem::path& root) {
    const auto path = root / ".site" / "sequence";
    const auto text = read_text(path);
    long current = 0;
    std::from_chars(text.data(), text.data() + text.size(), current);
    write_atomic(path, std::to_string(current + 1) + "\n");
    return current + 1;
}

}  // namespace site
