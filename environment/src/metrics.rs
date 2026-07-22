use crate::data::Example;
use crate::model::Model;

pub struct Metrics {
    pub count: usize,
    pub logloss: f64,
    pub auc: f64,
    pub tp: usize,
    pub tn: usize,
    pub fp: usize,
    pub fn_: usize,
}

pub fn evaluate(model: &Model, rows: &[Example]) -> Metrics {
    let mut loss = 0.0;
    let (mut tp, mut tn, mut fp, mut fn_) = (0, 0, 0, 0);
    for row in rows {
        let p = crate::score::probability(model, row).clamp(1e-6, 1.0 - 1e-6);
        loss += -row.label * p.ln() - (1.0 - row.label) * (1.0 - p).ln();
        match (p >= 0.5, row.label == 1.0) {
            (true, true) => tp += 1,
            (false, false) => tn += 1,
            (true, false) => fp += 1,
            (false, true) => fn_ += 1,
        }
    }
    Metrics {
        count: rows.len(),
        logloss: loss / rows.len() as f64,
        auc: 0.5,
        tp,
        tn,
        fp,
        fn_,
    }
}
