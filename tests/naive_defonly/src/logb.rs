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
