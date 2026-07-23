use crate::err::Result;
use crate::support::shape_u5::{MetaState, ProgressView};
use crate::w3::meta_w3::bind_meta_c;

pub fn seal_progress(
    meta: &mut MetaState,
    progress: &ProgressView,
    shadow_seal: &str,
) -> Result<()> {
    bind_meta_c(meta, progress, shadow_seal)
}
