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
    let mut scored = Vec::new();
    let mut loss = 0.0;
    let (mut tp, mut tn, mut fp, mut fn_) = (0, 0, 0, 0);
    for row in rows {
        let p = crate::score::probability(model, row);
        let safe = p.clamp(1e-15, 1.0 - 1e-15);
        loss += -row.label * safe.ln() - (1.0 - row.label) * (1.0 - safe).ln();
        scored.push((p, row.label));
        match (p >= 0.5, row.label == 1.0) {
            (true, true) => tp += 1,
            (false, false) => tn += 1,
            (true, false) => fp += 1,
            (false, true) => fn_ += 1,
        }
    }
    scored.sort_by(|a, b| a.0.total_cmp(&b.0));
    let positives = scored.iter().filter(|x| x.1 == 1.0).count();
    let negatives = scored.len() - positives;
    let mut positive_rank_sum = 0.0;
    let mut start = 0;
    while start < scored.len() {
        let mut end = start + 1;
        while end < scored.len() && scored[end].0 == scored[start].0 {
            end += 1;
        }
        let average_rank = ((start + 1 + end) as f64) / 2.0;
        positive_rank_sum += scored[start..end]
            .iter()
            .filter(|x| x.1 == 1.0)
            .count() as f64
            * average_rank;
        start = end;
    }
    let auc = if positives == 0 || negatives == 0 {
        0.0
    } else {
        (positive_rank_sum - (positives * (positives + 1)) as f64 / 2.0)
            / (positives * negatives) as f64
    };
    Metrics {
        count: rows.len(),
        logloss: loss / rows.len() as f64,
        auc,
        tp,
        tn,
        fp,
        fn_,
    }
}
