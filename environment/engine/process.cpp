#include "process.hpp"

#include <array>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <sys/wait.h>

namespace termatrix {

std::string shell_quote(const std::string &value) {
    std::string out = "'";
    for (char ch : value) {
        if (ch == '\'') {
            out += "'\\''";
        } else {
            out += ch;
        }
    }
    out += "'";
    return out;
}

static std::string join_command(const std::vector<std::string> &args) {
    std::string command;
    bool first = true;
    for (const auto &arg : args) {
        if (!first) {
            command += " ";
        }
        first = false;
        command += shell_quote(arg);
    }
    return command;
}

std::string capture_command(const std::vector<std::string> &args) {
    std::string command = join_command(args) + " 2>&1";
    FILE *pipe = popen(command.c_str(), "r");
    if (!pipe) {
        throw std::runtime_error("failed to run command: " + command);
    }

    std::array<char, 256> buffer{};
    std::string output;
    while (fgets(buffer.data(), static_cast<int>(buffer.size()), pipe) != nullptr) {
        output += buffer.data();
    }

    int status = pclose(pipe);
    if (status == -1 || !WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        throw std::runtime_error("command failed: " + command + "\n" + output);
    }
    return output;
}

void run_checked(const std::vector<std::string> &args) {
    std::string command = join_command(args);
    int status = std::system(command.c_str());
    if (status == -1 || !WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        throw std::runtime_error("command failed: " + command);
    }
}

}  // namespace termatrix
