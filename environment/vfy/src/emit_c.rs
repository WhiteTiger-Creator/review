use std::collections::HashSet;
use std::fs;
use std::io;
use std::path::Path;

use crate::skim_fold::Roster;

pub struct QuarantineEntry {
    pub epoch: u16,
    pub lane: String,
    pub ts: u64,
    pub reason: String,
}

pub fn write_roster(path: &str, roster: &Roster) -> io::Result<()> {
    if path.trim().is_empty() {
        return Err(io::Error::new(io::ErrorKind::InvalidInput, "empty path"));
    }
    if let Some(parent) = Path::new(path).parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent)?;
        }
    }
    let mut body = String::from("{\n  \"version\": 1,\n  \"backends\": [\n");
    for (i, (name, status)) in roster.backends.iter().enumerate() {
        if i > 0 {
            body.push_str(",\n");
        }
        body.push_str(&format!(
            "    {{\"name\": \"{}\", \"status\": \"{}\"}}",
            escape(name),
            escape(status)
        ));
    }
    body.push_str("\n  ],\n  \"epochs\": [\n");
    for (i, (id, profile, accepted)) in roster.epochs.iter().enumerate() {
        if i > 0 {
            body.push_str(",\n");
        }
        body.push_str(&format!(
            "    {{\"id\": {}, \"profile\": \"{}\", \"accepted\": {}}}",
            id,
            escape(profile),
            accepted
        ));
    }
    body.push_str("\n  ]\n}\n");
    fs::write(path, body)
}

pub fn write_quarantine(path: &str, entries: &[QuarantineEntry]) -> io::Result<()> {
    if path.trim().is_empty() {
        return Err(io::Error::new(io::ErrorKind::InvalidInput, "empty path"));
    }
    if let Some(parent) = Path::new(path).parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent)?;
        }
    }

    let mut seen: HashSet<(u16, String)> = HashSet::new();
    let mut body = String::from("{\n  \"version\": 1,\n  \"rejected\": [\n");
    let mut count = 0;
    for e in entries {
        let key = (e.epoch, e.lane.clone());
        if seen.contains(&key) {
            continue;
        }
        seen.insert(key);
        if count > 0 {
            body.push_str(",\n");
        }
        body.push_str(&format!(
            "    {{\"epoch\": {}, \"lane\": \"{}\", \"ts\": {}, \"reason\": \"{}\"}}",
            e.epoch,
            escape(&e.lane),
            e.ts,
            escape(&e.reason)
        ));
        count += 1;
    }
    body.push_str("\n  ]\n}\n");
    fs::write(path, body)
}

fn escape(raw: &str) -> String {
    raw.replace('\\', "\\\\").replace('"', "\\\"")
}
