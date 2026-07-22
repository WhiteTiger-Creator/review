use crate::data::Example;

pub fn ingest_dataset(path: &str) -> Result<Vec<Example>, String> {
    crate::data::load(path)
}
