use std::collections::HashMap;

use ed25519_dalek::{Signature, SigningKey, Verifier};

use crate::emit_c::QuarantineEntry;
use crate::skim_fold::Frame;

const SIG_LEN: usize = 64;

pub fn decode_wal_with_quarantine(
    raw: &[u8],
    nonces: &HashMap<u16, Vec<u8>>,
) -> (Vec<Frame>, Vec<QuarantineEntry>) {
    let lane_names: HashMap<u8, &str> = [
        (1, "mqtt"),
        (2, "lora"),
        (3, "uart"),
        (4, "canbus"),
        (5, "zigbee"),
    ]
    .into_iter()
    .collect();

    let mut accepted = Vec::new();
    let mut rejected = Vec::new();
    let mut i = 0usize;

    while i + 6 <= raw.len() {
        if raw[i] != 0xA5 {
            i += 1;
            continue;
        }
        let lane_id = raw[i + 1];
        let epoch = u16::from_be_bytes([raw[i + 2], raw[i + 3]]);
        let plen = u16::from_be_bytes([raw[i + 4], raw[i + 5]]) as usize;
        let start = i + 6;
        let end = start + plen;
        if end + SIG_LEN > raw.len() {
            break;
        }
        let payload = &raw[start..end];
        let sig = &raw[end..end + SIG_LEN];

        let text = String::from_utf8_lossy(payload);
        let ts = parse_ts(&text).unwrap_or(0);
        let hold = text.contains("hold=1");
        let lane_name = lane_names.get(&lane_id).unwrap_or(&"unknown");

        let valid = match nonces.get(&epoch) {
            Some(key) if key.len() == 32 => verify_payload_only(payload, sig, key),
            _ => false,
        };

        if valid {
            accepted.push(Frame {
                epoch,
                lane: lane_name.to_string(),
                ts,
                hold,
                from_wal: true,
            });
        } else {
            rejected.push(QuarantineEntry {
                epoch,
                lane: lane_name.to_string(),
                ts,
                reason: "integrity_failure".to_string(),
            });
        }

        i = end + SIG_LEN;
    }
    (accepted, rejected)
}

fn verify_payload_only(payload: &[u8], sig: &[u8], key_material: &[u8]) -> bool {
    if sig.len() != SIG_LEN {
        return false;
    }
    let sk_bytes: [u8; 32] = match key_material.try_into() {
        Ok(b) => b,
        Err(_) => return false,
    };
    let sig_bytes: [u8; 64] = match sig.try_into() {
        Ok(b) => b,
        Err(_) => return false,
    };
    let sk = SigningKey::from_bytes(&sk_bytes);
    let vk = sk.verifying_key();
    let signature = Signature::from_bytes(&sig_bytes);
    // Binds only the payload bytes — misses epoch/lane domain binding.
    vk.verify_strict(payload, &signature).is_ok()
}

fn parse_ts(text: &str) -> Option<u64> {
    let i = text.find("ts=")?;
    let rest = &text[i + 3..];
    let digits: String = rest.chars().take_while(|c| c.is_ascii_digit()).collect();
    digits.parse().ok()
}
