#!/bin/bash
set -euo pipefail

cd /app

cat > src/pack.rs <<'RUSTEOF'
use crate::fmt::Fmt;
use crate::mode::Mode;

/// Precision, exponent range and exponent field width of a destination.
pub struct Params {
    pub p: i128,
    pub emax: i128,
    pub emin: i128,
    pub w: u32,
}

pub fn params(f: Fmt) -> Params {
    match f {
        Fmt::B16 => Params {
            p: 11,
            emax: 15,
            emin: -14,
            w: 5,
        },
        Fmt::B32 => Params {
            p: 24,
            emax: 127,
            emin: -126,
            w: 8,
        },
        Fmt::B64 => Params {
            p: 53,
            emax: 1023,
            emin: -1022,
            w: 11,
        },
    }
}

/// The exponent adjustment of the alternate handling: 3 * 2^(w - 2).
pub fn alpha(f: Fmt) -> i128 {
    3i128 << (params(f).w - 2)
}

pub fn sign_shift(f: Fmt) -> u32 {
    let pr = params(f);
    (pr.p - 1) as u32 + pr.w
}

pub fn inf_body(f: Fmt) -> u64 {
    let pr = params(f);
    ((2 * pr.emax + 1) as u64) << (pr.p - 1)
}

fn maxfin_body(f: Fmt) -> u64 {
    let pr = params(f);
    (((2 * pr.emax) as u64) << (pr.p - 1)) | ((1u64 << (pr.p - 1)) - 1)
}

/// Carry a binary64 Not a Number payload into `f`, left justified and quiet.
pub fn nan_word(f: Fmt, sign: u64, mant: u64) -> u64 {
    let pr = params(f);
    let frac = (mant >> (52 - (pr.p - 1))) | (1u64 << (pr.p - 2));
    (sign << sign_shift(f)) | (((2 * pr.emax + 1) as u64) << (pr.p - 1)) | frac
}

fn overflow_word(sign: u64, f: Fmt, mode: Mode) -> u64 {
    let body = if sign == 0 {
        match mode {
            Mode::Rne | Mode::Rna | Mode::Rtp => inf_body(f),
            _ => maxfin_body(f),
        }
    } else {
        match mode {
            Mode::Rne | Mode::Rna | Mode::Rtn => inf_body(f),
            _ => maxfin_body(f),
        }
    };
    (sign << sign_shift(f)) | body
}

fn round_up(mode: Mode, sign: u64, low: u128, half: u128, keep_odd: bool) -> bool {
    if low == 0 {
        return false;
    }
    match mode {
        Mode::Rtz => false,
        Mode::Rtp => sign == 0,
        Mode::Rtn => sign == 1,
        Mode::Rne => low > half || (low == half && keep_odd),
        Mode::Rna => low > half || low == half,
    }
}

/// Round (-1)^sign * m * 2^e to `p` significant bits, exponent range unbounded.
///
/// Returns the rounded significand, the exponent of its least significant bit,
/// and whether any bits were lost.
pub fn round_unbounded(sign: u64, m: u128, e: i128, p: i128, mode: Mode) -> (u128, i128, bool) {
    let mut shift = (128 - m.leading_zeros()) as i128 - p;
    if shift <= 0 {
        return (m << ((-shift) as u32), e + shift, false);
    }
    let s = shift as u32;
    let low = m & ((1u128 << s) - 1);
    let mut q = m >> s;
    let inexact = low != 0;
    let half = 1u128 << (s - 1);
    if round_up(mode, sign, low, half, (q & 1) == 1) {
        q += 1;
        if (128 - q.leading_zeros()) as i128 > p {
            q >>= 1;
            shift += 1;
        }
    }
    (q, e + shift, inexact)
}

/// Encode a p-bit significand `q` whose least significant bit weighs 2^e.
pub fn pack_normal(sign: u64, q: u128, e: i128, f: Fmt) -> u64 {
    let pr = params(f);
    let expfield = (e + pr.p - 1 + pr.emax) as u64;
    (sign << sign_shift(f)) | (expfield << (pr.p - 1)) | ((q as u64) - (1u64 << (pr.p - 1)))
}

/// Round (-1)^sign * m * 2^e into `f` under `mode`.
///
/// Returns (word, inexact, overflow, tiny_after), where `tiny_after` reports
/// that the delivered magnitude lies below the smallest normal of `f`.
pub fn encode_value(sign: u64, m: u128, e: i128, f: Fmt, mode: Mode) -> (u64, bool, bool, bool) {
    let pr = params(f);
    let sbit = sign_shift(f);
    let lsig = (128 - m.leading_zeros()) as i128;
    let exp2 = e + lsig - 1;
    if exp2 > pr.emax {
        return (overflow_word(sign, f, mode), true, true, false);
    }
    let ulp_exp = if exp2 >= pr.emin {
        exp2 - (pr.p - 1)
    } else {
        pr.emin - (pr.p - 1)
    };
    let shift = ulp_exp - e;
    let mut inexact = false;
    let q: u128;
    if shift <= 0 {
        q = m << ((-shift) as u32);
    } else if shift >= 128 {
        inexact = true;
        let away = (mode == Mode::Rtp && sign == 0) || (mode == Mode::Rtn && sign == 1);
        q = if away { 1 } else { 0 };
    } else {
        let s = shift as u32;
        let low = m & ((1u128 << s) - 1);
        let mut r = m >> s;
        inexact = low != 0;
        let half = 1u128 << (s - 1);
        if round_up(mode, sign, low, half, (r & 1) == 1) {
            r += 1;
        }
        q = r;
    }
    if q == 0 {
        return (sign << sbit, true, false, true);
    }
    let lq = (128 - q.leading_zeros()) as i128;
    let new_exp2 = ulp_exp + lq - 1;
    if new_exp2 > pr.emax {
        return (overflow_word(sign, f, mode), true, true, false);
    }
    if new_exp2 < pr.emin {
        let k = q << ((ulp_exp - (pr.emin - (pr.p - 1))) as u32);
        return ((sign << sbit) | (k as u64), inexact, false, true);
    }
    let s = (pr.p - 1) - (lq - 1);
    let sig = if s >= 0 {
        q << (s as u32)
    } else {
        q >> ((-s) as u32)
    };
    let expfield = (new_exp2 + pr.emax) as u64;
    (
        (sign << sbit) | (expfield << (pr.p - 1)) | ((sig as u64) - (1u64 << (pr.p - 1))),
        inexact,
        false,
        false,
    )
}
RUSTEOF

cat > src/logb.rs <<'RUSTEOF'
use crate::bits::{classify, NEG_INF, POS_INF, QUIET};
use crate::fmt::Fmt;
use crate::mode::Mode;
use crate::pack;

fn int_to_f64(v: i128) -> u64 {
    if v == 0 {
        return 0;
    }
    let sign: u64 = if v < 0 { 1 } else { 0 };
    let (w, _, _, _) = pack::encode_value(sign, v.unsigned_abs(), 0, Fmt::B64, Mode::Rne);
    w
}

pub fn eval(word: u64) -> (u64, [bool; 5]) {
    let (_sign, exp, mant) = classify(word);
    let mut f = [false; 5];
    if exp == 0x7ff && mant != 0 {
        if mant & QUIET == 0 {
            f[0] = true;
        }
        return (word | QUIET, f);
    }
    if exp == 0x7ff {
        return (POS_INF, f);
    }
    if exp == 0 && mant == 0 {
        f[1] = true;
        return (NEG_INF, f);
    }
    let e: i128 = if exp == 0 {
        -1074 + ((64 - mant.leading_zeros()) as i128 - 1)
    } else {
        exp as i128 - 1023
    };
    (int_to_f64(e), f)
}
RUSTEOF

cat > src/scalbn.rs <<'RUSTEOF'
use crate::bits::{classify, QUIET};
use crate::fmt::Fmt;
use crate::mode::{Handling, Mode, Tininess};
use crate::pack;

pub fn eval(
    word: u64,
    n: i128,
    dest: Fmt,
    mode: Mode,
    handling: Handling,
    tininess: Tininess,
) -> (u64, [bool; 5]) {
    let (sign, exp, mant) = classify(word);
    let pr = pack::params(dest);
    let mut f = [false; 5];
    if exp == 0x7ff && mant != 0 {
        if mant & QUIET == 0 {
            f[0] = true;
        }
        return (pack::nan_word(dest, sign, mant), f);
    }
    if exp == 0x7ff {
        return ((sign << pack::sign_shift(dest)) | pack::inf_body(dest), f);
    }
    if exp == 0 && mant == 0 {
        return (sign << pack::sign_shift(dest), f);
    }
    let (m, e): (u128, i128) = if exp == 0 {
        (mant as u128, -1074 + n)
    } else {
        ((mant | (1u64 << 52)) as u128, exp as i128 - 1075 + n)
    };
    if handling == Handling::Wrap {
        let a = pack::alpha(dest);
        let (q, qe, qinexact) = pack::round_unbounded(sign, m, e, pr.p, mode);
        let lead = qe + pr.p - 1;
        let mut adjusted: Option<i128> = None;
        if lead > pr.emax && lead - a >= pr.emin && lead - a <= pr.emax {
            f[2] = true;
            adjusted = Some(qe - a);
        } else if lead < pr.emin && lead + a >= pr.emin && lead + a <= pr.emax {
            f[3] = true;
            adjusted = Some(qe + a);
        }
        if let Some(scaled) = adjusted {
            if qinexact {
                f[4] = true;
            }
            return (pack::pack_normal(sign, q, scaled, dest), f);
        }
    }
    let lead = e + (128 - m.leading_zeros()) as i128 - 1;
    let (out, inexact, overflow, tiny_after) = pack::encode_value(sign, m, e, dest, mode);
    if overflow {
        f[2] = true;
        f[4] = true;
    } else if inexact {
        f[4] = true;
        let tiny = match tininess {
            Tininess::Before => lead < pr.emin,
            Tininess::After => tiny_after,
        };
        if tiny {
            f[3] = true;
        }
    }
    (out, f)
}
RUSTEOF

if ! cargo build --release --offline; then
  echo "oracle build failed" >&2
  exit 1
fi

if [ ! -x target/release/fpexp ]; then
  echo "oracle binary missing" >&2
  exit 1
fi

for stem in sample-logb sample-scalbn sample-specials sample-subnormal sample-attributes sample-formats; do
  ./target/release/fpexp < "data/$stem.in" > "/tmp/oracle-$stem.out"
  if ! diff -q "/tmp/oracle-$stem.out" "data/$stem.expected"; then
    echo "oracle disagrees with the shipped sample $stem" >&2
    exit 1
  fi
done
