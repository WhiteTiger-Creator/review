use crate::data::Example;
use crate::model::Model;

pub fn score(model: &Model, row: &Example) -> f64 {
    let mut total = model.bias;
    for (name, x) in &row.features {
        if let Some(w) = model.features.get(name) {
            total += w.linear * x;
        }
    }
    total
}

pub fn probability(model: &Model, row: &Example) -> f64 {
    let z = score(model, row).clamp(-20.0, 20.0);
    1.0 / (1.0 + (-z).exp())
}
