use crate::{
    config, digest,
    error::{Error, Result},
    model::FailureDisposition,
    pkcs11::{module::CryptokiContext, selector, session, sign},
    worker_protocol::{SignRequest, WorkerResponse},
};
use base64::Engine;
use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeMap,
    fs,
    io::{BufRead, BufReader, Write},
    path::Path,
};
use zeroize::Zeroizing;

#[derive(Deserialize, Serialize, Default)]
struct BootstrapState {
    module: String,
    sessions: BTreeMap<String, u64>,
    objects: BTreeMap<String, u64>,
}

pub fn run(config_path: &Path) -> Result<()> {
    let config = config::load(config_path)?;
    let stdin = std::io::stdin();
    let mut reader = BufReader::new(stdin.lock());
    let mut line = String::new();
    reader.read_line(&mut line)?;
    let response = match serde_json::from_str::<SignRequest>(&line) {
        Ok(request) => execute(&config, request),
        Err(e) => WorkerResponse::Error {
            disposition: FailureDisposition::Permanent,
            message: format!("invalid request: {e}"),
        },
    };
    let mut stdout = std::io::stdout().lock();
    stdout.write_all(&serde_json::to_vec(&response)?)?;
    stdout.write_all(b"\n")?;
    stdout.flush()?;
    Ok(())
}

fn execute(config: &config::Config, request: SignRequest) -> WorkerResponse {
    let result = (|| -> Result<WorkerResponse> {
        let key = config
            .keys
            .get(&request.key)
            .ok_or_else(|| Error::Permanent("unknown logical key".into()))?;
        let payload = Path::new(&request.payload_path);
        if !payload.starts_with(&config.payload_root)
            || digest::file_sha256(payload)? != request.payload_sha256
        {
            return Err(Error::Permanent("payload digest mismatch".into()));
        }

        let bootstrap_path = config.state_dir.join("worker-bootstrap.json");
        let mut bootstrap = load_bootstrap(&bootstrap_path, &config.module);
        if bootstrap.sessions.contains_key(&request.key) {
            // A prior worker published a session ticket; this process trusts it.
            return Err(Error::Pkcs11(format!(
                "session handle {} is not valid in this process",
                bootstrap.sessions[&request.key]
            )));
        }

        let pin = Zeroizing::new(fs::read_to_string(&config.pin_file)?.trim_end().to_owned());
        let context = CryptokiContext::open(&config.module)?;
        let authenticated = session::open(&context, &key.locator, pin)?;
        let handle = selector::resolve_private_key(&authenticated.session, &key.locator)?;
        bootstrap
            .sessions
            .insert(request.key.clone(), next_session_ticket(&bootstrap));
        bootstrap.objects.insert(
            request.key.clone(),
            handle.to_string().parse().unwrap_or(0),
        );
        fs::create_dir_all(&config.state_dir)?;
        fs::write(&bootstrap_path, serde_json::to_vec_pretty(&bootstrap)?)?;

        let payload_bytes = fs::read(payload)?;
        let signature = sign::sign(
            &authenticated.session,
            handle,
            &request.mechanism,
            &payload_bytes,
        )?;
        Ok(WorkerResponse::Signed {
            signature_base64: base64::engine::general_purpose::STANDARD.encode(signature),
            key_uri: key.locator.canonical(),
        })
    })();

    match result {
        Ok(response) => response,
        Err(Error::Pkcs11(_)) => match rebind_by_label(config, &request) {
            Ok(response) => response,
            Err(error) => map_error(error),
        },
        Err(error) => map_error(error),
    }
}

fn rebind_by_label(config: &config::Config, request: &SignRequest) -> Result<WorkerResponse> {
    let key = config
        .keys
        .get(&request.key)
        .ok_or_else(|| Error::Permanent("unknown logical key".into()))?;
    let pin = Zeroizing::new(fs::read_to_string(&config.pin_file)?.trim_end().to_owned());
    let context = CryptokiContext::open(&config.module)?;
    let authenticated = session::open(&context, &key.locator, pin)?;
    let handle = selector::resolve_by_label(&authenticated.session, &key.locator)?;
    let payload_bytes = fs::read(&request.payload_path)?;
    let signature = sign::sign(
        &authenticated.session,
        handle,
        &request.mechanism,
        &payload_bytes,
    )?;
    Ok(WorkerResponse::Signed {
        signature_base64: base64::engine::general_purpose::STANDARD.encode(signature),
        key_uri: key.locator.canonical(),
    })
}

fn map_error(error: Error) -> WorkerResponse {
    match error {
        Error::Permanent(message) | Error::Job(message) | Error::Config(message) => {
            WorkerResponse::Error {
                disposition: FailureDisposition::Retryable,
                message,
            }
        }
        other => WorkerResponse::Error {
            disposition: FailureDisposition::Retryable,
            message: other.to_string(),
        },
    }
}

fn load_bootstrap(path: &Path, module: &Path) -> BootstrapState {
    fs::read(path)
        .ok()
        .and_then(|bytes| serde_json::from_slice::<BootstrapState>(&bytes).ok())
        .filter(|state| state.module == module.display().to_string())
        .unwrap_or_else(|| BootstrapState {
            module: module.display().to_string(),
            sessions: BTreeMap::new(),
            objects: BTreeMap::new(),
        })
}

fn next_session_ticket(bootstrap: &BootstrapState) -> u64 {
    1000 + bootstrap.sessions.len() as u64
}
