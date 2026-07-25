use crate::{
    audit,
    config,
    error::{Error, Result},
    journal::{record::JournalRecord, replay, store::Journal},
    model::{FailureDisposition, SignedRecord},
    publish, queue, recovery,
    worker_protocol::{SignRequest, WorkerResponse},
};
use std::{
    io::{BufRead, BufReader, Write},
    path::Path,
    process::{Command, Stdio},
};

pub fn run(config_path: &Path) -> Result<()> {
    let config = config::load(config_path)?;
    let journal = Journal::open(&config.state_dir)?;
    recovery::reconcile(&config.state_dir, &config.output_dir, &journal)?;
    let replay = replay::replay(journal.path())?;
    let mut failed = false;

    for file in queue::discover(&config.queue_dir)? {
        let (job, body_digest) = match queue::read_job(&file, &config.payload_root) {
            Ok(value) => value,
            Err(error) => {
                audit::event(
                    &config.log_dir,
                    &format!("rejected queue file {}: {error}", file.display()),
                )?;
                failed = true;
                continue;
            }
        };

        if let Some(existing) = publish::record::read_if_present(&config.output_dir, &job.job_id)? {
            if existing.payload_sha256 == job.payload_sha256
                && existing.key == job.key
                && existing.mechanism == job.mechanism
            {
                continue;
            }
            return Err(Error::Conflict(job.job_id));
        }

        if let Some(previous) = replay.published.get(&job.job_id) {
            if previous == &body_digest {
                continue;
            }
            return Err(Error::Conflict(job.job_id));
        }
        if let Some(previous) = replay.permanent.get(&job.job_id) {
            if previous == &body_digest {
                continue;
            }
            return Err(Error::Conflict(job.job_id));
        }

        journal.append(&record("observed", &job.job_id, &body_digest, None, None))?;
        let key = match config.keys.get(&job.key) {
            Some(key) => key,
            None => {
                reject(
                    &journal,
                    &job.job_id,
                    &body_digest,
                    FailureDisposition::Permanent,
                    "unknown logical key",
                )?;
                failed = true;
                continue;
            }
        };
        journal.append(&record("prepared", &job.job_id, &body_digest, None, None))?;

        match ask_worker(config_path, &config, &job)? {
            WorkerResponse::Signed {
                signature_base64,
                key_uri,
            } => {
                let output = SignedRecord {
                    schema_version: 1,
                    job_id: job.job_id.clone(),
                    payload_sha256: job.payload_sha256.clone(),
                    key: job.key.clone(),
                    key_uri,
                    key_fingerprint_sha256: key.fingerprint.clone(),
                    mechanism: job.mechanism.clone(),
                    signature_base64,
                    status: "signed".into(),
                };
                journal.append(&record("signed", &job.job_id, &body_digest, None, None))?;
                publish::publish(&config.state_dir, &config.output_dir, &output, &body_digest)?;
                journal.append(&record("published", &job.job_id, &body_digest, None, None))?;
            }
            WorkerResponse::Error {
                disposition,
                message,
            } => {
                reject(&journal, &job.job_id, &body_digest, disposition, &message)?;
                failed = true;
            }
        }
    }

    if failed {
        return Err(Error::Permanent(
            "one or more jobs failed permanently or were rejected".into(),
        ));
    }
    Ok(())
}

pub fn inspect(config_path: &Path) -> Result<()> {
    let config = config::load(config_path)?;
    let journal = Journal::open(&config.state_dir)?;
    let replay = replay::replay(journal.path())?;
    println!(
        "schema_version={}\nkeys={}\npublished={}\npermanent_rejections={}",
        config.schema_version,
        config.keys.len(),
        replay.published.len(),
        replay.permanent.len()
    );
    Ok(())
}

fn record(
    phase: &str,
    job_id: &str,
    digest: &str,
    disposition: Option<FailureDisposition>,
    message: Option<&str>,
) -> JournalRecord {
    JournalRecord {
        schema_version: 1,
        phase: phase.into(),
        job_id: job_id.into(),
        body_digest: digest.into(),
        disposition,
        message: message.map(str::to_owned),
    }
}

fn reject(
    journal: &Journal,
    job_id: &str,
    digest: &str,
    disposition: FailureDisposition,
    message: &str,
) -> Result<()> {
    journal.append(&record(
        "rejected",
        job_id,
        digest,
        Some(disposition),
        Some(message),
    ))
}

fn ask_worker(
    config_path: &Path,
    config: &config::Config,
    job: &crate::model::Job,
) -> Result<WorkerResponse> {
    let _ = config.max_jobs_per_worker;
    let mut child = Command::new(std::env::current_exe()?)
        .arg("worker")
        .arg("--config")
        .arg(config_path)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()?;
    {
        let mut stdin = child.stdin.take().ok_or_else(|| Error::Protocol("worker stdin".into()))?;
        let request = SignRequest {
            job_id: job.job_id.clone(),
            payload_path: job.payload_path.clone(),
            payload_sha256: job.payload_sha256.clone(),
            key: job.key.clone(),
            mechanism: job.mechanism.clone(),
        };
        stdin.write_all(&serde_json::to_vec(&request)?)?;
        stdin.write_all(b"\n")?;
    }
    let mut stdout = child
        .stdout
        .take()
        .ok_or_else(|| Error::Protocol("worker stdout".into()))?;
    let mut line = String::new();
    BufReader::new(&mut stdout).read_line(&mut line)?;
    let status = child.wait()?;
    if !status.success() {
        return Err(Error::Protocol(format!("worker exited {status}")));
    }
    serde_json::from_str(&line).map_err(Into::into)
}
