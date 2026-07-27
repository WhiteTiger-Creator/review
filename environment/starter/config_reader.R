read_key_value_config <- function(config_dir = Sys.getenv("CONFIG_DIR", "/app/config")) {
  cfg <- read.csv(file.path(config_dir, "model_config.csv"), stringsAsFactors = FALSE)
  values <- as.list(cfg$value)
  names(values) <- cfg$key
  values
}

read_feature_roles <- function(config_dir = Sys.getenv("CONFIG_DIR", "/app/config")) {
  read.csv(file.path(config_dir, "feature_roles.csv"), stringsAsFactors = FALSE)
}

read_feature_policies <- function(config_dir = Sys.getenv("CONFIG_DIR", "/app/config")) {
  config <- read_key_value_config(config_dir)
  read.csv(file.path(config_dir, config$feature_policy_file), stringsAsFactors = FALSE)
}
