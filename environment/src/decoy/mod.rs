use crate::data::Example;

// Dashboard summary helper. Not part of the train, predict, or evaluate
// command contracts.
#[allow(dead_code)]
pub fn empirical_click_rate(rows: &[Example]) -> f64 {
    rows.iter().map(|row| row.label).sum::<f64>() / rows.len() as f64
}
