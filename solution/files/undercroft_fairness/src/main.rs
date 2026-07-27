use cartograph_core::{generate_dungeon, Campaign};
use xd::scan_xd;
use xe::evaluate_fairness;
use std::env;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

fn main() -> ExitCode {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 || args[1] != "playtest" {
        eprintln!("usage: undercroft-fairness playtest --campaigns DIR --ledger PATH --atlas PATH --seal PATH --journal PATH");
        return ExitCode::from(2);
    }
    let mut campaigns_dir = None;
    let mut ledger = None;
    let mut atlas = None;
    let mut seal = None;
    let mut journal = None;
    let mut i = 2;
    while i < args.len() {
        match args[i].as_str() {
            "--campaigns" => {
                i += 1;
                campaigns_dir = args.get(i).cloned();
            }
            "--ledger" => {
                i += 1;
                ledger = args.get(i).cloned();
            }
            "--atlas" => {
                i += 1;
                atlas = args.get(i).cloned();
            }
            "--seal" => {
                i += 1;
                seal = args.get(i).cloned();
            }
            "--journal" => {
                i += 1;
                journal = args.get(i).cloned();
            }
            other => {
                eprintln!("unknown arg: {other}");
                return ExitCode::from(2);
            }
        }
        i += 1;
    }
    let (Some(cdir), Some(ledger), Some(atlas), Some(seal), Some(journal)) =
        (campaigns_dir, ledger, atlas, seal, journal)
    else {
        eprintln!("missing required flags");
        return ExitCode::from(2);
    };
    match run_playtest(
        Path::new(&cdir),
        Path::new(&ledger),
        Path::new(&atlas),
        Path::new(&seal),
        Path::new(&journal),
    ) {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("playtest failed: {e}");
            ExitCode::from(1)
        }
    }
}

fn run_playtest(
    campaigns_dir: &Path,
    ledger_path: &Path,
    atlas_path: &Path,
    seal_path: &Path,
    journal_path: &Path,
) -> Result<(), String> {
    let mut files: Vec<PathBuf> = fs::read_dir(campaigns_dir)
        .map_err(|e| e.to_string())?
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| p.extension().and_then(|x| x.to_str()) == Some("json"))
        .collect();
    files.sort();
    if files.is_empty() {
        return Err("no campaign json files".into());
    }
    for path in [ledger_path, atlas_path, seal_path, journal_path] {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
    }

    let staging_path = journal_path
        .parent()
        .unwrap_or_else(|| Path::new("."))
        .join("seed-hunt-staging.json");

    let mut staging_entries = Vec::new();
    let mut atlas_entries = Vec::new();
    let mut camps: Vec<Campaign> = Vec::new();

    for path in &files {
        let raw = fs::read_to_string(path).map_err(|e| e.to_string())?;
        let camp = parse_campaign(&raw)?;
        let Some(hit) = scan_xd(&camp) else {
            return Err(format!("no fair seed for {}", camp.campaign_id));
        };
        if !hit.report.ok {
            return Err(format!("seed {} not fair for {}", hit.seed, camp.campaign_id));
        }
        staging_entries.push(format!(
            "{{\"campaign_id\":\"{id}\",\"candidate_seed\":{seed},\"path_len\":{plen},\"mean_gap\":{gap:.10},\"gold_density_early\":{e:.10},\"gold_density_mid\":{m:.10},\"gold_density_late\":{l:.10},\"total_gold\":{tg},\"cum_threat_end\":{ct},\"max_room_threat\":{mx},\"fair\":true}}",
            id = camp.campaign_id,
            seed = hit.seed,
            plen = hit.report.reach.path_len,
            gap = hit.report.pace.mean_gap,
            e = hit.report.trove.densities[0],
            m = hit.report.trove.densities[1],
            l = hit.report.trove.densities[2],
            tg = hit.report.trove.total_gold,
            ct = hit.report.threat.cum_threat_end,
            mx = hit.report.threat.max_room_threat,
        ));
        let path_json = hit
            .dungeon
            .critical_path
            .iter()
            .map(|x| x.to_string())
            .collect::<Vec<_>>()
            .join(",");
        atlas_entries.push(format!(
            "{{\"campaign_id\":\"{}\",\"seed\":{},\"start\":{},\"exit\":{},\"critical_path\":[{}]}}",
            camp.campaign_id, hit.seed, hit.dungeon.start, hit.dungeon.exit, path_json
        ));
        camps.push(camp);
    }

    let staging_body = format!(
        "{{\"schema\":\"undercroft-seed-staging-v1\",\"campaigns\":[{}]}}",
        staging_entries.join(",")
    );
    fs::write(&staging_path, &staging_body).map_err(|e| e.to_string())?;

    let staging_raw = fs::read_to_string(&staging_path).map_err(|e| e.to_string())?;
    let mut ledger_entries = Vec::new();
    let mut journal = fs::File::create(journal_path).map_err(|e| e.to_string())?;
    let mut atlas_out = Vec::new();

    for (idx, camp) in camps.iter().enumerate() {
        let seed = staging_candidate_seed(&staging_raw, &camp.campaign_id)?;
        let dungeon = generate_dungeon(camp, seed);
        let report = evaluate_fairness(camp, &dungeon);
        if !report.ok {
            return Err(format!(
                "staging re-validation failed for {} seed {}",
                camp.campaign_id, seed
            ));
        }
        writeln!(
            journal,
            "{{\"campaign_id\":\"{}\",\"candidate_seed\":{},\"accepted\":true}}",
            camp.campaign_id, seed
        )
        .map_err(|e| e.to_string())?;
        ledger_entries.push(format!(
            "{{\"campaign_id\":\"{id}\",\"selected_seed\":{seed},\"path_len\":{plen},\"mean_gap\":{gap:.10},\"gold_density_early\":{e:.10},\"gold_density_mid\":{m:.10},\"gold_density_late\":{l:.10},\"total_gold\":{tg},\"cum_threat_end\":{ct},\"max_room_threat\":{mx},\"fair\":true}}",
            id = camp.campaign_id,
            seed = seed,
            plen = report.reach.path_len,
            gap = report.pace.mean_gap,
            e = report.trove.densities[0],
            m = report.trove.densities[1],
            l = report.trove.densities[2],
            tg = report.trove.total_gold,
            ct = report.threat.cum_threat_end,
            mx = report.threat.max_room_threat,
        ));
        let path_json = dungeon
            .critical_path
            .iter()
            .map(|x| x.to_string())
            .collect::<Vec<_>>()
            .join(",");
        // Prefer regenerated atlas; fall back index keeps order aligned.
        let _ = idx;
        atlas_out.push(format!(
            "{{\"campaign_id\":\"{}\",\"seed\":{},\"start\":{},\"exit\":{},\"critical_path\":[{}]}}",
            camp.campaign_id, seed, dungeon.start, dungeon.exit, path_json
        ));
    }
    let _ = atlas_entries;

    let ledger_body = format!(
        "{{\"schema\":\"undercroft-seed-ledger-v1\",\"campaigns\":[{}]}}",
        ledger_entries.join(",")
    );
    let atlas_body = format!(
        "{{\"schema\":\"undercroft-route-atlas-v1\",\"routes\":[{}]}}",
        atlas_out.join(",")
    );
    fs::write(ledger_path, &ledger_body).map_err(|e| e.to_string())?;
    fs::write(atlas_path, &atlas_body).map_err(|e| e.to_string())?;

    let ledger_digest = sha256_hex(fs::read(ledger_path).map_err(|e| e.to_string())?.as_slice());
    let atlas_digest = sha256_hex(fs::read(atlas_path).map_err(|e| e.to_string())?.as_slice());
    let staging_digest = sha256_hex(fs::read(&staging_path).map_err(|e| e.to_string())?.as_slice());
    let seal_body = format!(
        "{{\"schema\":\"undercroft-fairness-seal-v1\",\"seal_version\":1,\"campaign_count\":{},\"ledger_digest\":\"{}\",\"atlas_digest\":\"{}\",\"staging_digest\":\"{}\"}}",
        ledger_entries.len(),
        ledger_digest,
        atlas_digest,
        staging_digest
    );
    fs::write(seal_path, seal_body).map_err(|e| e.to_string())?;
    Ok(())
}

fn staging_candidate_seed(staging_raw: &str, campaign_id: &str) -> Result<u64, String> {
    let marker = format!("\"campaign_id\":\"{campaign_id}\"");
    let idx = staging_raw
        .find(&marker)
        .ok_or_else(|| format!("staging missing {campaign_id}"))?;
    let after = &staging_raw[idx + marker.len()..];
    let needle = "\"candidate_seed\":";
    let sidx = after
        .find(needle)
        .ok_or_else(|| format!("staging seed missing for {campaign_id}"))?;
    let rest = after[sidx + needle.len()..].trim_start();
    let num: String = rest.chars().take_while(|c| c.is_ascii_digit()).collect();
    num.parse()
        .map_err(|_| format!("bad staging seed for {campaign_id}"))
}

fn parse_campaign(raw: &str) -> Result<Campaign, String> {
    Ok(Campaign {
        campaign_id: json_string(raw, "campaign_id")?,
        width: json_u32(raw, "width")?,
        height: json_u32(raw, "height")?,
        room_target: json_u32(raw, "room_target")? as usize,
        chest_count: json_u32(raw, "chest_count")? as usize,
        monster_count: json_u32(raw, "monster_count")? as usize,
        path_min: json_u32(raw, "path_min")?,
        path_max: json_u32(raw, "path_max")?,
        min_gap: json_u32(raw, "min_gap")?,
        mean_gap_min: json_f64(raw, "mean_gap_min")?,
        band_d1: json_u32(raw, "band_d1")?,
        band_d2: json_u32(raw, "band_d2")?,
        band_lo: json_f64_array3(raw, "band_lo")?,
        band_hi: json_f64_array3(raw, "band_hi")?,
        total_gold_lo: json_u32(raw, "total_gold_lo")?,
        total_gold_hi: json_u32(raw, "total_gold_hi")?,
        threat_base: json_u32(raw, "threat_base")?,
        threat_slope: json_u32(raw, "threat_slope")?,
        max_room_threat: json_u32(raw, "max_room_threat")?,
        search_origin: json_u64(raw, "search_origin")?,
        search_limit: json_u64(raw, "search_limit")?,
    })
}

fn json_string(raw: &str, key: &str) -> Result<String, String> {
    let needle = format!("\"{key}\"");
    let idx = raw.find(&needle).ok_or_else(|| format!("missing {key}"))?;
    let after = &raw[idx + needle.len()..];
    let colon = after.find(':').ok_or_else(|| format!("bad {key}"))?;
    let mut rest = after[colon + 1..].trim_start();
    if !rest.starts_with('"') {
        return Err(format!("bad string {key}"));
    }
    rest = &rest[1..];
    let end = rest.find('"').ok_or_else(|| format!("unterminated {key}"))?;
    Ok(rest[..end].to_string())
}

fn json_u32(raw: &str, key: &str) -> Result<u32, String> {
    json_u64(raw, key).map(|v| v as u32)
}

fn json_u64(raw: &str, key: &str) -> Result<u64, String> {
    let needle = format!("\"{key}\"");
    let idx = raw.find(&needle).ok_or_else(|| format!("missing {key}"))?;
    let after = &raw[idx + needle.len()..];
    let colon = after.find(':').ok_or_else(|| format!("bad {key}"))?;
    let rest = after[colon + 1..].trim_start();
    let num: String = rest
        .chars()
        .take_while(|c| c.is_ascii_digit())
        .collect();
    num.parse().map_err(|_| format!("bad u64 {key}"))
}

fn json_f64(raw: &str, key: &str) -> Result<f64, String> {
    let needle = format!("\"{key}\"");
    let idx = raw.find(&needle).ok_or_else(|| format!("missing {key}"))?;
    let after = &raw[idx + needle.len()..];
    let colon = after.find(':').ok_or_else(|| format!("bad {key}"))?;
    let rest = after[colon + 1..].trim_start();
    let num: String = rest
        .chars()
        .take_while(|c| c.is_ascii_digit() || *c == '.' || *c == '-')
        .collect();
    num.parse().map_err(|_| format!("bad f64 {key}"))
}

fn json_f64_array3(raw: &str, key: &str) -> Result<[f64; 3], String> {
    let needle = format!("\"{key}\"");
    let idx = raw.find(&needle).ok_or_else(|| format!("missing {key}"))?;
    let after = &raw[idx + needle.len()..];
    let colon = after.find(':').ok_or_else(|| format!("bad {key}"))?;
    let rest = after[colon + 1..].trim_start();
    let start = rest.find('[').ok_or_else(|| format!("bad array {key}"))?;
    let end = rest.find(']').ok_or_else(|| format!("bad array {key}"))?;
    let inner = &rest[start + 1..end];
    let parts: Vec<f64> = inner
        .split(',')
        .map(|s| s.trim().parse().map_err(|_| format!("bad array elem {key}")))
        .collect::<Result<Vec<_>, _>>()?;
    if parts.len() != 3 {
        return Err(format!("{key} must have 3 elems"));
    }
    Ok([parts[0], parts[1], parts[2]])
}

fn sha256_hex(data: &[u8]) -> String {
    sha256::hash(data)
}

mod sha256 {
    pub fn hash(msg: &[u8]) -> String {
        let mut h: [u32; 8] = [
            0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab,
            0x5be0cd19,
        ];
        let bit_len = (msg.len() as u64) * 8;
        let mut buf = msg.to_vec();
        buf.push(0x80);
        while (buf.len() % 64) != 56 {
            buf.push(0);
        }
        buf.extend_from_slice(&bit_len.to_be_bytes());
        for chunk in buf.chunks(64) {
            compress(&mut h, chunk);
        }
        let mut out = String::new();
        for v in h {
            out.push_str(&format!("{v:08x}"));
        }
        out
    }

    fn compress(h: &mut [u32; 8], chunk: &[u8]) {
        const K: [u32; 64] = [
            0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
            0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
            0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
            0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
            0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
            0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
            0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
            0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
            0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
            0xc67178f2,
        ];
        let mut w = [0u32; 64];
        for i in 0..16 {
            w[i] = u32::from_be_bytes([
                chunk[i * 4],
                chunk[i * 4 + 1],
                chunk[i * 4 + 2],
                chunk[i * 4 + 3],
            ]);
        }
        for i in 16..64 {
            let s0 = w[i - 15].rotate_right(7) ^ w[i - 15].rotate_right(18) ^ (w[i - 15] >> 3);
            let s1 = w[i - 2].rotate_right(17) ^ w[i - 2].rotate_right(19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16]
                .wrapping_add(s0)
                .wrapping_add(w[i - 7])
                .wrapping_add(s1);
        }
        let (mut a, mut b, mut c, mut d, mut e, mut f, mut g, mut hh) =
            (h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7]);
        for i in 0..64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ ((!e) & g);
            let t1 = hh
                .wrapping_add(s1)
                .wrapping_add(ch)
                .wrapping_add(K[i])
                .wrapping_add(w[i]);
            let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let t2 = s0.wrapping_add(maj);
            hh = g;
            g = f;
            f = e;
            e = d.wrapping_add(t1);
            d = c;
            c = b;
            b = a;
            a = t1.wrapping_add(t2);
        }
        h[0] = h[0].wrapping_add(a);
        h[1] = h[1].wrapping_add(b);
        h[2] = h[2].wrapping_add(c);
        h[3] = h[3].wrapping_add(d);
        h[4] = h[4].wrapping_add(e);
        h[5] = h[5].wrapping_add(f);
        h[6] = h[6].wrapping_add(g);
        h[7] = h[7].wrapping_add(hh);
    }
}
