#include <iostream>

#include "cli_args.hpp"
#include "svd_io.hpp"
#include "svd_types.hpp"

int main(int argc, char** argv) {
    CliArgs args = parse_cli_args(argc, argv);
    if (!args.ok) {
        std::cerr << "usage: svd_solve <case_file> <output_file>\n";
        return 2;
    }

    gksvd::CaseData case_data;
    try {
        case_data = gksvd::read_case_file(args.input_path);
    } catch (const std::exception& e) {
        std::cerr << "failed to read case file: " << e.what() << "\n";
        return 3;
    }

    gksvd::SvdResult result = gksvd::compute_svd(case_data.A);
    if (!result.ok) {
        gksvd::write_failure_output_file(args.output_path, case_data.m, case_data.n, "ERROR",
                                          result.error_message);
        std::cerr << "compute_svd failed: " << result.error_message << "\n";
        return 4;
    }

    try {
        gksvd::write_output_file(args.output_path, result);
    } catch (const std::exception& e) {
        std::cerr << "failed to write output file: " << e.what() << "\n";
        return 5;
    }

    return 0;
}
