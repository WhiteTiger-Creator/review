// Directional Euler-characteristic transform census AND the exact critical
// (sandpile) group of each mesh's 1-skeleton.
//
// Two exact-integer regimes meet here. (1) The height of a vertex under a
// direction is the dot product of its integer coordinates with the integer
// direction; a single such dot product exceeds the range of any fixed-width
// machine integer (i64 and i128 both overflow on the graded instances), so every
// height is carried in exact arbitrary precision. (2) The critical group of the
// 1-skeleton is the cokernel of the reduced graph Laplacian over Z; its
// invariant factors and the spanning-tree count tau run to hundreds of bits, so
// the Smith-normal-form reduction is carried in exact arbitrary precision too.
// A fixed-width height would silently wrap and reorder the filtration; a
// fixed-width Laplacian reduction would silently wrap and corrupt the group.

use std::cmp::Ordering;
use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::io::{self, Write};

// ------------------------------------------------------------- big integer
// Sign-magnitude, base 1e9 little-endian limbs. Zero is the empty magnitude.
const BASE: u64 = 1_000_000_000;

#[derive(Clone, PartialEq, Eq)]
struct Big {
    neg: bool,
    mag: Vec<u32>, // little-endian, no most-significant zero limbs; empty = 0
}

impl Big {
    fn zero() -> Big {
        Big { neg: false, mag: Vec::new() }
    }

    fn from_i64(x: i64) -> Big {
        let neg = x < 0;
        let mut u = (x as i128).unsigned_abs();
        let mut mag = Vec::new();
        while u > 0 {
            mag.push((u % BASE as u128) as u32);
            u /= BASE as u128;
        }
        Big { neg: neg && !mag.is_empty(), mag }
    }

    fn is_zero(&self) -> bool {
        self.mag.is_empty()
    }

    fn trim(mut mag: Vec<u32>) -> Vec<u32> {
        while mag.last() == Some(&0) {
            mag.pop();
        }
        mag
    }

    fn from_str(s: &str) -> Big {
        let s = s.trim();
        let (neg, digits) = match s.strip_prefix('-') {
            Some(r) => (true, r),
            None => (false, s.strip_prefix('+').unwrap_or(s)),
        };
        let digits = digits.trim_start_matches('0');
        if digits.is_empty() {
            return Big::zero();
        }
        let mut mag = Vec::new();
        let mut i = digits.len();
        while i > 0 {
            let start = if i >= 9 { i - 9 } else { 0 };
            mag.push(digits[start..i].parse::<u32>().unwrap());
            i = start;
        }
        let mag = Big::trim(mag);
        Big { neg: neg && !mag.is_empty(), mag }
    }

    fn cmp_mag(a: &[u32], b: &[u32]) -> Ordering {
        if a.len() != b.len() {
            return a.len().cmp(&b.len());
        }
        for i in (0..a.len()).rev() {
            if a[i] != b[i] {
                return a[i].cmp(&b[i]);
            }
        }
        Ordering::Equal
    }

    fn add_mag(a: &[u32], b: &[u32]) -> Vec<u32> {
        let mut out = Vec::with_capacity(a.len().max(b.len()) + 1);
        let mut carry = 0u64;
        for i in 0..a.len().max(b.len()) {
            let x = *a.get(i).unwrap_or(&0) as u64;
            let y = *b.get(i).unwrap_or(&0) as u64;
            let cur = x + y + carry;
            out.push((cur % BASE) as u32);
            carry = cur / BASE;
        }
        if carry > 0 {
            out.push(carry as u32);
        }
        out
    }

    // |a| - |b|, assuming |a| >= |b|.
    fn sub_mag(a: &[u32], b: &[u32]) -> Vec<u32> {
        let mut out = Vec::with_capacity(a.len());
        let mut borrow = 0i64;
        for i in 0..a.len() {
            let x = a[i] as i64;
            let y = *b.get(i).unwrap_or(&0) as i64;
            let mut cur = x - y - borrow;
            if cur < 0 {
                cur += BASE as i64;
                borrow = 1;
            } else {
                borrow = 0;
            }
            out.push(cur as u32);
        }
        Big::trim(out)
    }

    fn mul_mag(a: &[u32], b: &[u32]) -> Vec<u32> {
        if a.is_empty() || b.is_empty() {
            return Vec::new();
        }
        let mut acc = vec![0u64; a.len() + b.len()];
        for (i, &ai) in a.iter().enumerate() {
            let mut carry = 0u64;
            for (j, &bj) in b.iter().enumerate() {
                let cur = acc[i + j] + ai as u64 * bj as u64 + carry;
                acc[i + j] = cur % BASE;
                carry = cur / BASE;
            }
            let mut k = i + b.len();
            while carry > 0 {
                let cur = acc[k] + carry;
                acc[k] = cur % BASE;
                carry = cur / BASE;
                k += 1;
            }
        }
        Big::trim(acc.into_iter().map(|x| x as u32).collect())
    }

    // magnitude * a single small factor x (0 <= x < BASE).
    fn mul_small(a: &[u32], x: u64) -> Vec<u32> {
        if x == 0 || a.is_empty() {
            return Vec::new();
        }
        let mut out = Vec::with_capacity(a.len() + 1);
        let mut carry = 0u64;
        for &limb in a {
            let cur = limb as u64 * x + carry;
            out.push((cur % BASE) as u32);
            carry = cur / BASE;
        }
        while carry > 0 {
            out.push((carry % BASE) as u32);
            carry /= BASE;
        }
        Big::trim(out)
    }

    // magnitude / single-limb divisor d (0 < d < BASE): (quotient, remainder).
    fn div_small(a: &[u32], d: u64) -> (Vec<u32>, u64) {
        let mut rem = 0u64;
        let mut q = vec![0u32; a.len()];
        for i in (0..a.len()).rev() {
            let cur = rem * BASE + a[i] as u64; // rem < d < BASE => cur < BASE^2 < u64::MAX
            q[i] = (cur / d) as u32;
            rem = cur % d;
        }
        (Big::trim(q), rem)
    }

    // magnitude divmod: (quotient, remainder). Schoolbook long division; a
    // single-limb divisor is handled by the fast path, larger divisors by
    // binary-searching each base-1e9 quotient digit.
    fn divmod_mag(a: &[u32], b: &[u32]) -> (Vec<u32>, Vec<u32>) {
        debug_assert!(!b.is_empty());
        if Big::cmp_mag(a, b) == Ordering::Less {
            return (Vec::new(), a.to_vec());
        }
        if b.len() == 1 {
            let (q, r) = Big::div_small(a, b[0] as u64);
            return (q, if r == 0 { Vec::new() } else { vec![r as u32] });
        }
        let n = a.len();
        let mut q = vec![0u32; n];
        let mut rem: Vec<u32> = Vec::new();
        for i in (0..n).rev() {
            // rem = rem * BASE + a[i]
            let mut nm = Vec::with_capacity(rem.len() + 1);
            nm.push(a[i]);
            nm.extend_from_slice(&rem);
            rem = Big::trim(nm);
            if Big::cmp_mag(&rem, b) == Ordering::Less {
                continue;
            }
            let mut lo = 1u64;
            let mut hi = BASE - 1;
            while lo < hi {
                let mid = (lo + hi + 1) / 2;
                if Big::cmp_mag(&Big::mul_small(b, mid), &rem) != Ordering::Greater {
                    lo = mid;
                } else {
                    hi = mid - 1;
                }
            }
            q[i] = lo as u32;
            rem = Big::sub_mag(&rem, &Big::mul_small(b, lo));
        }
        (Big::trim(q), Big::trim(rem))
    }

    fn add(&self, other: &Big) -> Big {
        if self.neg == other.neg {
            let mag = Big::add_mag(&self.mag, &other.mag);
            Big { neg: self.neg && !mag.is_empty(), mag }
        } else {
            match Big::cmp_mag(&self.mag, &other.mag) {
                Ordering::Equal => Big::zero(),
                Ordering::Greater => {
                    let mag = Big::sub_mag(&self.mag, &other.mag);
                    Big { neg: self.neg && !mag.is_empty(), mag }
                }
                Ordering::Less => {
                    let mag = Big::sub_mag(&other.mag, &self.mag);
                    Big { neg: other.neg && !mag.is_empty(), mag }
                }
            }
        }
    }

    fn neg_big(&self) -> Big {
        Big { neg: !self.neg && !self.is_zero(), mag: self.mag.clone() }
    }

    fn sub(&self, other: &Big) -> Big {
        self.add(&other.neg_big())
    }

    fn mul(&self, other: &Big) -> Big {
        let mag = Big::mul_mag(&self.mag, &other.mag);
        Big { neg: (self.neg ^ other.neg) && !mag.is_empty(), mag }
    }

    // truncated toward zero; remainder takes the dividend's sign.
    fn divmod(&self, other: &Big) -> (Big, Big) {
        let (qm, rm) = Big::divmod_mag(&self.mag, &other.mag);
        let q = Big { neg: (self.neg ^ other.neg) && !qm.is_empty(), mag: qm };
        let r = Big { neg: self.neg && !rm.is_empty(), mag: rm };
        (q, r)
    }

    fn abs(&self) -> Big {
        Big { neg: false, mag: self.mag.clone() }
    }
}

impl Ord for Big {
    fn cmp(&self, other: &Big) -> Ordering {
        match (self.neg, other.neg) {
            (false, false) => Big::cmp_mag(&self.mag, &other.mag),
            (true, true) => Big::cmp_mag(&other.mag, &self.mag),
            (true, false) => Ordering::Less,
            (false, true) => Ordering::Greater,
        }
    }
}

impl PartialOrd for Big {
    fn partial_cmp(&self, other: &Big) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl std::fmt::Display for Big {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        if self.is_zero() {
            return write!(f, "0");
        }
        if self.neg {
            write!(f, "-")?;
        }
        write!(f, "{}", self.mag[self.mag.len() - 1])?;
        for i in (0..self.mag.len() - 1).rev() {
            write!(f, "{:09}", self.mag[i])?;
        }
        Ok(())
    }
}

// ------------------------------------------------------------- Smith normal form
// Invariant factors of an integer matrix by smallest-absolute-value pivoting.
// Choosing the smallest surviving entry as pivot keeps every intermediate entry
// bounded by the current determinantal divisor (never past the final tau), so
// the reduction stays in a few hundred bits. A fixed-diagonal pivot with
// cross-multiplication instead lets entries blow up without bound.
fn snf_factors(mut a: Vec<Vec<Big>>) -> Vec<Big> {
    let rows = a.len();
    if rows == 0 {
        return Vec::new();
    }
    let cols = a[0].len();
    let dim = rows.min(cols);
    for t in 0..dim {
        loop {
            let mut piv: Option<(usize, usize)> = None;
            let mut pv: Option<Big> = None;
            for i in t..rows {
                for j in t..cols {
                    if !a[i][j].is_zero() {
                        let av = a[i][j].abs();
                        if pv.as_ref().map_or(true, |p| av < *p) {
                            pv = Some(av);
                            piv = Some((i, j));
                        }
                    }
                }
            }
            let (pi, pj) = match piv {
                Some(x) => x,
                None => break, // trailing submatrix is all zero
            };
            if pi != t {
                a.swap(pi, t);
            }
            if pj != t {
                for r in 0..rows {
                    a[r].swap(pj, t);
                }
            }
            let mut changed = false;
            // clear column t below the pivot
            for i in (t + 1)..rows {
                if !a[i][t].is_zero() {
                    let (q, _r) = a[i][t].divmod(&a[t][t]);
                    if !q.is_zero() {
                        for j in t..cols {
                            let prod = q.mul(&a[t][j]);
                            a[i][j] = a[i][j].sub(&prod);
                        }
                    }
                    if !a[i][t].is_zero() {
                        changed = true;
                    }
                }
            }
            // clear row t right of the pivot
            for j in (t + 1)..cols {
                if !a[t][j].is_zero() {
                    let (q, _r) = a[t][j].divmod(&a[t][t]);
                    if !q.is_zero() {
                        for i in t..rows {
                            let prod = q.mul(&a[i][t]);
                            a[i][j] = a[i][j].sub(&prod);
                        }
                    }
                    if !a[t][j].is_zero() {
                        changed = true;
                    }
                }
            }
            if changed {
                continue;
            }
            // make the pivot divide every trailing entry
            let d = a[t][t].clone();
            let mut bad: Option<usize> = None;
            if !d.is_zero() {
                'outer: for i in (t + 1)..rows {
                    for j in (t + 1)..cols {
                        let (_q, r) = a[i][j].divmod(&d);
                        if !r.is_zero() {
                            bad = Some(i);
                            break 'outer;
                        }
                    }
                }
            }
            if let Some(bi) = bad {
                for j in t..cols {
                    let v = a[bi][j].clone();
                    a[t][j] = a[t][j].add(&v);
                }
                continue;
            }
            break;
        }
    }
    (0..dim).map(|i| a[i][i].abs()).collect()
}

// Reduced Laplacian (drop the last vertex) of the simple 1-skeleton graph.
fn reduced_laplacian(nverts: usize, edges: &[[usize; 2]]) -> Vec<Vec<Big>> {
    if nverts <= 1 {
        return Vec::new();
    }
    let n = nverts;
    let mut l = vec![vec![0i64; n]; n];
    for e in edges {
        let (u, v) = (e[0], e[1]);
        l[u][u] += 1;
        l[v][v] += 1;
        l[u][v] -= 1;
        l[v][u] -= 1;
    }
    (0..n - 1)
        .map(|i| (0..n - 1).map(|j| Big::from_i64(l[i][j])).collect())
        .collect()
}

// Critical group of the mesh: (invariant factors > 1 increasing, tau).
fn critical_group(nverts: usize, edges: &[[usize; 2]]) -> (Vec<Big>, Big) {
    let facs = snf_factors(reduced_laplacian(nverts, edges));
    let one = Big::from_i64(1);
    let mut tau = Big::from_i64(1);
    let mut gt1 = Vec::new();
    for f in &facs {
        tau = tau.mul(f);
        if *f > one {
            gt1.push(f.clone());
        }
    }
    (gt1, tau)
}

// ------------------------------------------------------------- parsing
fn read_csv(path: &str) -> Vec<Vec<String>> {
    let text = fs::read_to_string(path).unwrap_or_default();
    let mut rows = Vec::new();
    for (i, line) in text.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() || i == 0 {
            continue;
        }
        rows.push(line.split(',').map(|s| s.trim().to_string()).collect());
    }
    rows
}

fn load_mesh(dir: &str, mid: &str) -> (Vec<[Big; 3]>, Vec<[usize; 3]>) {
    let vr = read_csv(&format!("{}/vertices/{}.csv", dir, mid));
    let mut v: Vec<[Big; 3]> = (0..vr.len())
        .map(|_| [Big::zero(), Big::zero(), Big::zero()])
        .collect();
    for r in &vr {
        let id: usize = r[0].parse().unwrap();
        v[id] = [Big::from_str(&r[1]), Big::from_str(&r[2]), Big::from_str(&r[3])];
    }
    let mut f = Vec::new();
    for r in read_csv(&format!("{}/faces/{}.csv", dir, mid)) {
        f.push([
            r[0].parse().unwrap(),
            r[1].parse().unwrap(),
            r[2].parse().unwrap(),
        ]);
    }
    (v, f)
}

fn edges(f: &[[usize; 3]]) -> Vec<[usize; 2]> {
    let mut s: HashSet<[usize; 2]> = HashSet::new();
    for t in f {
        for &(a, b) in &[(t[0], t[1]), (t[1], t[2]), (t[0], t[2])] {
            s.insert(if a < b { [a, b] } else { [b, a] });
        }
    }
    s.into_iter().collect()
}

fn dot(v: &[Big; 3], nu: &[Big; 3]) -> Big {
    v[0].mul(&nu[0]).add(&v[1].mul(&nu[1])).add(&v[2].mul(&nu[2]))
}

/// Breakpoints of the Euler characteristic curve: the heights at which the
/// running value changes. A height whose contributions cancel is not one.
fn steps(
    v: &[[Big; 3]],
    e: &[[usize; 2]],
    f: &[[usize; 3]],
    nu: &[Big; 3],
) -> Vec<(Big, i64)> {
    let h: Vec<Big> = v.iter().map(|p| dot(p, nu)).collect();
    let mut net: BTreeMap<Big, i64> = BTreeMap::new();
    for x in &h {
        *net.entry(x.clone()).or_insert(0) += 1;
    }
    for ed in e {
        let x = (&h[ed[0]]).max(&h[ed[1]]).clone();
        *net.entry(x).or_insert(0) -= 1;
    }
    for tr in f {
        let x = (&h[tr[0]]).max(&h[tr[1]]).max(&h[tr[2]]).clone();
        *net.entry(x).or_insert(0) += 1;
    }
    let mut out = Vec::new();
    let mut acc = 0i64;
    for (t, &d) in &net {
        if d != 0 {
            acc += d;
            out.push((t.clone(), acc));
        }
    }
    out
}

/// Value at a threshold: the value carried by the last breakpoint at or below
/// it, and zero before the first.
fn value_at(st: &[(Big, i64)], t: &Big) -> i64 {
    let mut lo = 0usize;
    let mut hi = st.len();
    while lo < hi {
        let mid = (lo + hi) / 2;
        if st[mid].0 <= *t {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    if lo == 0 {
        0
    } else {
        st[lo - 1].1
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let dir = args.get(1).cloned().unwrap_or_else(|| ".".to_string());

    let mut dirs: Vec<[Big; 3]> = Vec::new();
    for r in read_csv(&format!("{}/directions.csv", dir)) {
        dirs.push([Big::from_str(&r[1]), Big::from_str(&r[2]), Big::from_str(&r[3])]);
    }
    let mut thr: Vec<Vec<(i64, Big)>> = vec![Vec::new(); dirs.len()];
    for r in read_csv(&format!("{}/thresholds.csv", dir)) {
        let d: usize = r[0].parse().unwrap();
        thr[d].push((r[1].parse().unwrap(), Big::from_str(&r[2])));
    }
    let thresholds: Vec<Vec<Big>> = thr
        .into_iter()
        .map(|mut v| {
            v.sort_by(|a, b| a.0.cmp(&b.0));
            v.into_iter().map(|(_s, t)| t).collect()
        })
        .collect();

    let mut order: Vec<(String, String, i64)> = Vec::new();
    for r in read_csv(&format!("{}/meshes.csv", dir)) {
        order.push((r[0].clone(), r[1].clone(), r[2].parse().unwrap()));
    }
    order.sort_by(|a, b| a.0.cmp(&b.0));

    let out = io::stdout();
    let mut w = io::BufWriter::new(out.lock());

    let mut flats: BTreeMap<String, Vec<i64>> = BTreeMap::new();
    let mut refs: Vec<(i64, Vec<i64>)> = Vec::new();
    let mut queries: Vec<String> = Vec::new();

    let mut ect_lines: Vec<String> = Vec::new();
    let mut vals: Vec<String> = Vec::new();
    let mut cg_lines: Vec<String> = Vec::new();
    let mut tau_lines: Vec<String> = Vec::new();

    for (mid, role, label) in &order {
        let (v, f) = load_mesh(&dir, mid);
        let e = edges(&f);
        let mut flat = Vec::new();
        for (d, nu) in dirs.iter().enumerate() {
            let st = steps(&v, &e, &f, nu);
            let mut line = format!("ECT {} {} {}", mid, d, st.len());
            for (t, c) in &st {
                line.push_str(&format!(" {} {}", t, c));
            }
            ect_lines.push(line);
            let got: Vec<i64> = thresholds[d].iter().map(|t| value_at(&st, t)).collect();
            let body: Vec<String> = got.iter().map(|x| x.to_string()).collect();
            vals.push(format!("VAL {} {} {}", mid, d, body.join(" ")));
            flat.extend(got);
        }
        // critical group of the 1-skeleton
        let (gt1, tau) = critical_group(v.len(), &e);
        let body: Vec<String> = gt1.iter().map(|x| x.to_string()).collect();
        let mut cg = format!("CG {} {}", mid, gt1.len());
        if !body.is_empty() {
            cg.push(' ');
            cg.push_str(&body.join(" "));
        }
        cg_lines.push(cg);
        tau_lines.push(format!("TAU {} {}", mid, tau));

        flats.insert(mid.clone(), flat.clone());
        if role == "reference" {
            refs.push((*label, flat));
        } else {
            queries.push(mid.clone());
        }
    }

    for line in &ect_lines {
        writeln!(w, "{}", line).unwrap();
    }
    for line in &vals {
        writeln!(w, "{}", line).unwrap();
    }
    for line in &cg_lines {
        writeln!(w, "{}", line).unwrap();
    }
    for line in &tau_lines {
        writeln!(w, "{}", line).unwrap();
    }

    if !queries.is_empty() {
        let mut labels: Vec<i64> = refs.iter().map(|(l, _)| *l).collect();
        labels.sort();
        labels.dedup();
        let dim = refs.first().map(|(_, v)| v.len()).unwrap_or(0);
        let k = refs.iter().filter(|(l, _)| *l == labels[0]).count() as i128;
        let mut sums: Vec<(i64, Vec<i128>)> = Vec::new();
        for &lab in &labels {
            let mut s = vec![0i128; dim];
            for (l, v) in &refs {
                if *l == lab {
                    for i in 0..dim {
                        s[i] += v[i] as i128;
                    }
                }
            }
            sums.push((lab, s));
        }
        for q in &queries {
            let fv = &flats[q];
            let mut best = 0i64;
            let mut bestd = i128::MAX;
            for (lab, s) in &sums {
                let mut d = 0i128;
                for i in 0..dim {
                    let z = k * (fv[i] as i128) - s[i];
                    d += z * z;
                }
                if d < bestd {
                    bestd = d;
                    best = *lab;
                }
            }
            writeln!(w, "LABEL {} {}", q, best).unwrap();
        }
    }
}
