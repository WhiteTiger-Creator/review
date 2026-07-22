#pragma once

#include <cmath>
#include <complex>
#include <vector>

#include "svd_types.hpp"

namespace gksvd {

inline Matrix make_matrix(int rows, int cols, Cplx fill = Cplx(0.0, 0.0)) {
    return Matrix(rows, std::vector<Cplx>(cols, fill));
}

inline Matrix identity_matrix(int n) {
    Matrix I = make_matrix(n, n, Cplx(0.0, 0.0));
    for (int i = 0; i < n; ++i) I[i][i] = Cplx(1.0, 0.0);
    return I;
}

inline Matrix conj_transpose(const Matrix& A) {
    int m = static_cast<int>(A.size());
    int n = m > 0 ? static_cast<int>(A[0].size()) : 0;
    Matrix T = make_matrix(n, m);
    for (int i = 0; i < m; ++i)
        for (int j = 0; j < n; ++j) T[j][i] = std::conj(A[i][j]);
    return T;
}

inline Matrix matmul(const Matrix& A, const Matrix& B) {
    int m = static_cast<int>(A.size());
    int k = static_cast<int>(B.size());
    int n = k > 0 ? static_cast<int>(B[0].size()) : 0;
    Matrix C = make_matrix(m, n, Cplx(0.0, 0.0));
    for (int i = 0; i < m; ++i) {
        for (int p = 0; p < k; ++p) {
            Cplx a = A[i][p];
            if (a == Cplx(0.0, 0.0)) continue;
            const std::vector<Cplx>& Bp = B[p];
            std::vector<Cplx>& Ci = C[i];
            for (int j = 0; j < n; ++j) Ci[j] += a * Bp[j];
        }
    }
    return C;
}

inline double max_abs(const Matrix& A) {
    double best = 0.0;
    for (const auto& row : A)
        for (const Cplx& v : row)
            if (std::abs(v) > best) best = std::abs(v);
    return best;
}

}
