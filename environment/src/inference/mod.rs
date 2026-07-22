use crate::data::Example;
use crate::model::Model;

pub fn export_predictions(model: &Model, rows: &[Example]) -> String {
    let mut output = String::new();
    for row in rows {
        output.push_str(&format!("{:.12}\n", crate::score::probability(model, row)));
    }
    output
}
