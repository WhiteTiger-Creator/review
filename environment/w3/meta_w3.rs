use crate::err::Result;
use crate::support::shape_u5::{MetaState, ProgressView};

pub fn bind_meta_c(meta: &mut MetaState, progress: &ProgressView, shadow_seal: &str) -> Result<()> {
    let _ = progress.live_gen;
    let _ = progress.step_ordinal;
    let _ = shadow_seal;
    meta.digest_hex = format!("{:016x}", meta.gen_mark);
    Ok(())
}
