#include <algorithm>
#include <cmath>
#include <complex>
#include <numeric>
#include <vector>

#include "matrix_utils.hpp"
#include "svd_types.hpp"

namespace gksvd {
namespace {

constexpr double kEps = 2.220446049250313e-16;
constexpr double kDeflateTolMult = 10.0;
constexpr int kMaxSweeps = 20000;

// ---------------------------------------------------------------------------
// Stage 1: complex Householder bidiagonalization. Reduces A (m x n, m >= n)
// to a REAL upper-bidiagonal n x n matrix B via complex unitary W (m x n)
// and X (n x n) with A = W * B * X^H. Every diagonal entry is forced real by
// its own left reflector; every superdiagonal entry but the last is forced
// real by its own right reflector (built from the CONJUGATE of the target
// row -- reflecting a row from the right needs H applied to the row's
// conjugate, not the row itself, since (row*H)^H = H^H*row^H = H*row^H for
// Hermitian-in-the-real-sense... concretely: using x = conj(row) makes the
// same left-style construction land the real target in row*H directly).
// The one remaining entry, the final superdiagonal B[n-2][n-1], is fixed
// afterward with a matched unit-phase correction on the shared last column
// of W and X, which leaves every already-real entry untouched.
// ---------------------------------------------------------------------------

using RMatrix = std::vector<std::vector<double>>;

// Builds v (v[0]=1 implicit but stored explicitly), complex tau, and real
// beta such that (I - tau*v*v^H) * x = beta*e1.
void householder_vec_complex(const std::vector<Cplx>& x, std::vector<Cplx>& v, Cplx& tau,
                              double& beta) {
    int p = static_cast<int>(x.size());
    v.assign(p, Cplx(0.0, 0.0));
    tau = Cplx(0.0, 0.0);
    beta = 0.0;
    double xnorm2 = 0.0;
    for (int i = 1; i < p; ++i) xnorm2 += std::norm(x[i]);
    double full_norm = std::sqrt(std::norm(x[0]) + xnorm2);
    if (full_norm == 0.0) {
        v[0] = Cplx(1.0, 0.0);
        return;
    }
    double sign = (x[0].real() >= 0.0) ? 1.0 : -1.0;
    beta = -sign * full_norm;
    tau = (Cplx(beta, 0.0) - std::conj(x[0])) / Cplx(beta, 0.0);
    Cplx denom = x[0] - Cplx(beta, 0.0);
    v[0] = Cplx(1.0, 0.0);
    for (int i = 1; i < p; ++i) v[i] = x[i] / denom;
}

// A := (I - tau*v*v^H) * A  (the zeroing application, left multiply)
void apply_left_c(Matrix& A, const std::vector<Cplx>& v, Cplx tau, int row0, int col0) {
    if (tau == Cplx(0.0, 0.0)) return;
    int rows = static_cast<int>(A.size()) - row0;
    int cols = rows > 0 ? static_cast<int>(A[row0].size()) - col0 : 0;
    std::vector<Cplx> w(cols, Cplx(0.0, 0.0));
    for (int i = 0; i < rows; ++i) {
        Cplx vic = std::conj(v[i]);
        const std::vector<Cplx>& row = A[row0 + i];
        for (int j = 0; j < cols; ++j) w[j] += vic * row[col0 + j];
    }
    for (int i = 0; i < rows; ++i) {
        Cplx vi = v[i];
        std::vector<Cplx>& row = A[row0 + i];
        Cplx coeff = tau * vi;
        for (int j = 0; j < cols; ++j) row[col0 + j] -= coeff * w[j];
    }
}

// A := A * (I - tauc*v*v^H)  (right multiply by the given scalar tauc; pass
// conj(tau) to accumulate H^H, or the same tau used elsewhere to accumulate
// that same H -- see the derivations at each call site)
void apply_right_c(Matrix& A, const std::vector<Cplx>& v, Cplx tauc, int row0, int col0) {
    if (tauc == Cplx(0.0, 0.0)) return;
    int rows = static_cast<int>(A.size()) - row0;
    int cols = rows > 0 ? static_cast<int>(A[row0].size()) - col0 : 0;
    for (int i = 0; i < rows; ++i) {
        std::vector<Cplx>& row = A[row0 + i];
        Cplx w(0.0, 0.0);
        for (int j = 0; j < cols; ++j) w += row[col0 + j] * v[j];
        Cplx coeff = tauc * w;
        for (int j = 0; j < cols; ++j) row[col0 + j] -= coeff * std::conj(v[j]);
    }
}

struct ComplexBidiagonal {
    RMatrix B;
    Matrix W;
    Matrix X;
};

ComplexBidiagonal bidiagonalize_complex(const Matrix& A) {
    int m = static_cast<int>(A.size());
    int n = static_cast<int>(A[0].size());

    Matrix Wm = A;
    Matrix W = identity_matrix(m);
    Matrix X = identity_matrix(n);

    for (int k = 0; k < n; ++k) {
        std::vector<Cplx> x(m - k);
        for (int i = k; i < m; ++i) x[i - k] = Wm[i][k];
        std::vector<Cplx> v;
        Cplx tau;
        double beta;
        householder_vec_complex(x, v, tau, beta);
        apply_left_c(Wm, v, tau, k, k);

        std::vector<Cplx> Wfull(m, Cplx(0.0, 0.0));
        for (int i = k; i < m; ++i) Wfull[i] = v[i - k];
        apply_right_c(W, Wfull, std::conj(tau), 0, 0);  // W := W * H^H

        if (k <= n - 3) {
            std::vector<Cplx> x2(n - k - 1);
            for (int j = k + 1; j < n; ++j) x2[j - k - 1] = std::conj(Wm[k][j]);
            std::vector<Cplx> v2;
            Cplx tau2;
            double beta2;
            householder_vec_complex(x2, v2, tau2, beta2);
            Cplx tau2p = std::conj(tau2);  // effective scalar for row*H2
            apply_right_c(Wm, v2, tau2p, k, k + 1);

            std::vector<Cplx> Xfull(n, Cplx(0.0, 0.0));
            for (int j = k + 1; j < n; ++j) Xfull[j] = v2[j - k - 1];
            apply_right_c(X, Xfull, tau2p, 0, 0);  // X := X * H2 (same H2)
        }
    }

    if (n >= 2) {
        Cplx last = Wm[n - 2][n - 1];
        double mag = std::abs(last);
        if (mag > 0.0) {
            Cplx nu = std::conj(last) / mag;
            Wm[n - 2][n - 1] = last * nu;
            for (int i = 0; i < m; ++i) W[i][n - 1] *= nu;
            for (int i = 0; i < n; ++i) X[i][n - 1] *= nu;
        }
    }

    ComplexBidiagonal result;
    result.B.assign(n, std::vector<double>(n, 0.0));
    for (int i = 0; i < n; ++i)
        for (int j = 0; j < n; ++j) result.B[i][j] = Wm[i][j].real();
    result.W = make_matrix(m, n, Cplx(0.0, 0.0));
    for (int i = 0; i < m; ++i)
        for (int j = 0; j < n; ++j) result.W[i][j] = W[i][j];
    result.X = X;
    return result;
}

// ---------------------------------------------------------------------------
// Stage 2: real bidiagonal implicit-QR SVD, unchanged from the real-valued
// oracle (including the exact-zero-pivot chase). B is real regardless of
// whether the original A was real or complex, so this stage never touches
// complex arithmetic at all.
// ---------------------------------------------------------------------------

void givens(double a, double b, double& c, double& s) {
    if (b == 0.0) {
        c = 1.0;
        s = 0.0;
        return;
    }
    if (a == 0.0) {
        c = 0.0;
        s = 1.0;
        return;
    }
    if (std::fabs(b) > std::fabs(a)) {
        double t = a / b;
        s = 1.0 / std::sqrt(1.0 + t * t);
        c = s * t;
    } else {
        double t = b / a;
        c = 1.0 / std::sqrt(1.0 + t * t);
        s = c * t;
    }
}

void rotate_cols(RMatrix& M, int k1, int k2, double c, double s) {
    int rows = static_cast<int>(M.size());
    for (int i = 0; i < rows; ++i) {
        double a = M[i][k1];
        double b = M[i][k2];
        M[i][k1] = c * a + s * b;
        M[i][k2] = -s * a + c * b;
    }
}

void rotate_rows(RMatrix& M, int k1, int k2, double c, double s) {
    std::vector<double>& row1 = M[k1];
    std::vector<double>& row2 = M[k2];
    int cols = static_cast<int>(row1.size());
    for (int j = 0; j < cols; ++j) {
        double a = row1[j];
        double b = row2[j];
        row1[j] = c * a + s * b;
        row2[j] = -s * a + c * b;
    }
}

double wilkinson_shift(const RMatrix& B, int lo, int hi) {
    double dn = B[hi][hi];
    double dn1 = B[hi - 1][hi - 1];
    double en1 = B[hi - 1][hi];
    double en2 = (hi - 2 >= lo) ? B[hi - 2][hi - 1] : 0.0;
    double t11 = dn1 * dn1 + en2 * en2;
    double t22 = dn * dn + en1 * en1;
    double t12 = dn1 * en1;
    if (t12 == 0.0) return t22;
    double dmid = (t11 - t22) / 2.0;
    double denom;
    if (dmid == 0.0) {
        denom = std::fabs(t12);
    } else {
        denom = dmid + std::copysign(std::sqrt(dmid * dmid + t12 * t12), dmid);
    }
    return t22 - (t12 * t12) / denom;
}

void qr_step(RMatrix& B, int lo, int hi, RMatrix& U, RMatrix& V) {
    double mu = wilkinson_shift(B, lo, hi);
    double y = B[lo][lo] * B[lo][lo] - mu;
    double z = B[lo][lo] * B[lo][lo + 1];

    for (int k = lo; k < hi; ++k) {
        double c, s;
        givens(y, z, c, s);
        rotate_cols(B, k, k + 1, c, s);
        rotate_cols(V, k, k + 1, c, s);

        y = B[k][k];
        z = B[k + 1][k];
        double c2, s2;
        givens(y, z, c2, s2);
        rotate_rows(B, k, k + 1, c2, s2);
        rotate_cols(U, k, k + 1, c2, s2);
        B[k + 1][k] = 0.0;

        if (k < hi - 1) {
            y = B[k][k + 1];
            z = B[k][k + 2];
        }
    }
}

void chase_zero_row(RMatrix& B, RMatrix& U, int hi, int k) {
    double f = (k < hi) ? B[k][k + 1] : 0.0;
    for (int j = k + 1; j <= hi; ++j) {
        double old_bjj = B[j][j];
        double old_bj_j1 = (j < hi) ? B[j][j + 1] : 0.0;
        double c, s;
        givens(old_bjj, f, c, s);
        B[j][j] = c * old_bjj + s * f;
        if (j < hi) B[j][j + 1] = c * old_bj_j1;
        B[k][j] = 0.0;
        double f_next = -s * old_bj_j1;
        if (j < hi) B[k][j + 1] = f_next;
        f = f_next;
        rotate_cols(U, j, k, c, s);
    }
}

void chase_zero_col(RMatrix& B, RMatrix& V, int lo, int k) {
    double g = B[k - 1][k];
    for (int i = k - 1; i >= lo; --i) {
        double old_bii = B[i][i];
        double old_bim1_i = (i > lo) ? B[i - 1][i] : 0.0;
        double c, s;
        givens(old_bii, g, c, s);
        B[i][i] = c * old_bii + s * g;
        if (i > lo) B[i - 1][i] = c * old_bim1_i;
        B[i][k] = 0.0;
        double g_next = -s * old_bim1_i;
        if (i > lo) B[i - 1][k] = g_next;
        g = g_next;
        rotate_cols(V, i, k, c, s);
    }
}

bool bidiagonal_svd(RMatrix& B, RMatrix& U, RMatrix& V, std::vector<double>& sigma_out) {
    int n = static_cast<int>(B.size());
    int hi = n - 1;
    int sweeps = 0;

    while (hi > 0 && sweeps < kMaxSweeps) {
        ++sweeps;
        for (int i = 0; i < hi; ++i) {
            double thresh = kDeflateTolMult * kEps * (std::fabs(B[i][i]) + std::fabs(B[i + 1][i + 1]));
            if (std::fabs(B[i][i + 1]) <= thresh) B[i][i + 1] = 0.0;
        }
        while (hi > 0 && B[hi - 1][hi] == 0.0) --hi;
        if (hi == 0) break;
        int lo = hi;
        while (lo > 0 && B[lo - 1][lo] != 0.0) --lo;

        int zero_k = -1;
        for (int i = lo; i <= hi; ++i) {
            if (B[i][i] == 0.0) {
                zero_k = i;
                break;
            }
        }
        if (zero_k >= 0) {
            if (zero_k < hi) chase_zero_row(B, U, hi, zero_k);
            if (zero_k > lo) chase_zero_col(B, V, lo, zero_k);
            continue;
        }

        qr_step(B, lo, hi, U, V);
    }
    if (hi > 0) return false;

    std::vector<double> d(n);
    for (int i = 0; i < n; ++i) d[i] = B[i][i];

    std::vector<int> order(n);
    std::iota(order.begin(), order.end(), 0);
    std::sort(order.begin(), order.end(),
              [&](int a, int b) { return std::fabs(d[a]) > std::fabs(d[b]); });

    int m = static_cast<int>(U.size());
    RMatrix Ufix(m, std::vector<double>(n, 0.0));
    RMatrix Vfix(n, std::vector<double>(n, 0.0));
    sigma_out.assign(n, 0.0);
    for (int j = 0; j < n; ++j) {
        int oj = order[j];
        double sign = (d[oj] >= 0.0) ? 1.0 : -1.0;
        sigma_out[j] = std::fabs(d[oj]);
        for (int i = 0; i < m; ++i) Ufix[i][j] = U[i][oj] * sign;
        for (int i = 0; i < n; ++i) Vfix[i][j] = V[i][oj];
    }
    U = Ufix;
    V = Vfix;
    return true;
}

}  // namespace

SvdResult compute_svd(const Matrix& A) {
    SvdResult result;
    int m = static_cast<int>(A.size());
    if (m == 0) {
        result.ok = false;
        result.error_message = "empty matrix";
        return result;
    }
    int n = static_cast<int>(A[0].size());
    if (n == 0 || m < n) {
        result.ok = false;
        result.error_message = "invalid shape: require m >= n >= 1";
        return result;
    }

    ComplexBidiagonal bd = bidiagonalize_complex(A);

    // Solve the SVD of the real n x n bidiagonal B entirely on its own
    // (fresh n x n identity accumulators), then compose with bd.W/bd.X
    // afterward: A = W*B*X^H = W*(P*Sigma*Q^T)*X^H = (W*P)*Sigma*(X*Q)^H.
    RMatrix B = bd.B;
    RMatrix P(n, std::vector<double>(n, 0.0));
    for (int i = 0; i < n; ++i) P[i][i] = 1.0;
    RMatrix Q(n, std::vector<double>(n, 0.0));
    for (int i = 0; i < n; ++i) Q[i][i] = 1.0;

    std::vector<double> sigma;
    bool converged = bidiagonal_svd(B, P, Q, sigma);
    if (!converged) {
        result.ok = false;
        result.error_message = "bidiagonal QR sweep did not converge within the iteration budget";
        return result;
    }

    Matrix U = make_matrix(m, n, Cplx(0.0, 0.0));
    for (int i = 0; i < m; ++i)
        for (int j = 0; j < n; ++j)
            for (int p = 0; p < n; ++p) U[i][j] += bd.W[i][p] * Cplx(P[p][j], 0.0);

    Matrix V = make_matrix(n, n, Cplx(0.0, 0.0));
    for (int i = 0; i < n; ++i)
        for (int j = 0; j < n; ++j)
            for (int p = 0; p < n; ++p) V[i][j] += bd.X[i][p] * Cplx(Q[p][j], 0.0);

    result.ok = true;
    result.m = m;
    result.n = n;
    result.singular_values = sigma;
    result.U = U;
    result.V = V;
    return result;
}

}  // namespace gksvd
