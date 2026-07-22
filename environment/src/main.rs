mod model;
mod order;
mod render;
mod scan;

use std::io::{self, Read, Write};

fn main() {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input).unwrap();
    let mut out = String::new();
    let mut sid = String::new();
    let mut resolver = order::Resolver::new();
    for line in input.lines() {
        let f = scan::fields(line);
        if f.is_empty() {
            continue;
        }
        match f[0] {
            "SCENARIO" => {
                sid = if f.len() > 1 {
                    f[1].to_string()
                } else {
                    String::new()
                };
                // Each scenario is an independent resolver session.
                resolver = order::Resolver::new();
            }
            "REQUIRE" => {
                if f.len() >= 2 {
                    let v = model::parse(f[1]);
                    resolver.require(&v);
                }
            }
            "CMP" => {
                if f.len() >= 4 {
                    let a = model::parse(f[2]);
                    let b = model::parse(f[3]);
                    let r = resolver.install(&a, &b);
                    out.push_str(&render::line(&sid, f[1], &r));
                    out.push('\n');
                }
            }
            _ => {}
        }
    }
    io::stdout().write_all(out.as_bytes()).unwrap();
}
