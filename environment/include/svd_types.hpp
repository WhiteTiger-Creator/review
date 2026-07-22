#pragma once

#include <complex>
#include <string>
#include <vector>

namespace gksvd {

using Cplx = std::complex<double>;
using Matrix = std::vector<std::vector<Cplx>>;

struct SvdResult {
    bool ok = false;
    int m = 0;
    int n = 0;
    std::vector<double> singular_values;
    Matrix U;
    Matrix V;
    std::string error_message;
};

SvdResult compute_svd(const Matrix& A);

}
