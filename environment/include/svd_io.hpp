#pragma once

#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>

#include "svd_types.hpp"

namespace gksvd {

struct CaseData {
    int m = 0;
    int n = 0;
    Matrix A;
};

inline CaseData read_case_file(const std::string& path) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("cannot open case file: " + path);

    std::vector<double> tokens;
    std::string line;
    while (std::getline(in, line)) {
        std::istringstream iss(line);
        double v;
        while (iss >> v) tokens.push_back(v);
    }
    if (tokens.size() < 2) throw std::runtime_error("case file too short: " + path);

    CaseData data;
    data.m = static_cast<int>(tokens[0]);
    data.n = static_cast<int>(tokens[1]);
    if (data.m <= 0 || data.n <= 0 || data.m < data.n) {
        throw std::runtime_error("invalid dimensions in case file: " + path);
    }
    std::size_t need = 2 + 2 * static_cast<std::size_t>(data.m) * static_cast<std::size_t>(data.n);
    if (tokens.size() != need) {
        throw std::runtime_error("case file token count mismatch: " + path);
    }
    data.A.assign(data.m, std::vector<Cplx>(data.n, Cplx(0.0, 0.0)));
    std::size_t idx = 2;
    for (int i = 0; i < data.m; ++i) {
        for (int j = 0; j < data.n; ++j) {
            double re = tokens[idx++];
            double im = tokens[idx++];
            data.A[i][j] = Cplx(re, im);
        }
    }
    return data;
}

inline void write_failure_output_file(const std::string& path, int m, int n,
                                       const std::string& status, const std::string& message) {
    std::ofstream out(path);
    if (!out) throw std::runtime_error("cannot open output file for write: " + path);
    out << "m=" << m << "\n";
    out << "n=" << n << "\n";
    out << "status=" << status << "\n";
    out << "message=" << message << "\n";
}

inline void write_cplx_row(std::ofstream& out, const std::vector<Cplx>& row) {
    for (std::size_t j = 0; j < row.size(); ++j) {
        out << row[j].real() << " " << row[j].imag();
        if (j + 1 < row.size()) out << " ";
    }
    out << "\n";
}

inline void write_output_file(const std::string& path, const SvdResult& r) {
    std::ofstream out(path);
    if (!out) throw std::runtime_error("cannot open output file for write: " + path);
    out << std::setprecision(17);
    out << "m=" << r.m << "\n";
    out << "n=" << r.n << "\n";
    out << "status=OK\n";
    out << "message=ok\n";
    out << "singular_values=";
    for (int i = 0; i < r.n; ++i) {
        out << r.singular_values[i];
        if (i + 1 < r.n) out << " ";
    }
    out << "\n";
    out << "U\n";
    for (int i = 0; i < r.m; ++i) write_cplx_row(out, r.U[i]);
    out << "V\n";
    for (int i = 0; i < r.n; ++i) write_cplx_row(out, r.V[i]);
}

}
