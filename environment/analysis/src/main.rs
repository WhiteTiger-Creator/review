// Witness synthesizer -- starter scaffold.
//
// The wire-format library in `hpack.rs` (declared below) ships everything that
// /app/environment/docs/hpack.md discloses: the RFC 7541 Appendix B Huffman
// code, integer/string primitives, encoders for every instruction
// representation (`indexed`, `incr_indexing`, `without_indexing`,
// `never_indexed`, `size_update`, `block`, `hex`), the spec-compliant
// **reference decoder** (`decode_reference`), a `first_divergence` helper, and
// `run_audited`, which runs the black-box audited binary and parses its output.
// Together those let you compute, for any candidate block, both the reference
// side (in-process) and the audited side (from the binary) and see where they
// diverge -- the differential-probing loop you need.
//
// What is left for you is `construct` below. The library gives you spec-
// COMPLIANT building blocks only: `enc_int` emits minimal integers and the
// Huffman helpers emit compliant padding, and `decode_reference` implements only
// the reference. The audited decoder's five deviations are defined solely by the
// binary at /app/environment/evidence/decoder -- reverse-engineer each one by
// probing, then build a witness block whose reference/audited divergence lands
// at exactly the obligation's position and outcome and is attributable to
// exactly the named deviation(s) (sufficiency / minimality / necessity).
//
// Build with: cargo build --release --locked

mod hpack;
use hpack::*;

use std::env;
use std::fs;
use std::process;

/// One parsed obligation line (hpack.md, "Obligations").
pub struct Ob {
    pub mech: String,
    pub outcome: String,
    pub pos: i64,
    pub max: u64,
    pub maxlen: u64,
    pub huff: String,
}

fn parse_ob(line: &str) -> Ob {
    let mut ob = Ob {
        mech: String::new(),
        outcome: String::new(),
        pos: 0,
        max: 0,
        maxlen: 0,
        huff: String::from("none"),
    };
    for tok in line.split_whitespace() {
        let mut it = tok.splitn(2, '=');
        let k = it.next().unwrap_or("");
        let v = it.next().unwrap_or("");
        match k {
            "mech" => ob.mech = v.to_string(),
            "outcome" => ob.outcome = v.to_string(),
            "pos" => ob.pos = v.parse().unwrap_or(0),
            "max" => ob.max = v.parse().unwrap_or(0),
            "maxlen" => ob.maxlen = v.parse().unwrap_or(0),
            "huff" => ob.huff = v.to_string(),
            _ => {}
        }
    }
    ob
}

/// TODO(you): build a witness block for `ob`.
///
/// Return the full block (the 4-octet `ob.max` header followed by instruction
/// octets, e.g. via `block(ob.max, &octets)`), on which the reference decoder
/// (`decode_reference`) and the audited binary (`run_audited`) first diverge at
/// emitted position `ob.pos` with outcome `ob.outcome`, attributable to exactly
/// the deviation(s) named in `ob.mech` (honoring `ob.maxlen` and `ob.huff`).
/// Returning an empty vector signals "not yet implemented". `oid` is a stable
/// per-obligation id you may use to keep distinct obligations distinct.
fn construct(ob: &Ob, oid: u64) -> Vec<u8> {
    let _ = (ob, oid);
    Vec::new()
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
    // Deterministic obligation id from the line contents -- no wall clock.
    let mut oid: u64 = 0;
    for b in line.bytes() {
        oid = oid.wrapping_mul(131).wrapping_add(b as u64);
    }
    oid %= 100000;
    let witness = construct(&ob, oid);
    if witness.is_empty() {
        eprintln!("construct() is not implemented yet");
        process::exit(1);
    }
    println!("{}", hex(&witness));
}
