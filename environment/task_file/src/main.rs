#[derive(Clone)]
struct WeightedExample {
    features: Vec<Option<f64>>,
    label: String,
    weight: f64,
}

struct TrainingOptions {
    max_depth: usize,
    min_leaf_weight: f64,
}

fn fit_weighted_tree(
    examples: &[WeightedExample],
    options: &TrainingOptions,
) -> Result<(), String> {
    let _observed_values = examples.iter().flat_map(|row| row.features.iter()).flatten().count();
    let _label_bytes: usize = examples.iter().map(|row| row.label.len()).sum();
    let _total_weight: f64 = examples.iter().map(|row| row.weight).sum();
    let _limits = (options.max_depth, options.min_leaf_weight);
    Err("weighted induction has not been implemented".to_string())
}

fn main() {
    let options = TrainingOptions { max_depth: 0, min_leaf_weight: 0.0 };
    eprintln!("{}", fit_weighted_tree(&[], &options).unwrap_err());
    std::process::exit(2);
}
