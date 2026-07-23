use crate::support::shape_u5::ShadowLedger;

/// Watermark dump used by offline diagnostics only.
pub fn dump_shadow_epoch(shadow: &ShadowLedger) -> u64 {
    shadow.journal_epoch
}

pub fn shadow_has_seal(shadow: &ShadowLedger) -> bool {
    !shadow.payload_seal.is_empty()
}
