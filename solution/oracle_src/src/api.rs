//! Localhost policy API client.

use crate::error::FatalError;
use serde_json::Value;
use std::time::Duration;

pub struct PolicySnapshot {
    pub environment: String,
    pub policy_revision: String,
    pub fragment_rows: Vec<(String, String)>,
    pub identity: Value,
    pub database: Value,
    pub access: Value,
}

const FRAGMENT_ORDER: [&str; 3] = ["identity", "database", "access"];

pub fn fetch_snapshot(base_url: &str, environment: &str) -> Result<PolicySnapshot, FatalError> {
    let manifest_url = format!(
        "{}/v1/policy/manifest?environment={}",
        base_url.trim_end_matches('/'),
        urlencoding(environment)
    );
    let (status, headers, body) = http_get(&manifest_url)?;
    if (300..400).contains(&status) {
        return Err(FatalError::new("policy_api_redirect_forbidden", ""));
    }
    if status != 200 {
        return Err(FatalError::new("policy_api_status_error", format!("status={status}")));
    }
    if !valid_json_content_type(headers.get("content-type").map(String::as_str)) {
        return Err(FatalError::new("policy_api_content_type_invalid", ""));
    }
    let manifest: Value = serde_json::from_slice(&body).map_err(|_| FatalError::new("policy_manifest_invalid", ""))?;
    let env = manifest.get("environment").and_then(|v| v.as_str()).ok_or_else(|| FatalError::new("policy_manifest_invalid", ""))?;
    if env != environment {
        return Err(FatalError::new("policy_environment_mismatch", ""));
    }
    let revision = manifest
        .get("policy_revision")
        .and_then(|v| v.as_str())
        .ok_or_else(|| FatalError::new("policy_manifest_invalid", ""))?
        .to_string();
    let fragments = manifest
        .get("fragments")
        .and_then(|v| v.as_array())
        .ok_or_else(|| FatalError::new("policy_manifest_invalid", ""))?;
    let mut seen = std::collections::HashSet::new();
    for f in fragments {
        let fid = f.get("fragment_id").and_then(|v| v.as_str()).unwrap_or("");
        if !seen.insert(fid.to_string()) {
            return Err(FatalError::new("duplicate_policy_fragment", ""));
        }
    }
    if seen.len() != 3 || !FRAGMENT_ORDER.iter().all(|id| seen.contains(*id)) {
        if fragments.len() < 3 {
            return Err(FatalError::new("missing_policy_fragment", ""));
        }
        for id in &seen {
            if !FRAGMENT_ORDER.contains(&id.as_str()) {
                return Err(FatalError::new("unknown_policy_fragment", ""));
            }
        }
        return Err(FatalError::new("missing_policy_fragment", ""));
    }

    let mut fragment_rows = Vec::new();
    let mut docs = std::collections::BTreeMap::new();
    for fid in FRAGMENT_ORDER {
        let entry = fragments
            .iter()
            .find(|f| f.get("fragment_id").and_then(|v| v.as_str()) == Some(fid))
            .ok_or_else(|| FatalError::new("missing_policy_fragment", ""))?;
        let digest = entry
            .get("body_sha256")
            .and_then(|v| v.as_str())
            .ok_or_else(|| FatalError::new("invalid_fragment_digest", ""))?;
        if !digest.chars().all(|c| c.is_ascii_hexdigit()) || digest.len() != 64 {
            return Err(FatalError::new("invalid_fragment_digest", ""));
        }
        fragment_rows.push((fid.to_string(), digest.to_string()));
        let url = format!(
            "{}/v1/policy/fragments/{}?environment={}&revision={}",
            base_url.trim_end_matches('/'),
            fid,
            urlencoding(environment),
            urlencoding(&revision)
        );
        let (fstatus, fheaders, fbody) = http_get(&url)?;
        if fstatus != 200 {
            return Err(FatalError::new("policy_api_status_error", ""));
        }
        if !valid_json_content_type(fheaders.get("content-type").map(String::as_str)) {
            return Err(FatalError::new("policy_api_content_type_invalid", ""));
        }
        let actual = crate::canonical::sha256_hex(&fbody);
        if actual != digest {
            return Err(FatalError::new("fragment_digest_mismatch", ""));
        }
        let frag: Value = serde_json::from_slice(&fbody).map_err(|_| FatalError::new("malformed_policy_fragment", ""))?;
        if frag.get("fragment_id").and_then(|v| v.as_str()) != Some(fid) {
            return Err(FatalError::new("fragment_id_mismatch", ""));
        }
        if frag.get("policy_revision").and_then(|v| v.as_str()) != Some(revision.as_str()) {
            return Err(FatalError::new("policy_revision_mismatch", ""));
        }
        if frag.get("environment").and_then(|v| v.as_str()) != Some(environment) {
            return Err(FatalError::new("policy_environment_mismatch", ""));
        }
        docs.insert(fid.to_string(), frag.get("document").cloned().unwrap_or(Value::Null));
    }
    Ok(PolicySnapshot {
        environment: environment.to_string(),
        policy_revision: revision,
        fragment_rows,
        identity: docs["identity"].clone(),
        database: docs["database"].clone(),
        access: docs["access"].clone(),
    })
}

fn urlencoding(s: &str) -> String {
    s.chars()
        .map(|c| match c {
            'A'..='Z' | 'a'..='z' | '0'..='9' | '-' | '_' | '.' | '~' => c.to_string(),
            _ => format!("%{:02X}", c as u8),
        })
        .collect()
}

fn valid_json_content_type(ct: Option<&str>) -> bool {
    ct.map(|v| v.split(';').next().unwrap_or(v).trim().eq_ignore_ascii_case("application/json"))
        .unwrap_or(false)
}

fn http_get(url: &str) -> Result<(u16, std::collections::HashMap<String, String>, Vec<u8>), FatalError> {
    let host = url
        .strip_prefix("http://")
        .and_then(|u| u.split('/').next())
        .unwrap_or("");
    if !host.starts_with("127.0.0.1") && host != "localhost" && !host.starts_with("localhost:") {
        return Err(FatalError::new("policy_api_unavailable", "non-localhost"));
    }
    let agent = ureq::AgentBuilder::new()
        .timeout_connect(Duration::from_secs(10))
        .timeout_read(Duration::from_secs(10))
        .redirects(0)
        .build();
    let result = agent.get(url).call();
    let resp = match result {
        Ok(resp) => resp,
        Err(ureq::Error::Status(_code, resp)) => resp,
        Err(e) => {
            let msg = e.to_string();
            if msg.to_ascii_lowercase().contains("timed out") {
                return Err(FatalError::new("policy_api_timeout", msg));
            }
            return Err(FatalError::new("policy_api_unavailable", msg));
        }
    };
    let status = resp.status();
    let mut headers = std::collections::HashMap::new();
    for name in resp.headers_names() {
        if let Some(v) = resp.header(&name) {
            headers.insert(name.to_ascii_lowercase(), v.to_string());
        }
    }
    let body = resp.into_string().unwrap_or_default().into_bytes();
    Ok((status, headers, body))
}
