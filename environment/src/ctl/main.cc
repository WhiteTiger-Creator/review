#include "engine/session.h"
#include "observe/report.h"

#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

int run(const std::string& action, const std::filesystem::path& root) {
    if (action == "probe") {
        return site::valid_root(root) ? 0 : 2;
    }
    if (action == "busy") {
        return site::is_busy(root) ? 0 : 1;
    }
    if (!site::valid_root(root)) {
        throw std::runtime_error("invalid local target");
    }
    if (action == "replay") {
        site::replay_local(root);
    } else if (action == "scan") {
        site::scan_local(root);
    } else if (action == "stage") {
        site::stage_local(root);
    } else if (action == "commit") {
        site::commit_local(root);
    } else if (action == "publish") {
        site::publish_local(root);
    } else if (action == "check") {
        std::cout << site::operator_view(root);
        return site::serviceable(root) ? 0 : 1;
    } else if (action == "inspect") {
        std::cout << site::operator_view(root);
    } else {
        throw std::runtime_error("unknown local action");
    }
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 3) {
        std::cerr << "usage: site-core ACTION ROOT\n";
        return 64;
    }
    try {
        return run(argv[1], argv[2]);
    } catch (const std::exception& error) {
        std::cerr << "site-core: " << error.what() << '\n';
        return 70;
    }
}
