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
