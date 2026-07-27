// hpack.rs -- disclosed wire-format library for the witness synthesizer.
//
// Everything here is PUBLIC per /app/environment/docs/hpack.md: the RFC 7541
// Appendix B Huffman code, the integer/string primitives, encoders for each
// documented instruction representation, and a faithful port of the *spec-
// compliant reference decoder* (`decode_reference`) that the contract uses to
// fix ground truth. `run_audited` is a convenience wrapper that runs the
// black-box audited decoder binary and parses its disclosed output format.
//
// None of this reveals the audited decoder's deviations: `decode_reference`
// implements only the reference (`decode_{}`), and the audited behavior comes
// solely from probing the binary. Reverse-engineering each deviation, placing a
// divergence at an exact position/outcome, and satisfying mechanism attribution
// (sufficiency / minimality / necessity) remain entirely in `construct`.
#![allow(dead_code)]

use std::collections::HashMap;
use std::fs;
use std::process::Command;

pub const STATIC_LEN: u64 = 61;
pub const PROTOCOL_MAX: u64 = 4096;
pub const AUDITED_DECODER: &str = "/app/environment/evidence/decoder";

/// RFC 7541 Appendix B static table, combined indices 1..=61.
pub static STATIC: [(&[u8], &[u8]); 61] = [
    (b":authority", b""), (b":method", b"GET"), (b":method", b"POST"), (b":path", b"/"),
    (b":path", b"/index.html"), (b":scheme", b"http"), (b":scheme", b"https"), (b":status", b"200"),
    (b":status", b"204"), (b":status", b"206"), (b":status", b"304"), (b":status", b"400"),
    (b":status", b"404"), (b":status", b"500"), (b"accept-charset", b""),
    (b"accept-encoding", b"gzip, deflate"), (b"accept-language", b""), (b"accept-ranges", b""),
    (b"accept", b""), (b"access-control-allow-origin", b""), (b"age", b""), (b"allow", b""),
    (b"authorization", b""), (b"cache-control", b""), (b"content-disposition", b""),
    (b"content-encoding", b""), (b"content-language", b""), (b"content-length", b""),
    (b"content-location", b""), (b"content-range", b""), (b"content-type", b""), (b"cookie", b""),
    (b"date", b""), (b"etag", b""), (b"expect", b""), (b"expires", b""), (b"from", b""),
    (b"host", b""), (b"if-match", b""), (b"if-modified-since", b""), (b"if-none-match", b""),
    (b"if-range", b""), (b"if-unmodified-since", b""), (b"last-modified", b""), (b"link", b""),
    (b"location", b""), (b"max-forwards", b""), (b"proxy-authenticate", b""),
    (b"proxy-authorization", b""), (b"range", b""), (b"referer", b""), (b"refresh", b""),
    (b"retry-after", b""), (b"server", b""), (b"set-cookie", b""), (b"strict-transport-security", b""),
    (b"transfer-encoding", b""), (b"user-agent", b""), (b"vary", b""), (b"via", b""),
    (b"www-authenticate", b""),
];

// RFC 7541 Appendix B canonical Huffman code, indexed by symbol 0..=256 (256=EOS).
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

fn huff_map() -> HashMap<(u8, u32), u16> {
    let mut m = HashMap::new();
    for (sym, &(code, n)) in HUFF.iter().enumerate() {
        m.insert((n, code), sym as u16);
    }
    m
}

// -------------------- Encoders (all spec-compliant) --------------------------

/// Huffman-encode `data` per Appendix B with compliant all-ones EOS-prefix padding.
pub fn huff_encode(data: &[u8]) -> Vec<u8> {
    let mut bits: Vec<u8> = Vec::new();
    for &byte in data {
        let (code, n) = HUFF[byte as usize];
        for k in (0..n).rev() {
            bits.push(((code >> k) & 1) as u8);
        }
    }
    let npad = (8 - bits.len() % 8) % 8;
    for _ in 0..npad {
        bits.push(1);
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
    out
}

/// HPACK N-bit-prefix integer (Section 5.1), encoded minimally. `high` supplies
/// the representation bits in the top `8 - prefix_bits` bits of the first octet.
pub fn enc_int(value: u64, prefix_bits: u32, high: u8) -> Vec<u8> {
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

pub fn enc_str_literal(data: &[u8]) -> Vec<u8> {
    let mut out = enc_int(data.len() as u64, 7, 0x00);
    out.extend_from_slice(data);
    out
}

pub fn enc_str_huff(data: &[u8]) -> Vec<u8> {
    let enc = huff_encode(data);
    let mut out = enc_int(enc.len() as u64, 7, 0x80);
    out.extend_from_slice(&enc);
    out
}

pub fn value_str(data: &[u8], huff: bool) -> Vec<u8> {
    if huff { enc_str_huff(data) } else { enc_str_literal(data) }
}

/// Indexed Header Field (high bit 1, 7-bit-prefix index).
pub fn indexed(idx: u64) -> Vec<u8> {
    enc_int(idx, 7, 0x80)
}

fn lit_repr(high: u8, prefix_bits: u32, name_idx: u64, name: &[u8], value: &[u8], huff: bool) -> Vec<u8> {
    let mut out = enc_int(name_idx, prefix_bits, high);
    if name_idx == 0 {
        out.extend_from_slice(&enc_str_literal(name));
    }
    out.extend_from_slice(&value_str(value, huff));
    out
}

/// Literal Header Field with Incremental Indexing (01, 6-bit prefix); inserted.
pub fn incr_indexing(name_idx: u64, name: &[u8], value: &[u8], huff: bool) -> Vec<u8> {
    lit_repr(0x40, 6, name_idx, name, value, huff)
}

/// Literal Header Field without Indexing (0000, 4-bit prefix).
pub fn without_indexing(name_idx: u64, name: &[u8], value: &[u8], huff: bool) -> Vec<u8> {
    lit_repr(0x00, 4, name_idx, name, value, huff)
}

/// Literal Header Field Never Indexed (0001, 4-bit prefix).
pub fn never_indexed(name_idx: u64, name: &[u8], value: &[u8], huff: bool) -> Vec<u8> {
    lit_repr(0x10, 4, name_idx, name, value, huff)
}

/// Dynamic Table Size Update (001, 5-bit-prefix new maximum).
pub fn size_update(newmax: u64) -> Vec<u8> {
    enc_int(newmax, 5, 0x20)
}

/// Prepend the 4-octet big-endian initial-maximum header to instruction octets.
pub fn block(max0: u64, octets: &[u8]) -> Vec<u8> {
    let mut out = (max0 as u32).to_be_bytes().to_vec();
    out.extend_from_slice(octets);
    out
}

pub fn hex(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push_str(&format!("{:02x}", b));
    }
    s
}

pub fn unhex(s: &str) -> Option<Vec<u8>> {
    let s = s.trim();
    if s.len() % 2 != 0 {
        return None;
    }
    let mut out = Vec::with_capacity(s.len() / 2);
    let b = s.as_bytes();
    let mut i = 0;
    while i < b.len() {
        let hi = (b[i] as char).to_digit(16)?;
        let lo = (b[i + 1] as char).to_digit(16)?;
        out.push(((hi << 4) | lo) as u8);
        i += 2;
    }
    Some(out)
}

// -------------------- Spec-compliant reference decoder -----------------------

/// The result of a decode: the fields emitted before any error, and the emit
/// index at which a fatal decode error occurred (None if the block decoded fully
/// / the decoder accepted the block).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Decoded {
    pub fields: Vec<(Vec<u8>, Vec<u8>)>,
    pub error_at: Option<usize>,
}

impl Decoded {
    pub fn accepted(&self) -> bool {
        self.error_at.is_none()
    }
}

struct Reader<'a> {
    buf: &'a [u8],
    pos: usize,
}

impl<'a> Reader<'a> {
    fn read_int(&mut self, prefix_bits: u32) -> Result<u64, ()> {
        if self.pos >= self.buf.len() {
            return Err(());
        }
        let mask = (1u64 << prefix_bits) - 1;
        let mut value = (self.buf[self.pos] as u64) & mask;
        self.pos += 1;
        if value < mask {
            return Ok(value);
        }
        let mut shift = 0u32;
        let mut octets = 0;
        loop {
            if self.pos >= self.buf.len() {
                return Err(());
            }
            let b = self.buf[self.pos];
            self.pos += 1;
            octets += 1;
            if octets > 6 {
                return Err(());
            }
            value += ((b & 0x7f) as u64) << shift;
            shift += 7;
            if b & 0x80 == 0 {
                break;
            }
        }
        Ok(value)
    }

    fn read_string(&mut self) -> Result<Vec<u8>, ()> {
        if self.pos >= self.buf.len() {
            return Err(());
        }
        let huffman = (self.buf[self.pos] & 0x80) != 0;
        let length = self.read_int(7)? as usize;
        let end = self.pos + length;
        if end > self.buf.len() {
            return Err(());
        }
        let raw = &self.buf[self.pos..end];
        self.pos = end;
        if huffman {
            huff_decode_strict(raw)
        } else {
            Ok(raw.to_vec())
        }
    }
}

/// Reference Huffman decode with the three RFC 7541 5.2 padding rules enforced:
/// padding at most 7 bits, all-ones EOS prefix, and no decoded EOS symbol.
fn huff_decode_strict(data: &[u8]) -> Result<Vec<u8>, ()> {
    let map = huff_map();
    let mut out = Vec::new();
    let mut cur: u32 = 0;
    let mut len: u8 = 0;
    for &byte in data {
        for k in (0..8).rev() {
            let bit = ((byte >> k) & 1) as u32;
            cur = (cur << 1) | bit;
            len += 1;
            if len > 30 {
                return Err(());
            }
            if let Some(&sym) = map.get(&(len, cur)) {
                if sym == 256 {
                    return Err(()); // EOS symbol decoded
                }
                out.push(sym as u8);
                cur = 0;
                len = 0;
            }
        }
    }
    if len > 0 {
        if len > 7 {
            return Err(()); // padding too long
        }
        let ones = (1u32 << len) - 1;
        if cur != ones {
            return Err(()); // padding is not the all-ones EOS prefix
        }
    }
    Ok(out)
}

/// Decode a full witness block (4-octet initial-maximum header + instructions)
/// under the spec-compliant RFC 7541 reference maintainer. This is `decode_{}`
/// in the contract -- ground truth's reference side. The audited side must be
/// obtained by running the black-box binary (see `run_audited`).
pub fn decode_reference(block: &[u8]) -> Decoded {
    if block.len() < 4 {
        return Decoded { fields: Vec::new(), error_at: Some(0) };
    }
    let max0 = u32::from_be_bytes([block[0], block[1], block[2], block[3]]) as u64;
    decode_ref_body(&block[4..], max0)
}

fn decode_ref_body(buf: &[u8], max0: u64) -> Decoded {
    let mut dyn_tbl: Vec<(Vec<u8>, Vec<u8>)> = Vec::new();
    let mut cur_max = max0;
    let mut size: u64 = 0;
    let mut emitted: Vec<(Vec<u8>, Vec<u8>)> = Vec::new();
    let mut r = Reader { buf, pos: 0 };

    let esize = |n: &[u8], v: &[u8]| -> u64 { n.len() as u64 + v.len() as u64 + 32 };

    macro_rules! fail {
        () => {{
            return Decoded { fields: emitted.clone(), error_at: Some(emitted.len()) };
        }};
    }

    let result: Result<(), ()> = (|| {
        while r.pos < buf.len() {
            let b = buf[r.pos];
            if b & 0x80 != 0 {
                let idx = r.read_int(7)?;
                emitted.push(resolve(&dyn_tbl, idx)?);
            } else if b & 0x40 != 0 {
                let idx = r.read_int(6)?;
                let name = if idx == 0 { r.read_string()? } else { resolve(&dyn_tbl, idx)?.0 };
                let value = r.read_string()?;
                emitted.push((name.clone(), value.clone()));
                // reference insert (per-entry overhead 32, evict oldest to fit)
                let es = esize(&name, &value);
                if es > cur_max {
                    dyn_tbl.clear();
                    size = 0;
                } else {
                    let limit = cur_max - es;
                    while !dyn_tbl.is_empty() && size > limit {
                        let (nn, vv) = dyn_tbl.pop().unwrap();
                        size -= esize(&nn, &vv);
                    }
                    dyn_tbl.insert(0, (name, value));
                    size += es;
                }
            } else if b & 0x20 != 0 {
                let newmax = r.read_int(5)?;
                if newmax > PROTOCOL_MAX {
                    return Err(());
                }
                cur_max = newmax;
                while !dyn_tbl.is_empty() && size > cur_max {
                    let (nn, vv) = dyn_tbl.pop().unwrap();
                    size -= esize(&nn, &vv);
                }
            } else {
                let _never = (b & 0x10) != 0;
                let idx = r.read_int(4)?;
                let name = if idx == 0 { r.read_string()? } else { resolve(&dyn_tbl, idx)?.0 };
                let value = r.read_string()?;
                emitted.push((name, value));
                // reference never inserts for without/never-indexed representations
            }
        }
        Ok(())
    })();

    match result {
        Ok(()) => Decoded { fields: emitted, error_at: None },
        Err(()) => fail!(),
    }
}

fn resolve(dyn_tbl: &[(Vec<u8>, Vec<u8>)], idx: u64) -> Result<(Vec<u8>, Vec<u8>), ()> {
    if idx == 0 {
        return Err(());
    }
    if idx <= STATIC_LEN {
        let (n, v) = STATIC[(idx - 1) as usize];
        return Ok((n.to_vec(), v.to_vec()));
    }
    let di = (idx - STATIC_LEN - 1) as usize;
    if di >= dyn_tbl.len() {
        return Err(());
    }
    Ok(dyn_tbl[di].clone())
}

/// First emitted position where two decode results differ, with the field taken
/// from the second (audited) side when present there, else the first. None when
/// the emitted sequences are identical. Mirrors the contract's definition.
pub fn first_divergence(a: &Decoded, b: &Decoded) -> Option<(usize, (Vec<u8>, Vec<u8>))> {
    let n = a.fields.len().max(b.fields.len());
    for p in 0..n {
        let ra = a.fields.get(p);
        let rb = b.fields.get(p);
        if ra != rb {
            let field = rb.or(ra).unwrap().clone();
            return Some((p, field));
        }
    }
    None
}

/// Run the black-box audited decoder on `block` and parse its disclosed output
/// (`H <namehex> <valuehex>` lines, then `ACCEPT` or `REJECT <n>`). Returns the
/// audited decode as a `Decoded`. Errors only on I/O / spawn failure.
pub fn run_audited(block: &[u8]) -> std::io::Result<Decoded> {
    let path = format!("/tmp/.hpack_probe_{}.bin", std::process::id());
    fs::write(&path, block)?;
    let out = Command::new(AUDITED_DECODER).arg(&path).output()?;
    let text = String::from_utf8_lossy(&out.stdout);
    let mut fields: Vec<(Vec<u8>, Vec<u8>)> = Vec::new();
    let mut error_at: Option<usize> = None;
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        if let Some(rest) = line.strip_prefix("H ") {
            let mut it = rest.split_whitespace();
            let nh = it.next().unwrap_or("");
            let vh = it.next().unwrap_or("");
            let n = unhex(nh).unwrap_or_default();
            let v = unhex(vh).unwrap_or_default();
            fields.push((n, v));
        } else if line == "ACCEPT" {
            error_at = None;
        } else if let Some(rest) = line.strip_prefix("REJECT") {
            error_at = Some(rest.trim().parse::<usize>().unwrap_or(fields.len()));
        }
    }
    Ok(Decoded { fields, error_at })
}
