use crate::data::Example;
use crate::model::Model;

pub fn score(model: &Model, row: &Example) -> f64 {
    let mut total = model.bias;
    for (name, x) in &row.features {
        if let Some(w) = model.features.get(name) {
            total += w.linear * x;
        }
    }
    for factor in 0..model.factors {
        let mut sum = 0.0;
        let mut squares = 0.0;
        for (name, x) in &row.features {
            if let Some(w) = model.features.get(name) {
                let vx = w.latent[factor] * x;
                sum += vx;
                squares += vx * vx;
            }
        }
        total += 0.5 * (sum * sum - squares);
    }
    total
}

pub fn probability(model: &Model, row: &Example) -> f64 {
    let z = score(model, row).clamp(-35.0, 35.0);
    1.0 / (1.0 + (-z).exp())
}
