use std::collections::BTreeSet;

use crate::data::Example;
use crate::model::Model;

pub struct Options {
    pub factors: usize,
    pub epochs: usize,
    pub batch: usize,
    pub lr: f64,
    pub l2: f64,
    pub seed: u64,
}

pub fn fit(rows: &[Example], options: &Options) -> Model {
    let mut names = BTreeSet::new();
    for row in rows {
        names.extend(row.features.keys().cloned());
    }
    let names: Vec<String> = names.into_iter().collect();
    let mut model = Model::new(&names, options.factors, options.seed);
    let mut order: Vec<usize> = (0..rows.len()).collect();

    for epoch in 0..options.epochs {
        crate::rng::shuffle(&mut order, options.seed, epoch);
        let rate = options.lr;
        for &idx in &order {
            let row = &rows[idx];
            let gradient = crate::score::probability(&model, row) - row.label;
            model.bias -= rate * (gradient + options.l2 * model.bias);
            for (name, x) in &row.features {
                if let Some(w) = model.features.get_mut(name) {
                    w.linear -= rate * gradient * x;
                }
            }
        }
    }
    model
}
