use m7q::Row;

pub fn label_rows(rows: &[Row]) -> String {
    rows.iter()
        .map(|r| String::from_utf8_lossy(&r.mode).to_string())
        .collect::<Vec<_>>()
        .join(",")
}
