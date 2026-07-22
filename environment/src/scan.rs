pub fn fields(line: &str) -> Vec<&str> {
    line.split_whitespace().collect()
}
