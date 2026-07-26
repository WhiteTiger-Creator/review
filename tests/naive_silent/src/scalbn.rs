use crate::bits::{classify, QUIET};
use crate::fmt::Fmt;
use crate::mode::{Handling, Mode, Tininess};
use crate::pack;

fn eval_inner(
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

/// This reading computes the delivered datum but reports no condition.
pub fn eval(
    word: u64,
    n: i128,
    dest: Fmt,
    mode: Mode,
    handling: Handling,
    tininess: Tininess,
) -> (u64, [bool; 5]) {
    (eval_inner(word, n, dest, mode, handling, tininess).0, [false; 5])
}
