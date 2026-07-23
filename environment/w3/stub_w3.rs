use crate::support::shape_u5::MetaState;

/// Loads meta blobs without progress binding for bench mode.
pub fn load_meta_blob(raw: &MetaState) -> MetaState {
    MetaState {
        schema: raw.schema,
        gen_mark: 0,
        step_ordinal: 0,
        digest_hex: String::new(),
    }
}

pub fn bench_meta_len(raw: &MetaState) -> usize {
    raw.digest_hex.len()
}
