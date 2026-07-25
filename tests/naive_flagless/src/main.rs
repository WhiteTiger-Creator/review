mod bits;
mod driver;
mod fmt;
mod hex;
mod logb;
mod mode;
mod pack;
mod scalbn;

use std::io::{self, BufWriter, Read, Write};

fn main() {
    let mut input = String::new();
    if io::stdin().read_to_string(&mut input).is_err() {
        std::process::exit(1);
    }
    let stdout = io::stdout();
    let mut out = BufWriter::new(stdout.lock());
    for line in input.lines() {
        if let Some(reply) = driver::handle(line) {
            let _ = writeln!(out, "{}", reply);
        }
    }
    let _ = out.flush();
}
