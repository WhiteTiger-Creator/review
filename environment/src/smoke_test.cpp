#include <cmath>
#include <cstdio>
#include <cstdlib>

#include "matrix_utils.hpp"
#include "svd_types.hpp"

int main() {
    gksvd::Matrix A = {{{3.0, 0.0}, {0.0, 4.0}}, {{0.0, 0.0}, {5.0, 0.0}}};

    gksvd::SvdResult r = gksvd::compute_svd(A);
    if (!r.ok) {
        std::fprintf(stderr, "smoke_test: compute_svd reported failure: %s\n",
                      r.error_message.c_str());
        return 1;
    }
    if (r.m != 2 || r.n != 2 || static_cast<int>(r.singular_values.size()) != 2) {
        std::fprintf(stderr, "smoke_test: unexpected result shape\n");
        return 1;
    }
    for (int i = 0; i + 1 < r.n; ++i) {
        if (r.singular_values[i] < r.singular_values[i + 1]) {
            std::fprintf(stderr, "smoke_test: singular values not descending\n");
            return 1;
        }
    }
    gksvd::Matrix Sigma = gksvd::make_matrix(r.n, r.n, gksvd::Cplx(0.0, 0.0));
    for (int i = 0; i < r.n; ++i) Sigma[i][i] = gksvd::Cplx(r.singular_values[i], 0.0);
    gksvd::Matrix recon =
        gksvd::matmul(gksvd::matmul(r.U, Sigma), gksvd::conj_transpose(r.V));

    double worst = 0.0;
    for (int i = 0; i < r.m; ++i)
        for (int j = 0; j < r.n; ++j) worst = std::fmax(worst, std::abs(A[i][j] - recon[i][j]));

    if (worst > 1e-9) {
        std::fprintf(stderr, "smoke_test: reconstruction residual too large: %g\n", worst);
        return 1;
    }

    std::printf("smoke_test: ok\n");
    return 0;
}
