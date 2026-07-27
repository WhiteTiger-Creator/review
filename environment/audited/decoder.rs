// Audited HPACK header-block decoder.
//
// Self-contained RFC 7541 HPACK decoder as deployed. It shares the octet grammar
// and the Huffman code with a spec-compliant peer; its observable behavior is the
// authoritative definition of the "audited decoder" referenced by the task. This
// source is compiled into the stripped `decoder` binary staged as immutable
// evidence; the source itself is not shipped in the task image. The binary reads
// a block file named on argv[1], prints one `H <namehex> <valuehex>` line per
// emitted field, then `ACCEPT` or `REJECT <n>` where n is the count of fields
// emitted before a decode error. Probe it as a black box to characterize its
// departures from the spec-compliant reference.

use std::env;
use std::fs;
use std::process;

const PROTOCOL_MAX: u64 = 4096;

static STATIC: [(&str, &str); 61] = [
    (":authority", ""), (":method", "GET"), (":method", "POST"), (":path", "/"),
    (":path", "/index.html"), (":scheme", "http"), (":scheme", "https"),
    (":status", "200"), (":status", "204"), (":status", "206"), (":status", "304"),
    (":status", "400"), (":status", "404"), (":status", "500"),
    ("accept-charset", ""), ("accept-encoding", "gzip, deflate"),
    ("accept-language", ""), ("accept-ranges", ""), ("accept", ""),
    ("access-control-allow-origin", ""), ("age", ""), ("allow", ""),
    ("authorization", ""), ("cache-control", ""), ("content-disposition", ""),
    ("content-encoding", ""), ("content-language", ""), ("content-length", ""),
    ("content-location", ""), ("content-range", ""), ("content-type", ""),
    ("cookie", ""), ("date", ""), ("etag", ""), ("expect", ""), ("expires", ""),
    ("from", ""), ("host", ""), ("if-match", ""), ("if-modified-since", ""),
    ("if-none-match", ""), ("if-range", ""), ("if-unmodified-since", ""),
    ("last-modified", ""), ("link", ""), ("location", ""), ("max-forwards", ""),
    ("proxy-authenticate", ""), ("proxy-authorization", ""), ("range", ""),
    ("referer", ""), ("refresh", ""), ("retry-after", ""), ("server", ""),
    ("set-cookie", ""), ("strict-transport-security", ""),
    ("transfer-encoding", ""), ("user-agent", ""), ("vary", ""), ("via", ""),
    ("www-authenticate", ""),
];

// RFC 7541 Appendix B canonical Huffman code, indexed by symbol 0..256 (256=EOS).
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

fn entry_size(name: &[u8], value: &[u8]) -> i64 {
    name.len() as i64 + value.len() as i64
}

fn minimal_cont_octets(residual: u64) -> u32 {
    if residual == 0 {
        return 1;
    }
    let mut n = 0u32;
    let mut r = residual;
    while r > 0 {
        r >>= 7;
        n += 1;
    }
    n
}

fn read_int(buf: &[u8], pos: usize, prefix: u32) -> Option<(u64, usize)> {
    if pos >= buf.len() {
        return None;
    }
    let mask: u64 = (1u64 << prefix) - 1;
    let mut value: u64 = (buf[pos] as u64) & mask;
    let mut p = pos + 1;
    if value < mask {
        return Some((value, p));
    }
    let mut shift: u32 = 0;
    let mut octets: u32 = 0;
    loop {
        if p >= buf.len() {
            return None;
        }
        let b = buf[p];
        p += 1;
        octets += 1;
        if octets > 6 {
            return None;
        }
        value = value.wrapping_add(((b & 0x7f) as u64) << shift);
        shift += 7;
        if b & 0x80 == 0 {
            break;
        }
    }
    if octets > minimal_cont_octets(value - mask) {
        return None;
    }
    Some((value, p))
}

fn huff_decode(data: &[u8]) -> Option<Vec<u8>> {
    let mut out = Vec::new();
    let mut acc: u32 = 0;
    let mut nbits: u32 = 0;
    let mut cur_len: u32 = 0;
    for &byte in data {
        for k in (0..8).rev() {
            let bit = ((byte >> k) & 1) as u32;
            acc = (acc << 1) | bit;
            nbits += 1;
            cur_len += 1;
            if nbits >= 5 {
                if let Some(sym) = match_symbol(acc, nbits) {
                    if sym == 256 {
                        return None;
                    }
                    out.push(sym as u8);
                    acc = 0;
                    nbits = 0;
                    cur_len = 0;
                }
            }
        }
    }
    if cur_len > 7 {
        return None;
    }
    Some(out)
}

fn match_symbol(code: u32, len: u32) -> Option<u16> {
    for (sym, &(c, l)) in HUFF.iter().enumerate() {
        if l as u32 == len && c == code {
            return Some(sym as u16);
        }
    }
    None
}

fn read_string(buf: &[u8], pos: usize) -> Option<(Vec<u8>, usize)> {
    if pos >= buf.len() {
        return None;
    }
    let huff = buf[pos] & 0x80 != 0;
    let (len, p) = read_int(buf, pos, 7)?;
    let len = len as usize;
    if p + len > buf.len() {
        return None;
    }
    let raw = &buf[p..p + len];
    if huff {
        let decoded = huff_decode(raw)?;
        Some((decoded, p + len))
    } else {
        Some((raw.to_vec(), p + len))
    }
}

fn resolve(dyn_tbl: &[(Vec<u8>, Vec<u8>)], idx: u64) -> Option<(Vec<u8>, Vec<u8>)> {
    if idx == 0 {
        return None;
    }
    let idx = idx as usize;
    if idx <= STATIC.len() {
        let (n, v) = STATIC[idx - 1];
        return Some((n.as_bytes().to_vec(), v.as_bytes().to_vec()));
    }
    let di = idx - STATIC.len() - 1;
    if di >= dyn_tbl.len() {
        return None;
    }
    Some(dyn_tbl[di].clone())
}

fn insert(dyn_tbl: &mut Vec<(Vec<u8>, Vec<u8>)>, size: &mut i64, cur_max: i64, name: Vec<u8>, value: Vec<u8>) {
    let es = entry_size(&name, &value);
    if es > cur_max {
        dyn_tbl.clear();
        *size = 0;
        return;
    }
    let limit = cur_max - es;
    while !dyn_tbl.is_empty() && *size > limit {
        let (n, v) = dyn_tbl.pop().unwrap();
        *size -= entry_size(&n, &v);
    }
    dyn_tbl.insert(0, (name, value));
    *size += es;
}

fn decode(buf: &[u8], max0: u64) -> (Vec<(Vec<u8>, Vec<u8>)>, Option<usize>) {
    let mut dyn_tbl: Vec<(Vec<u8>, Vec<u8>)> = Vec::new();
    let mut cur_max: i64 = max0 as i64;
    let mut size: i64 = 0;
    let mut emitted: Vec<(Vec<u8>, Vec<u8>)> = Vec::new();
    let mut pos = 0usize;
    while pos < buf.len() {
        let b = buf[pos];
        if b & 0x80 != 0 {
            let (idx, np) = match read_int(buf, pos, 7) {
                Some(x) => x,
                None => return (emitted.clone(), Some(emitted.len())),
            };
            pos = np;
            match resolve(&dyn_tbl, idx) {
                Some(h) => emitted.push(h),
                None => return (emitted.clone(), Some(emitted.len())),
            }
        } else if b & 0x40 != 0 {
            let (idx, np) = match read_int(buf, pos, 6) {
                Some(x) => x,
                None => return (emitted.clone(), Some(emitted.len())),
            };
            pos = np;
            let name = if idx == 0 {
                let (n, np2) = match read_string(buf, pos) {
                    Some(x) => x,
                    None => return (emitted.clone(), Some(emitted.len())),
                };
                pos = np2;
                n
            } else {
                match resolve(&dyn_tbl, idx) {
                    Some((n, _)) => n,
                    None => return (emitted.clone(), Some(emitted.len())),
                }
            };
            let (value, np3) = match read_string(buf, pos) {
                Some(x) => x,
                None => return (emitted.clone(), Some(emitted.len())),
            };
            pos = np3;
            emitted.push((name.clone(), value.clone()));
            insert(&mut dyn_tbl, &mut size, cur_max, name, value);
        } else if b & 0x20 != 0 {
            let (newmax, np) = match read_int(buf, pos, 5) {
                Some(x) => x,
                None => return (emitted.clone(), Some(emitted.len())),
            };
            pos = np;
            if newmax > PROTOCOL_MAX {
                return (emitted.clone(), Some(emitted.len()));
            }
            cur_max = newmax as i64;
        } else {
            let never = b & 0x10 != 0;
            let (idx, np) = match read_int(buf, pos, 4) {
                Some(x) => x,
                None => return (emitted.clone(), Some(emitted.len())),
            };
            pos = np;
            let name = if idx == 0 {
                let (n, np2) = match read_string(buf, pos) {
                    Some(x) => x,
                    None => return (emitted.clone(), Some(emitted.len())),
                };
                pos = np2;
                n
            } else {
                match resolve(&dyn_tbl, idx) {
                    Some((n, _)) => n,
                    None => return (emitted.clone(), Some(emitted.len())),
                }
            };
            let (value, np3) = match read_string(buf, pos) {
                Some(x) => x,
                None => return (emitted.clone(), Some(emitted.len())),
            };
            pos = np3;
            emitted.push((name.clone(), value.clone()));
            if never {
                insert(&mut dyn_tbl, &mut size, cur_max, name, value);
            }
        }
    }
    (emitted, None)
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
        eprintln!("usage: decoder <block-file>");
        process::exit(2);
    }
    let raw = match fs::read(&args[1]) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("read error: {}", e);
            process::exit(2);
        }
    };
    if raw.len() < 4 {
        eprintln!("block too short");
        process::exit(2);
    }
    let max0 = u32::from_be_bytes([raw[0], raw[1], raw[2], raw[3]]) as u64;
    let buf = &raw[4..];
    let (emitted, err) = decode(buf, max0);
    for (n, v) in &emitted {
        println!("H {} {}", hex(n), hex(v));
    }
    match err {
        None => println!("ACCEPT"),
        Some(p) => println!("REJECT {}", p),
    }
}
