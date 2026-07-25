use crate::{
    config, digest,
    error::{Error, Result},
    model::FailureDisposition,
    pkcs11::{module::CryptokiContext, selector, session, sign},
    worker_protocol::{SignRequest, WorkerResponse},
};
use base64::Engine;
use std::{
    fs,
    io::{BufRead, BufReader, Write},
    path::Path,
};
use zeroize::Zeroizing;

pub fn run(config_path: &Path) -> Result<()> {
    // Each worker process owns a fresh Cryptoki context for the request on stdin.
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
        let pin = Zeroizing::new(fs::read_to_string(&config.pin_file)?.trim_end().to_owned());
        let context = CryptokiContext::open(&config.module)?;
        let authenticated = session::open(&context, &key.locator, pin)?;
        let handle = selector::resolve_private_key(&authenticated.session, &key.locator)?;
        let signature = sign::sign(
            &authenticated.session,
            handle,
            &request.mechanism,
            &fs::read(payload)?,
        )?;
        Ok(WorkerResponse::Signed {
            signature_base64: base64::engine::general_purpose::STANDARD.encode(signature),
            key_uri: key.locator.canonical(),
        })
    })();
    match result {
        Ok(response) => response,
        Err(Error::Permanent(message) | Error::Job(message) | Error::Config(message)) => {
            WorkerResponse::Error {
                disposition: FailureDisposition::Permanent,
                message,
            }
        }
        Err(error) => WorkerResponse::Error {
            disposition: FailureDisposition::Retryable,
            message: error.to_string(),
        },
    }
}
