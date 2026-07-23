use crate::Row;

pub fn hud_lines(rows: &[Row]) -> Vec<String> {
    rows.iter()
        .map(|r| format!("arm={} tok={}", r.arm, r.weight_tok))
        .collect()
}
