#pragma once

#include <string>

struct CliArgs {
    bool ok = false;
    std::string input_path;
    std::string output_path;
};

inline CliArgs parse_cli_args(int argc, char** argv) {
    CliArgs args;
    if (argc != 3) return args;
    args.input_path = argv[1];
    args.output_path = argv[2];
    args.ok = true;
    return args;
}
