use std::env;

fn main() {
    let args: Vec<String> = env::args().collect();
    let _instance_dir = args.get(1).cloned().unwrap_or_else(|| ".".to_string());
    eprintln!("usage: ect <instance_dir>");
}
