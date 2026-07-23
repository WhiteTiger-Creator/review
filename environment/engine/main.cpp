#include "compile.hpp"
#include "flow.hpp"

#include <exception>
#include <iostream>
#include <string>

int main(int argc, char **argv) {
    try {
        if (argc < 2) {
            throw std::runtime_error("missing subcommand");
        }
        std::string subcommand = argv[1];
        if (subcommand == "run") {
            return termatrix::run_matrix_main(argc, argv);
        }
        if (subcommand == "key-unit") {
            return termatrix::key_unit_main(argc, argv);
        }
        if (subcommand == "compile-unit") {
            return termatrix::compile_unit_main(argc, argv);
        }
        throw std::runtime_error("unknown subcommand: " + subcommand);
    } catch (const std::exception &err) {
        std::cerr << "termatrix-driver: " << err.what() << "\n";
        return 1;
    }
}
