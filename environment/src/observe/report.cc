#include "observe/report.h"

#include "engine/session.h"
#include "support/files.h"

namespace site {

std::string operator_view(const std::filesystem::path& root) {
    return inspect_local(root);
}

void append_event(const std::filesystem::path& root, const std::string& event) {
    const auto path = root / ".site" / "events";
    auto text = read_text(path);
    text += event;
    text += '\n';
    write_atomic(path, text);
}

}  // namespace site
