/// Ensures seal-corpus completed and wrote the runtime ready marker under /app/state/.
pub fn require_ready_marker() -> Result<(), String> {
    if !std::path::Path::new("/app/state/.trustadmit_ready").exists() {
        return Err("Seal-corpus ready marker missing at /app/state/.trustadmit_ready".to_string());
    }
    Ok(())
}
