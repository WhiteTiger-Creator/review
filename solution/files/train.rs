use std::collections::{BTreeMap, BTreeSet};

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
    let mut name_set = BTreeSet::new();
    for row in rows {
        name_set.extend(row.features.keys().cloned());
    }
    let names: Vec<String> = name_set.into_iter().collect();
    let mut model = Model::new(&names, options.factors, options.seed);
    let mut order: Vec<usize> = (0..rows.len()).collect();

    for epoch in 0..options.epochs {
        crate::rng::shuffle(&mut order, options.seed, epoch);
        let rate = options.lr / (1.0 + 0.1 * epoch as f64);
        for batch_indices in order.chunks(options.batch) {
            let mut bias_grad = 0.0;
            let mut linear_grad: BTreeMap<String, f64> =
                names.iter().map(|n| (n.clone(), 0.0)).collect();
            let mut latent_grad: BTreeMap<String, Vec<f64>> = names
                .iter()
                .map(|n| (n.clone(), vec![0.0; options.factors]))
                .collect();

            for &idx in batch_indices {
                let row = &rows[idx];
                let g = crate::score::probability(&model, row) - row.label;
                bias_grad += g;
                let mut sums = vec![0.0; options.factors];
                for (name, x) in &row.features {
                    if let Some(w) = model.features.get(name) {
                        for (f, sum) in sums.iter_mut().enumerate() {
                            *sum += w.latent[f] * x;
                        }
                    }
                }
                for (name, x) in &row.features {
                    if let Some(w) = model.features.get(name) {
                        *linear_grad.get_mut(name).unwrap() +=
                            g * x + options.l2 * w.linear;
                        let target = latent_grad.get_mut(name).unwrap();
                        for f in 0..options.factors {
                            target[f] += g * x * (sums[f] - w.latent[f] * x)
                                + options.l2 * w.latent[f];
                        }
                    }
                }
                // Regularize parameters absent from this sparse row once per example.
                for name in &names {
                    if !row.features.contains_key(name) {
                        let w = model.features.get(name).unwrap();
                        *linear_grad.get_mut(name).unwrap() += options.l2 * w.linear;
                        let target = latent_grad.get_mut(name).unwrap();
                        for f in 0..options.factors {
                            target[f] += options.l2 * w.latent[f];
                        }
                    }
                }
            }

            let scale = rate / batch_indices.len() as f64;
            model.bias -= scale * bias_grad;
            for name in &names {
                let weights = model.features.get_mut(name).unwrap();
                weights.linear -= scale * linear_grad[name];
                for f in 0..options.factors {
                    weights.latent[f] -= scale * latent_grad[name][f];
                }
            }
        }
    }
    model
}
