use std::collections::BTreeMap;

#[derive(Clone, Debug)]
pub struct Weights {
    pub linear: f64,
    pub latent: Vec<f64>,
}

#[derive(Clone, Debug)]
pub struct Model {
    pub factors: usize,
    pub bias: f64,
    pub features: BTreeMap<String, Weights>,
}

impl Model {
    pub fn new(names: &[String], factors: usize, seed: u64) -> Self {
        let mut features = BTreeMap::new();
        for (i, name) in names.iter().enumerate() {
            let latent = (0..factors)
                .map(|f| crate::rng::initial(seed, i, f))
                .collect();
            features.insert(
                name.clone(),
                Weights {
                    linear: 0.0,
                    latent,
                },
            );
        }
        Self {
            factors,
            bias: 0.0,
            features,
        }
    }
}
