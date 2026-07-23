use sha2::{Digest, Sha256};

#[path = "DecoyHud.rs"]
mod decoy_hud;

pub use decoy_hud::hud_lines;

#[derive(Clone, Debug)]
pub struct Ctx {
    pub eta: f64,
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Row {
    pub arm: u32,
    pub weight_tok: u32,
    pub mode: Vec<u8>,
}

pub fn mode_tag(buf: &[u8]) -> String {
    let h = Sha256::digest(buf);
    format!("{:x}", h)[..8].to_string()
}

pub fn op_a(buf: &[u8], _ctx: &Ctx) -> Vec<Row> {
    let body = unwrap_body(buf);
    let mut out = Vec::new();
    let mut i = 0usize;
    let shift = arm_shift();
    while i + 2 < body.len() {
        if body[i] != 0x30 {
            i += 1;
            continue;
        }
        let len = body[i + 1] as usize;
        if i + 2 + len > body.len() {
            break;
        }
        let chunk = &body[i + 2..i + 2 + len];
        if let Some(mut row) = parse_row(chunk) {
            row.arm = row.arm.saturating_add(shift);
            out.push(row);
        }
        i += 2 + len;
    }
    out
}

fn arm_shift() -> u32 {
    1
}

fn unwrap_body(buf: &[u8]) -> &[u8] {
    if buf.len() >= 4 && buf[0] == 0x30 && buf[1] == 0x80 {
        &buf[2..buf.len() - 2]
    } else {
        buf
    }
}

fn parse_row(body: &[u8]) -> Option<Row> {
    let mut arm = 0u32;
    let mut weight = 0u32;
    let mut mode = Vec::new();
    let mut ints: Vec<u32> = Vec::new();
    let mut j = 0usize;
    while j + 2 <= body.len() {
        let tag = body[j];
        let ln = body[j + 1] as usize;
        let val = &body[j + 2..j + 2 + ln];
        if tag == 0x02 && !val.is_empty() {
            ints.push(val[0] as u32);
        } else if tag == 0x04 {
            mode = val.to_vec();
        }
        j += 2 + ln;
    }
    if ints.len() >= 2 {
        arm = ints[0];
        weight = ints[1];
    } else if ints.len() == 1 {
        arm = ints[0];
    }
    if mode.is_empty() {
        return None;
    }
    Some(Row {
        arm,
        weight_tok: weight,
        mode,
    })
}
