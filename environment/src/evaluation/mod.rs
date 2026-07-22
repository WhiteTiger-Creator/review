use crate::data::Example;
use crate::metrics::Metrics;
use crate::model::Model;

pub fn evaluate_snapshot(model: &Model, rows: &[Example]) -> Metrics {
    crate::metrics::evaluate(model, rows)
}
