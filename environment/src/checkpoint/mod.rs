use crate::model::Model;

pub fn write_training_snapshot(model: &Model, path: &str) -> Result<(), String> {
    crate::persist::save(model, path)
}

pub fn load_training_snapshot(path: &str) -> Result<Model, String> {
    crate::persist::load(path)
}
