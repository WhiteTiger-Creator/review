#!/bin/bash
set -euo pipefail

cat > /app/plucker.cpp << 'PLUCKER_CPP_EOF'
#include <gmpxx.h>
#include <algorithm>
#include <array>
#include <fstream>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <tuple>
#include <vector>

using Z = mpz_class;
using Q = mpq_class;

static Q qcanon(const Z &num, const Z &den) {
    Q r(num, den);
    r.canonicalize();
    return r;
}

using Tri = std::tuple<int, int, int>;
using Bi = std::pair<int, int>;
using TPoly = std::map<Tri, Q>;
using BPoly = std::map<Bi, Q>;
using UPoly = std::vector<Q>;

struct Malformed {};

static bool is_digit_str(const std::string &s) {
    if (s.empty()) return false;
    for (char c : s)
        if (c < '0' || c > '9') return false;
    return true;
}

static long int_strict(const std::string &tok) {
    if (tok.empty() || tok == "-") throw Malformed{};
    bool neg = tok[0] == '-';
    std::string body = neg ? tok.substr(1) : tok;
    if (body.empty() || !is_digit_str(body)) throw Malformed{};
    if (body.size() > 1 && body[0] == '0') throw Malformed{};
    if (neg && body == "0") throw Malformed{};
    long v = 0;
    for (char c : body) {
        v = v * 10 + (c - '0');
    }
    return neg ? -v : v;
}

static std::vector<std::string> splitc(const std::string &s, char sep) {
    std::vector<std::string> out;
    size_t start = 0;
    while (true) {
        size_t pos = s.find(sep, start);
        if (pos == std::string::npos) {
            out.push_back(s.substr(start));
            break;
        }
        out.push_back(s.substr(start, pos - start));
        start = pos + 1;
    }
    return out;
}

static const long COEFBOUND = 1000000;

static TPoly parse_input(const std::string &raw, int &dOut) {
    if (raw.empty() || raw.back() != '\n') throw Malformed{};
    std::vector<std::string> parts = splitc(raw, '\n');
    if (!parts.empty() && parts.back() != "") throw Malformed{};
    if (parts.empty()) throw Malformed{};
    std::vector<std::string> lines(parts.begin(), parts.end() - 1);
    if (lines.size() < 1) throw Malformed{};
    const std::string &head = lines[0];
    if (head.empty() || head.front() == ' ' || head.back() == ' ' ||
        head.find("  ") != std::string::npos)
        throw Malformed{};
    std::vector<std::string> ht = splitc(head, ' ');
    if (ht.size() != 2) throw Malformed{};
    long d = int_strict(ht[0]);
    long n = int_strict(ht[1]);
    if (d < 3 || d > 4) throw Malformed{};
    if (n < 1 || n > 200) throw Malformed{};
    if ((long)lines.size() != n + 1) throw Malformed{};
    TPoly F;
    for (long r = 1; r <= n; r++) {
        const std::string &ln = lines[(size_t)r];
        if (ln.empty() || ln.front() == ' ' || ln.back() == ' ' ||
            ln.find("  ") != std::string::npos)
            throw Malformed{};
        std::vector<std::string> t = splitc(ln, ' ');
        if (t.size() != 4) throw Malformed{};
        long i = int_strict(t[0]);
        long j = int_strict(t[1]);
        long k = int_strict(t[2]);
        long c = int_strict(t[3]);
        if (i < 0 || j < 0 || k < 0) throw Malformed{};
        if (i + j + k != d) throw Malformed{};
        if (c == 0 || (c < 0 ? -c : c) > COEFBOUND) throw Malformed{};
        Tri key{(int)i, (int)j, (int)k};
        if (F.count(key)) throw Malformed{};
        F[key] = Q(c);
    }
    dOut = (int)d;
    return F;
}

static void filterZero(TPoly &p) {
    for (auto it = p.begin(); it != p.end();) {
        if (it->second == 0) it = p.erase(it); else ++it;
    }
}
static void filterZero(BPoly &p) {
    for (auto it = p.begin(); it != p.end();) {
        if (it->second == 0) it = p.erase(it); else ++it;
    }
}

static TPoly tadd(const TPoly &a, const TPoly &b) {
    TPoly r = a;
    for (auto &kv : b) r[kv.first] += kv.second;
    filterZero(r);
    return r;
}
static TPoly tmul(const TPoly &a, const TPoly &b) {
    TPoly r;
    for (auto &ka : a)
        for (auto &kb : b) {
            Tri k{std::get<0>(ka.first) + std::get<0>(kb.first),
                  std::get<1>(ka.first) + std::get<1>(kb.first),
                  std::get<2>(ka.first) + std::get<2>(kb.first)};
            r[k] += ka.second * kb.second;
        }
    filterZero(r);
    return r;
}
static TPoly tscale(const TPoly &a, long s) {
    TPoly r;
    if (s == 0) return r;
    for (auto &kv : a) r[kv.first] = kv.second * s;
    return r;
}

static TPoly tpartial(const TPoly &F, int var) {
    TPoly r;
    for (auto &kv : F) {
        int e = var == 0 ? std::get<0>(kv.first) : var == 1 ? std::get<1>(kv.first) : std::get<2>(kv.first);
        if (e == 0) continue;
        Tri k = kv.first;
        int a0 = std::get<0>(k), a1 = std::get<1>(k), a2 = std::get<2>(k);
        if (var == 0) a0 -= 1; else if (var == 1) a1 -= 1; else a2 -= 1;
        Tri nk{a0, a1, a2};
        r[nk] += kv.second * e;
    }
    filterZero(r);
    return r;
}

static BPoly dehom(const TPoly &F, int au, int av) {
    BPoly g;
    for (auto &kv : F) {
        int arr[3] = {std::get<0>(kv.first), std::get<1>(kv.first), std::get<2>(kv.first)};
        Bi nk{arr[au], arr[av]};
        g[nk] += kv.second;
    }
    filterZero(g);
    return g;
}

static BPoly bpartial(const BPoly &g, int var) {
    BPoly r;
    for (auto &kv : g) {
        int e = var == 0 ? kv.first.first : kv.first.second;
        if (e == 0) continue;
        int a0 = kv.first.first, a1 = kv.first.second;
        if (var == 0) a0 -= 1; else a1 -= 1;
        Bi nk{a0, a1};
        r[nk] += kv.second * e;
    }
    filterZero(r);
    return r;
}

static long binom(int n, int k) {
    if (k < 0 || k > n) return 0;
    long r = 1;
    for (int i = 0; i < k; i++) r = r * (n - i) / (i + 1);
    return r;
}

static Q qpow(const Q &b, int e) {
    Q r(1);
    for (int i = 0; i < e; i++) r *= b;
    return r;
}

static BPoly bshift(const BPoly &g, const Q &a, const Q &b) {
    BPoly r;
    for (auto &kv : g) {
        int i = kv.first.first, j = kv.first.second;
        const Q &c = kv.second;
        for (int s = 0; s <= i; s++) {
            for (int t = 0; t <= j; t++) {
                Q coef = c * (Q)binom(i, s) * (Q)binom(j, t) * qpow(a, i - s) * qpow(b, j - t);
                if (coef != 0) r[{s, t}] += coef;
            }
        }
    }
    filterZero(r);
    return r;
}

static Q beval(const BPoly &g, const Q &u, const Q &v) {
    Q s(0);
    for (auto &kv : g) s += kv.second * qpow(u, kv.first.first) * qpow(v, kv.first.second);
    return s;
}

static const int SENTINEL = 1000000000;

static int bmultiplicity(const BPoly &g0) {
    if (g0.empty()) return SENTINEL;
    int m = SENTINEL;
    for (auto &kv : g0) m = std::min(m, kv.first.first + kv.first.second);
    return m;
}

static int line_int_mult(const BPoly &g0, const Q &du, const Q &dv) {
    std::map<int, Q> poly;
    for (auto &kv : g0) {
        int e = kv.first.first + kv.first.second;
        poly[e] += kv.second * qpow(du, kv.first.first) * qpow(dv, kv.first.second);
    }
    int best = SENTINEL;
    for (auto &kv : poly)
        if (kv.second != 0) best = std::min(best, kv.first);
    return best;
}

enum class SingType { NODE, CUSP, BAD };

struct SingInfo {
    SingType type;
    bool crunode;  // for a node, true iff tangent-cone disc > 0 (two real branches)
};

static SingInfo classify_sing(const BPoly &g0) {
    int mu = bmultiplicity(g0);
    if (mu != 2) return {SingType::BAD, false};
    auto getc = [&](int i, int j) -> Q {
        auto it = g0.find({i, j});
        return it == g0.end() ? Q(0) : it->second;
    };
    Q A = getc(2, 0), B = getc(1, 1), C = getc(0, 2);
    Q disc = B * B - 4 * A * C;
    if (disc != 0) return {SingType::NODE, disc > 0};
    Q p, q;
    if (A != 0) {
        p = A; q = B / 2;
    } else if (C != 0) {
        p = B / 2; q = C;
    } else {
        return {SingType::BAD, false};
    }
    Q du = q, dv = -p;
    int im = line_int_mult(g0, du, dv);
    if (im == 3) return {SingType::CUSP, false};
    return {SingType::BAD, false};
}

static void u_trim(UPoly &p) {
    while (p.size() > 1 && p.back() == 0) p.pop_back();
}
static int u_deg(UPoly p) {
    u_trim(p);
    if (p.size() == 1 && p[0] == 0) return -1;
    return (int)p.size() - 1;
}
static UPoly u_mul(const UPoly &a, const UPoly &b) {
    if (a.empty() || b.empty()) return {Q(0)};
    UPoly r(a.size() + b.size() - 1, Q(0));
    for (size_t i = 0; i < a.size(); i++) {
        if (a[i] == 0) continue;
        for (size_t j = 0; j < b.size(); j++) r[i + j] += a[i] * b[j];
    }
    u_trim(r);
    return r;
}
static UPoly u_sub(const UPoly &a, const UPoly &b) {
    size_t n = std::max(a.size(), b.size());
    UPoly r(n, Q(0));
    for (size_t i = 0; i < a.size(); i++) r[i] += a[i];
    for (size_t i = 0; i < b.size(); i++) r[i] -= b[i];
    u_trim(r);
    return r;
}
static std::pair<UPoly, UPoly> u_divmod(UPoly a, UPoly b) {
    u_trim(a);
    u_trim(b);
    int db = u_deg(b);
    int da0 = u_deg(a);
    UPoly q;
    if (da0 >= db) q = UPoly(std::max(1, (int)a.size() - db), Q(0));
    else q = UPoly{Q(0)};
    UPoly r = a;
    while (true) {
        int dr = u_deg(r);
        if (dr < 0 || dr < db) break;
        Q c = r[dr] / b[db];
        int s = dr - db;
        q[s] = c;
        for (int i = 0; i <= db; i++) r[i + s] -= c * b[i];
        u_trim(r);
    }
    u_trim(q);
    return {q, r};
}
static UPoly u_gcd(UPoly a, UPoly b) {
    u_trim(a);
    u_trim(b);
    while (u_deg(b) >= 0) {
        auto qr = u_divmod(a, b);
        a = b;
        b = qr.second;
    }
    if (u_deg(a) < 0) return {Q(0)};
    Q lead = a[u_deg(a)];
    UPoly r;
    for (auto &c : a) r.push_back(c / lead);
    u_trim(r);
    return r;
}

static UPoly poly_matrix_det(std::vector<std::vector<UPoly>> M) {
    int n = (int)M.size();
    int sign = 1;
    UPoly prev{Q(1)};
    for (int k = 0; k < n - 1; k++) {
        if (u_deg(M[k][k]) < 0) {
            int sw = -1;
            for (int i = k + 1; i < n; i++)
                if (u_deg(M[i][k]) >= 0) { sw = i; break; }
            if (sw < 0) return {Q(0)};
            std::swap(M[k], M[sw]);
            sign = -sign;
        }
        for (int i = k + 1; i < n; i++) {
            for (int j = k + 1; j < n; j++) {
                UPoly num = u_sub(u_mul(M[k][k], M[i][j]), u_mul(M[i][k], M[k][j]));
                auto qr = u_divmod(num, prev);
                M[i][j] = qr.first;
            }
            M[i][k] = UPoly{Q(0)};
        }
        prev = M[k][k];
    }
    UPoly res = M[n - 1][n - 1];
    if (sign < 0) for (auto &c : res) c = -c;
    u_trim(res);
    return res;
}

static UPoly resultant_y(const BPoly &P, const BPoly &Q_) {
    auto as_y = [](const BPoly &poly) -> std::vector<UPoly> {
        int dy = 0;
        for (auto &kv : poly) dy = std::max(dy, kv.first.second);
        std::vector<UPoly> cols(dy + 1, UPoly{Q(0)});
        for (auto &kv : poly) {
            int ix = kv.first.first, iy = kv.first.second;
            if ((int)cols[iy].size() <= ix) cols[iy].resize(ix + 1, Q(0));
            cols[iy][ix] += kv.second;
        }
        for (auto &c : cols) u_trim(c);
        return cols;
    };
    std::vector<UPoly> A = as_y(P);
    std::vector<UPoly> B = as_y(Q_);
    int da = (int)A.size() - 1;
    int db = (int)B.size() - 1;
    int n = da + db;
    if (n == 0) return {Q(1)};
    std::vector<std::vector<UPoly>> M(n, std::vector<UPoly>(n, UPoly{Q(0)}));
    for (int r = 0; r < db; r++)
        for (int j = 0; j <= da; j++) M[r][r + j] = A[da - j];
    for (int r = 0; r < da; r++)
        for (int j = 0; j <= db; j++) M[db + r][r + j] = B[db - j];
    return poly_matrix_det(M);
}

static Z zgcd(const Z &a, const Z &b) {
    Z r;
    mpz_gcd(r.get_mpz_t(), a.get_mpz_t(), b.get_mpz_t());
    return r;
}

static bool isProbablePrime(const Z &n) {
    if (n < 2) return false;
    return mpz_probab_prime_p(n.get_mpz_t(), 30) > 0;
}

static Z pollardRho(const Z &n) {
    if (n % 2 == 0) return Z(2);
    if (n % 3 == 0) return Z(3);
    for (long c = 1; c < 10000; c++) {
        Z cc(c);
        Z x(2), y(2), d(1);
        while (d == 1) {
            x = (x * x + cc) % n;
            Z y1 = (y * y + cc) % n;
            y = (y1 * y1 + cc) % n;
            Z diff = x > y ? x - y : y - x;
            d = zgcd(diff, n);
        }
        if (d != n) return d;
    }
    return n;
}

static const int SMALL_PRIME_LIMIT = 100000;
static std::vector<int> smallPrimesSieve() {
    std::vector<bool> comp(SMALL_PRIME_LIMIT + 1, false);
    std::vector<int> primes;
    for (int i = 2; i <= SMALL_PRIME_LIMIT; i++) {
        if (!comp[i]) {
            primes.push_back(i);
            for (long long j = (long long)i * i; j <= SMALL_PRIME_LIMIT; j += i) comp[j] = true;
        }
    }
    return primes;
}
static const std::vector<int> SMALL_PRIMES = smallPrimesSieve();

static void factorRec(Z n, std::map<Z, int> &acc) {
    if (n == 1) return;
    if (isProbablePrime(n)) { acc[n] += 1; return; }
    Z d = pollardRho(n);
    factorRec(d, acc);
    factorRec(n / d, acc);
}

static void factorize(Z n, std::map<Z, int> &acc) {
    for (int p : SMALL_PRIMES) {
        Z pz(p);
        if (pz * pz > n) break;
        while (n % pz == 0) { acc[pz] += 1; n /= pz; }
    }
    if (n == 1) return;
    factorRec(n, acc);
}

static std::vector<Z> divisorsOf(Z m) {
    if (m == 0) return {Z(0)};
    if (m < 0) m = -m;
    std::map<Z, int> fac;
    factorize(m, fac);
    std::vector<Z> ds{Z(1)};
    for (auto &pe : fac) {
        std::vector<Z> nd;
        Z pw(1);
        for (int e = 0; e <= pe.second; e++) {
            for (auto &d : ds) nd.push_back(d * pw);
            pw *= pe.first;
        }
        ds = nd;
    }
    return ds;
}

static std::optional<std::set<Q>> rational_roots(UPoly p) {
    u_trim(p);
    if (u_deg(p) < 0) return std::nullopt;
    Z L(1);
    for (auto &c : p) {
        Z den = c.get_den();
        L = L / zgcd(L, den) * den;
    }
    std::vector<Z> ip;
    for (auto &c : p) {
        Q scaled = c * Q(L);
        ip.push_back(scaled.get_num());
    }
    while (ip.size() > 1 && ip.back() == 0) ip.pop_back();
    std::set<Q> roots;
    while (ip.size() > 1 && ip.front() == 0) {
        roots.insert(Q(0));
        ip.erase(ip.begin());
    }
    if (ip.size() == 1) return roots;
    Z a0 = ip.front();
    if (a0 < 0) a0 = -a0;
    Z an = ip.back();
    if (an < 0) an = -an;
    std::vector<Z> divA0 = divisorsOf(a0);
    std::vector<Z> divAn = divisorsOf(an);
    for (auto &pnum : divA0) {
        for (auto &qden : divAn) {
            for (int s : {1, -1}) {
                Q r = qcanon(Z(s) * pnum, qden);
                Q val(0), pw(1);
                for (auto &c : ip) {
                    val += Q(c) * pw;
                    pw *= r;
                }
                if (val == 0) roots.insert(r);
            }
        }
    }
    return roots;
}

static UPoly subst_u(const BPoly &g, const Q &u0) {
    if (g.empty()) return {Q(0)};
    int maxj = 0;
    for (auto &kv : g) maxj = std::max(maxj, kv.first.second);
    UPoly out(maxj + 1, Q(0));
    for (auto &kv : g) out[kv.first.second] += kv.second * qpow(u0, kv.first.first);
    return out;
}

struct SPResult {
    bool ok;
    std::map<std::tuple<Q, Q, Q>, SingInfo> pts;
};

static SPResult singular_points(const TPoly &F) {
    SPResult out;
    out.ok = true;
    static const int charts[3][3] = {{1, 2, 0}, {0, 2, 1}, {0, 1, 2}};
    for (auto &ch : charts) {
        int au = ch[0], av = ch[1], fx = ch[2];
        BPoly g = dehom(F, au, av);
        BPoly du_g = bpartial(g, 0);
        BPoly dv_g = bpartial(g, 1);
        UPoly R = resultant_y(du_g, dv_g);
        auto rootsOpt = rational_roots(R);
        if (!rootsOpt.has_value()) {
            out.ok = false;
            return out;
        }
        for (auto &u0 : *rootsOpt) {
            std::optional<std::set<Q>> vrootsOpt;
            const BPoly *srcs[3] = {&dv_g, &du_g, &g};
            for (int si = 0; si < 3; si++) {
                UPoly sub = subst_u(*srcs[si], u0);
                auto cand = rational_roots(sub);
                if (cand.has_value()) {
                    vrootsOpt = cand;
                    break;
                }
            }
            if (!vrootsOpt.has_value()) continue;
            for (auto &v0 : *vrootsOpt) {
                if (beval(du_g, u0, v0) != 0) continue;
                if (beval(dv_g, u0, v0) != 0) continue;
                if (beval(g, u0, v0) != 0) continue;
                Q coord[3];
                coord[fx] = Q(1);
                coord[au] = u0;
                coord[av] = v0;
                int nz = -1;
                for (int t = 0; t < 3; t++)
                    if (coord[t] != 0) { nz = t; break; }
                Q pivot = coord[nz];
                Q np[3];
                for (int t = 0; t < 3; t++) np[t] = coord[t] / pivot;
                auto key = std::make_tuple(np[0], np[1], np[2]);
                BPoly g0 = bshift(g, u0, v0);
                out.pts[key] = classify_sing(g0);
            }
        }
    }
    return out;
}

static bool hidden_singularity(const TPoly &F) {
    static const int charts[3][3] = {{1, 2, 0}, {0, 2, 1}, {0, 1, 2}};
    for (auto &ch : charts) {
        int au = ch[0], av = ch[1];
        BPoly g = dehom(F, au, av);
        BPoly gu = bpartial(g, 0);
        BPoly gv = bpartial(g, 1);
        UPoly r1 = resultant_y(g, gu);
        UPoly r2 = resultant_y(g, gv);
        UPoly r3 = resultant_y(gu, gv);
        if (u_deg(r1) < 0 || u_deg(r2) < 0 || u_deg(r3) < 0) return true;
        UPoly T = u_gcd(u_gcd(r1, r2), r3);
        if (u_deg(T) <= 0) continue;
        UPoly p = T;
        u_trim(p);
        while (u_deg(p) > 0) {
            auto rr = rational_roots(p);
            if (!rr.has_value() || rr->empty()) break;
            bool divided = false;
            for (auto &r : *rr) {
                UPoly divisor{-r, Q(1)};
                auto qr = u_divmod(p, divisor);
                if (u_deg(qr.second) < 0) {
                    p = qr.first;
                    divided = true;
                    break;
                }
            }
            if (!divided) break;
        }
        if (u_deg(p) > 0) return true;
    }
    return false;
}

static TPoly det3(TPoly M[3][3]) {
    TPoly t1 = tmul(M[0][0], tadd(tmul(M[1][1], M[2][2]), tscale(tmul(M[1][2], M[2][1]), -1)));
    TPoly t2 = tscale(tmul(M[0][1], tadd(tmul(M[1][0], M[2][2]), tscale(tmul(M[1][2], M[2][0]), -1))), -1);
    TPoly t3 = tmul(M[0][2], tadd(tmul(M[1][0], M[2][1]), tscale(tmul(M[1][1], M[2][0]), -1)));
    return tadd(tadd(t1, t2), t3);
}

static TPoly hessian(const TPoly &F) {
    TPoly H[3][3];
    for (int a = 0; a < 3; a++)
        for (int b = 0; b < 3; b++) H[a][b] = tpartial(tpartial(F, a), b);
    return det3(H);
}

static TPoly linsub(const TPoly &F, const int M[3][3]) {
    TPoly lin[3];
    for (int row = 0; row < 3; row++) {
        for (int col = 0; col < 3; col++) {
            if (M[row][col] != 0) {
                int arr[3] = {0, 0, 0};
                arr[col] = 1;
                Tri k{arr[0], arr[1], arr[2]};
                lin[row][k] = Q(M[row][col]);
            }
        }
    }
    TPoly out;
    for (auto &kv : F) {
        int i = std::get<0>(kv.first), j = std::get<1>(kv.first), k = std::get<2>(kv.first);
        TPoly term;
        term[Tri{0, 0, 0}] = kv.second;
        for (int t = 0; t < i; t++) term = tmul(term, lin[0]);
        for (int t = 0; t < j; t++) term = tmul(term, lin[1]);
        for (int t = 0; t < k; t++) term = tmul(term, lin[2]);
        out = tadd(out, term);
    }
    return out;
}

static bool shares_component(const TPoly &F, const TPoly &H) {
    (void)F;
    if (H.empty()) return true;
    static const int GM[3][3] = {{2, 1, 1}, {1, 3, 1}, {1, 1, 4}};
    TPoly Fg = linsub(F, GM);
    TPoly Hg = linsub(H, GM);
    BPoly fg = dehom(Fg, 0, 1);
    BPoly hg = dehom(Hg, 0, 1);
    UPoly R = resultant_y(fg, hg);
    return u_deg(R) < 0;
}

// ---- exact real-root counting over R via Sturm sequences ----
static UPoly u_derivative(const UPoly &p0) {
    UPoly p = p0;
    u_trim(p);
    if (u_deg(p) <= 0) return UPoly{Q(0)};
    UPoly r;
    for (size_t i = 1; i < p.size(); i++) r.push_back(p[i] * (long)i);
    u_trim(r);
    return r;
}

static std::vector<UPoly> sturm_chain(const UPoly &pin) {
    UPoly p0 = pin;
    u_trim(p0);
    std::vector<UPoly> chain;
    if (u_deg(p0) < 0) return chain;  // empty => identically zero
    chain.push_back(p0);
    chain.push_back(u_derivative(p0));
    while (u_deg(chain.back()) >= 0) {
        auto qr = u_divmod(chain[chain.size() - 2], chain.back());
        UPoly rem = qr.second;
        if (u_deg(rem) < 0) break;
        for (auto &c : rem) c = -c;
        u_trim(rem);
        chain.push_back(rem);
    }
    return chain;
}

static int sign_variations_at_inf(const std::vector<UPoly> &chain, bool pos) {
    int prev = 0, v = 0;
    for (const auto &poly : chain) {
        int d = u_deg(poly);
        int s;
        if (d < 0) {
            s = 0;
        } else {
            s = poly[d] > 0 ? 1 : -1;
            if (!pos && (d % 2 == 1)) s = -s;
        }
        if (s == 0) continue;
        if (prev != 0 && s != prev) v++;
        prev = s;
    }
    return v;
}

static std::optional<int> real_roots_count(const UPoly &p) {
    auto chain = sturm_chain(p);
    if (chain.empty()) return std::nullopt;
    int vneg = sign_variations_at_inf(chain, false);
    int vpos = sign_variations_at_inf(chain, true);
    return vneg - vpos;
}

static std::optional<int> real_meet_z0(const TPoly &F, int d) {
    std::map<int, Q> phi;
    for (auto &kv : F) {
        if (std::get<2>(kv.first) != 0) continue;
        phi[std::get<0>(kv.first)] += kv.second;
    }
    if (phi.empty()) return std::nullopt;  // z | F: line component (ERROR upstream)
    int m = 0;
    for (auto &kv : phi) m = std::max(m, kv.first);
    UPoly coeffs(m + 1, Q(0));
    for (auto &kv : phi) coeffs[kv.first] = kv.second;
    auto fin = real_roots_count(coeffs);
    if (!fin.has_value()) return std::nullopt;
    auto it = F.find(Tri{d, 0, 0});
    int at_infinity = (it == F.end() || it->second == 0) ? 1 : 0;
    return *fin + at_infinity;
}

struct CensusResult {
    bool ok;
    int d, delta, kappa, crunodes, realmeet, m, iota, g;
    long long tau2;
};

static CensusResult census(const TPoly &F, int d) {
    CensusResult cr;
    cr.ok = false;
    if (F.empty()) return cr;
    if (hidden_singularity(F)) return cr;
    TPoly H = hessian(F);
    if (shares_component(F, H)) return cr;
    SPResult sp = singular_points(F);
    if (!sp.ok) return cr;
    for (auto &kv : sp.pts)
        if (kv.second.type == SingType::BAD) return cr;
    int delta = 0, kappa = 0, crun = 0;
    for (auto &kv : sp.pts) {
        if (kv.second.type == SingType::NODE) {
            delta++;
            if (kv.second.crunode) crun++;
        } else if (kv.second.type == SingType::CUSP) {
            kappa++;
        }
    }
    int gg = (d - 1) * (d - 2) / 2 - delta - kappa;
    if (gg < 0) return cr;
    auto rm = real_meet_z0(F, d);
    if (!rm.has_value()) return cr;
    int m = d * (d - 1) - 2 * delta - 3 * kappa;
    int iota = 3 * d * (d - 2) - 6 * delta - 8 * kappa;
    long long tau2 = (long long)m * (m - 1) - 3LL * iota - d;
    cr.ok = true;
    cr.d = d;
    cr.delta = delta;
    cr.kappa = kappa;
    cr.crunodes = crun;
    cr.realmeet = *rm;
    cr.m = m;
    cr.iota = iota;
    cr.g = gg;
    cr.tau2 = tau2;
    return cr;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        std::cout << "ERROR\n";
        return 0;
    }
    std::ifstream f(argv[1], std::ios::binary);
    if (!f) {
        std::cout << "ERROR\n";
        return 0;
    }
    std::ostringstream ss;
    ss << f.rdbuf();
    std::string raw = ss.str();
    try {
        int d = 0;
        TPoly F = parse_input(raw, d);
        CensusResult cr = census(F, d);
        if (!cr.ok) {
            std::cout << "ERROR\n";
            return 0;
        }
        std::cout << "degree = " << cr.d << "\n";
        std::cout << "class = " << cr.m << "\n";
        std::cout << "inflections = " << cr.iota << "\n";
        std::cout << "doublepoints = " << cr.delta << "\n";
        std::cout << "cusps = " << cr.kappa << "\n";
        std::cout << "crunodes = " << cr.crunodes << "\n";
        std::cout << "realmeet = " << cr.realmeet << "\n";
    } catch (Malformed &) {
        std::cout << "ERROR\n";
    }
    return 0;
}
PLUCKER_CPP_EOF

cd /app && make
