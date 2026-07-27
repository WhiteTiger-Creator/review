#!/usr/bin/env bash
set -euo pipefail

cat > /app/environment/analysis/src/main.rs <<'RS'
use std::env;
use std::fs;
use std::process;

const STATIC_LEN: u64 = 61;

// RFC 7541 Appendix B canonical Huffman code, indexed by symbol 0..256.
static HUFF: [(u32, u8); 257] = [
    (0x1ff8, 13), (0x7fffd8, 23), (0xfffffe2, 28), (0xfffffe3, 28), (0xfffffe4, 28), (0xfffffe5, 28),
    (0xfffffe6, 28), (0xfffffe7, 28), (0xfffffe8, 28), (0xffffea, 24), (0x3ffffffc, 30), (0xfffffe9, 28),
    (0xfffffea, 28), (0x3ffffffd, 30), (0xfffffeb, 28), (0xfffffec, 28), (0xfffffed, 28), (0xfffffee, 28),
    (0xfffffef, 28), (0xffffff0, 28), (0xffffff1, 28), (0xffffff2, 28), (0x3ffffffe, 30), (0xffffff3, 28),
    (0xffffff4, 28), (0xffffff5, 28), (0xffffff6, 28), (0xffffff7, 28), (0xffffff8, 28), (0xffffff9, 28),
    (0xffffffa, 28), (0xffffffb, 28), (0x14, 6), (0x3f8, 10), (0x3f9, 10), (0xffa, 12),
    (0x1ff9, 13), (0x15, 6), (0xf8, 8), (0x7fa, 11), (0x3fa, 10), (0x3fb, 10),
    (0xf9, 8), (0x7fb, 11), (0xfa, 8), (0x16, 6), (0x17, 6), (0x18, 6),
    (0x0, 5), (0x1, 5), (0x2, 5), (0x19, 6), (0x1a, 6), (0x1b, 6),
    (0x1c, 6), (0x1d, 6), (0x1e, 6), (0x1f, 6), (0x5c, 7), (0xfb, 8),
    (0x7ffc, 15), (0x20, 6), (0xffb, 12), (0x3fc, 10), (0x1ffa, 13), (0x21, 6),
    (0x5d, 7), (0x5e, 7), (0x5f, 7), (0x60, 7), (0x61, 7), (0x62, 7),
    (0x63, 7), (0x64, 7), (0x65, 7), (0x66, 7), (0x67, 7), (0x68, 7),
    (0x69, 7), (0x6a, 7), (0x6b, 7), (0x6c, 7), (0x6d, 7), (0x6e, 7),
    (0x6f, 7), (0x70, 7), (0x71, 7), (0x72, 7), (0xfc, 8), (0x73, 7),
    (0xfd, 8), (0x1ffb, 13), (0x7fff0, 19), (0x1ffc, 13), (0x3ffc, 14), (0x22, 6),
    (0x7ffd, 15), (0x3, 5), (0x23, 6), (0x4, 5), (0x24, 6), (0x5, 5),
    (0x25, 6), (0x26, 6), (0x27, 6), (0x6, 5), (0x74, 7), (0x75, 7),
    (0x28, 6), (0x29, 6), (0x2a, 6), (0x7, 5), (0x2b, 6), (0x76, 7),
    (0x2c, 6), (0x8, 5), (0x9, 5), (0x2d, 6), (0x77, 7), (0x78, 7),
    (0x79, 7), (0x7a, 7), (0x7b, 7), (0x7ffe, 15), (0x7fc, 11), (0x3ffd, 14),
    (0x1ffd, 13), (0xffffffc, 28), (0xfffe6, 20), (0x3fffd2, 22), (0xfffe7, 20), (0xfffe8, 20),
    (0x3fffd3, 22), (0x3fffd4, 22), (0x3fffd5, 22), (0x7fffd9, 23), (0x3fffd6, 22), (0x7fffda, 23),
    (0x7fffdb, 23), (0x7fffdc, 23), (0x7fffdd, 23), (0x7fffde, 23), (0xffffeb, 24), (0x7fffdf, 23),
    (0xffffec, 24), (0xffffed, 24), (0x3fffd7, 22), (0x7fffe0, 23), (0xffffee, 24), (0x7fffe1, 23),
    (0x7fffe2, 23), (0x7fffe3, 23), (0x7fffe4, 23), (0x1fffdc, 21), (0x3fffd8, 22), (0x7fffe5, 23),
    (0x3fffd9, 22), (0x7fffe6, 23), (0x7fffe7, 23), (0xffffef, 24), (0x3fffda, 22), (0x1fffdd, 21),
    (0xfffe9, 20), (0x3fffdb, 22), (0x3fffdc, 22), (0x7fffe8, 23), (0x7fffe9, 23), (0x1fffde, 21),
    (0x7fffea, 23), (0x3fffdd, 22), (0x3fffde, 22), (0xfffff0, 24), (0x1fffdf, 21), (0x3fffdf, 22),
    (0x7fffeb, 23), (0x7fffec, 23), (0x1fffe0, 21), (0x1fffe1, 21), (0x3fffe0, 22), (0x1fffe2, 21),
    (0x7fffed, 23), (0x3fffe1, 22), (0x7fffee, 23), (0x7fffef, 23), (0xfffea, 20), (0x3fffe2, 22),
    (0x3fffe3, 22), (0x3fffe4, 22), (0x7ffff0, 23), (0x3fffe5, 22), (0x3fffe6, 22), (0x7ffff1, 23),
    (0x3ffffe0, 26), (0x3ffffe1, 26), (0xfffeb, 20), (0x7fff1, 19), (0x3fffe7, 22), (0x7ffff2, 23),
    (0x3fffe8, 22), (0x1ffffec, 25), (0x3ffffe2, 26), (0x3ffffe3, 26), (0x3ffffe4, 26), (0x7ffffde, 27),
    (0x7ffffdf, 27), (0x3ffffe5, 26), (0xfffff1, 24), (0x1ffffed, 25), (0x7fff2, 19), (0x1fffe3, 21),
    (0x3ffffe6, 26), (0x7ffffe0, 27), (0x7ffffe1, 27), (0x3ffffe7, 26), (0x7ffffe2, 27), (0xfffff2, 24),
    (0x1fffe4, 21), (0x1fffe5, 21), (0x3ffffe8, 26), (0x3ffffe9, 26), (0xffffffd, 28), (0x7ffffe3, 27),
    (0x7ffffe4, 27), (0x7ffffe5, 27), (0xfffec, 20), (0xfffff3, 24), (0xfffed, 20), (0x1fffe6, 21),
    (0x3fffea, 22), (0x1fffe7, 21), (0x1fffe8, 21), (0x7ffff3, 23), (0x3fffeb, 22), (0x3fffe9, 22),
    (0x1ffffee, 25), (0x1ffffef, 25), (0xfffff4, 24), (0xfffff5, 24), (0x3ffffea, 26), (0x7ffff4, 23),
    (0x3ffffeb, 26), (0x7ffffe6, 27), (0x3ffffec, 26), (0x3ffffed, 26), (0x7ffffe7, 27), (0x7ffffe8, 27),
    (0x7ffffe9, 27), (0x7ffffea, 27), (0x7ffffeb, 27), (0xffffffe, 28), (0x7ffffec, 27), (0x7ffffed, 27),
    (0x7ffffee, 27), (0x7ffffef, 27), (0x7fffff0, 27), (0x3ffffee, 26), (0x3fffffff, 30),
];

fn huff_encode(data: &[u8], bad_pad: bool) -> (Vec<u8>, usize) {
    let mut bits: Vec<u8> = Vec::new();
    for &byte in data {
        let (code, n) = HUFF[byte as usize];
        for k in (0..n).rev() {
            bits.push(((code >> k) & 1) as u8);
        }
    }
    let npad = (8 - bits.len() % 8) % 8;
    let pad = if bad_pad { 0u8 } else { 1u8 };
    for _ in 0..npad {
        bits.push(pad);
    }
    let mut out = Vec::new();
    let mut i = 0;
    while i < bits.len() {
        let mut v = 0u8;
        for j in 0..8 {
            v = (v << 1) | bits[i + j];
        }
        out.push(v);
        i += 8;
    }
    (out, npad)
}

fn enc_int(value: u64, prefix_bits: u32, high: u8) -> Vec<u8> {
    let mask = (1u64 << prefix_bits) - 1;
    if value < mask {
        return vec![high | (value as u8)];
    }
    let mut out = vec![high | (mask as u8)];
    let mut v = value - mask;
    while v >= 128 {
        out.push(((v & 0x7f) as u8) | 0x80);
        v >>= 7;
    }
    out.push(v as u8);
    out
}

fn enc_str_literal(data: &[u8]) -> Vec<u8> {
    let mut out = enc_int(data.len() as u64, 7, 0x00);
    out.extend_from_slice(data);
    out
}

fn enc_str_huff(data: &[u8], bad_pad: bool) -> Vec<u8> {
    let (enc, _) = huff_encode(data, bad_pad);
    let mut out = enc_int(enc.len() as u64, 7, 0x80);
    out.extend_from_slice(&enc);
    out
}

fn indexed(idx: u64) -> Vec<u8> {
    enc_int(idx, 7, 0x80)
}

fn lit_incr_lit(name: &[u8], value: &[u8]) -> Vec<u8> {
    let mut out = enc_int(0, 6, 0x40);
    out.extend_from_slice(&enc_str_literal(name));
    out.extend_from_slice(&enc_str_literal(value));
    out
}

fn lit_never_lit(name: &[u8], value: &[u8]) -> Vec<u8> {
    let mut out = enc_int(0, 4, 0x10);
    out.extend_from_slice(&enc_str_literal(name));
    out.extend_from_slice(&enc_str_literal(value));
    out
}

fn lit_noindex_idx(name_idx: u64, value_encoded: &[u8]) -> Vec<u8> {
    let mut out = enc_int(name_idx, 4, 0x00);
    out.extend_from_slice(value_encoded);
    out
}

fn size_update(newmax: u64) -> Vec<u8> {
    enc_int(newmax, 5, 0x20)
}

fn lit_noindex_idx15_nonminimal(value_encoded: &[u8]) -> Vec<u8> {
    // Literal without Indexing, 4-bit-prefix name index = static 15
    // (accept-charset) encoded non-minimally as 0f 80 00. The reference decodes
    // index 15 and emits; the audited maintainer rejects the over-long integer.
    let mut out = vec![0x0f, 0x80, 0x00];
    out.extend_from_slice(value_encoded);
    out
}

fn name_bytes(i: u64) -> Vec<u8> {
    format!("f{}", i).into_bytes()
}

fn val_bytes(n: usize, seed: u64) -> Vec<u8> {
    let mut out = Vec::with_capacity(n);
    for k in 0..n as u64 {
        out.push((97 + ((seed * 7 + k * 13) % 26)) as u8);
    }
    out
}

fn get_filler() -> Vec<u8> {
    indexed(2)
}

fn block(max0: u64, octets: &[u8]) -> Vec<u8> {
    let mut out = (max0 as u32).to_be_bytes().to_vec();
    out.extend_from_slice(octets);
    out
}

struct Ob {
    mech: String,
    outcome: String,
    pos: i64,
    max: u64,
    huff: String,
}

fn parse_ob(line: &str) -> Ob {
    let mut mech = String::new();
    let mut outcome = String::new();
    let mut pos = 0i64;
    let mut max = 0u64;
    let mut huff = String::from("none");
    for tok in line.split_whitespace() {
        let mut it = tok.splitn(2, '=');
        let k = it.next().unwrap_or("");
        let v = it.next().unwrap_or("");
        match k {
            "mech" => mech = v.to_string(),
            "outcome" => outcome = v.to_string(),
            "pos" => pos = v.parse().unwrap_or(0),
            "max" => max = v.parse().unwrap_or(0),
            "huff" => huff = v.to_string(),
            _ => {}
        }
    }
    Ob { mech, outcome, pos, max, huff }
}

fn valid_huff_filler(seed: u64) -> Vec<u8> {
    let v = val_bytes(3 + (seed % 4) as usize, seed);
    lit_noindex_idx(1, &enc_str_huff(&v, false))
}

fn construct(ob: &Ob, oid: u64) -> Vec<u8> {
    let hf = ob.huff == "required";
    let mut fillers: Vec<u8> = Vec::new();
    let mut fill_emits = 0i64;
    if hf && ob.mech != "huffpad" {
        fillers.extend_from_slice(&valid_huff_filler(oid));
        fill_emits += 1;
    }

    let mut body: Vec<u8> = Vec::new();

    if ob.mech == "never" && ob.outcome == "both_accept" {
        let need = ob.pos - fill_emits - 2;
        for _ in 0..need {
            body.extend_from_slice(&get_filler());
        }
        body.extend_from_slice(&lit_incr_lit(&name_bytes(oid), &val_bytes(6 + (oid % 5) as usize, oid)));
        body.extend_from_slice(&lit_never_lit(&name_bytes(100 + oid), &val_bytes(5 + (oid % 4) as usize, oid + 1)));
        body.extend_from_slice(&indexed(STATIC_LEN + 1));
    } else if ob.mech == "never" && ob.outcome == "reference_reject" {
        let need = ob.pos - fill_emits - 2;
        for _ in 0..need {
            body.extend_from_slice(&get_filler());
        }
        body.extend_from_slice(&lit_incr_lit(&name_bytes(oid), &val_bytes(6 + (oid % 5) as usize, oid)));
        body.extend_from_slice(&lit_never_lit(&name_bytes(100 + oid), &val_bytes(5 + (oid % 4) as usize, oid + 1)));
        body.extend_from_slice(&indexed(STATIC_LEN + 2));
    } else if ob.mech == "overhead" && ob.outcome == "reference_reject" {
        let mut chosen: Option<(u64, u64)> = None;
        for c in 1u64..6 {
            if ob.max % c != 0 {
                continue;
            }
            let s = ob.max / c;
            if s < 34 {
                continue;
            }
            let s = s - 32;
            if s >= 2 && (c + 1) * s <= ob.max && (ob.pos - fill_emits) >= (c as i64 + 1) {
                chosen = Some((c, s));
                break;
            }
        }
        let (c, s) = chosen.expect("no overhead params");
        let need = ob.pos - fill_emits - (c as i64 + 1);
        for _ in 0..need {
            body.extend_from_slice(&get_filler());
        }
        let nlen = 2usize;
        for j in 0..(c + 1) {
            let mut nm = name_bytes(j);
            while nm.len() < nlen {
                nm.push(b'z');
            }
            nm.truncate(nlen);
            body.extend_from_slice(&lit_incr_lit(&nm, &val_bytes((s as usize) - nlen, oid * 10 + j)));
        }
        body.extend_from_slice(&indexed(STATIC_LEN + 1 + c));
    } else if ob.mech == "sizeupdate" && ob.outcome == "reference_reject" {
        let need = ob.pos - fill_emits - 1;
        for _ in 0..need {
            body.extend_from_slice(&get_filler());
        }
        body.extend_from_slice(&lit_incr_lit(&name_bytes(oid), &val_bytes(4 + (oid % 5) as usize, oid)));
        body.extend_from_slice(&size_update(0));
        body.extend_from_slice(&indexed(STATIC_LEN + 1));
    } else if ob.mech == "minint" && ob.outcome == "audited_reject" {
        let need = ob.pos - fill_emits;
        for _ in 0..need {
            body.extend_from_slice(&get_filler());
        }
        body.extend_from_slice(&lit_noindex_idx15_nonminimal(&enc_str_literal(b"a")));
    } else if ob.mech == "never+sizeupdate" && ob.outcome == "reference_reject" {
        let need = ob.pos - fill_emits - 1;
        for _ in 0..need {
            body.extend_from_slice(&get_filler());
        }
        body.extend_from_slice(&lit_never_lit(&name_bytes(oid), &val_bytes(4 + (oid % 5) as usize, oid)));
        body.extend_from_slice(&size_update(0));
        body.extend_from_slice(&indexed(STATIC_LEN + 1));
    } else if ob.mech == "huffpad" && ob.outcome == "reference_reject" {
        let candidates: [&[u8]; 7] = [b"abc", b"abcd", b"abcde", b"ab", b"abcdef", b"xyz", b"qz"];
        let mut val: &[u8] = b"abc";
        for cand in candidates.iter() {
            let (_, npad) = huff_encode(cand, true);
            if npad >= 1 && npad <= 7 {
                val = cand;
                break;
            }
        }
        let need = ob.pos - fill_emits;
        for _ in 0..need {
            body.extend_from_slice(&get_filler());
        }
        body.extend_from_slice(&lit_noindex_idx(1, &enc_str_huff(val, true)));
    } else {
        eprintln!("unhandled obligation");
        process::exit(3);
    }

    let mut octets = fillers;
    octets.extend_from_slice(&body);
    block(ob.max, &octets)
}

fn hex(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push_str(&format!("{:02x}", b));
    }
    s
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("usage: synth <obligation-file>");
        process::exit(2);
    }
    let text = match fs::read_to_string(&args[1]) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("read error: {}", e);
            process::exit(2);
        }
    };
    let line = text.lines().next().unwrap_or("").trim().to_string();
    let ob = parse_ob(&line);
    // Deterministic obligation id from the line contents keeps distinct
    // obligations distinct without depending on any wall clock.
    let mut oid: u64 = 0;
    for b in line.bytes() {
        oid = oid.wrapping_mul(131).wrapping_add(b as u64);
    }
    oid %= 100000;
    let witness = construct(&ob, oid);
    println!("{}", hex(&witness));
}
RS

cd /app/environment/analysis
cargo build --release --locked --offline
