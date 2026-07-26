args <- commandArgs(trailingOnly=TRUE)
output_file <- if (length(args) >= 2) args[[2]] else "/app/outputs/results.csv"
dir.create(dirname(output_file), recursive=TRUE, showWarnings=FALSE)
writeLines(
  paste(
    "case_id,selected_policy,feasible_count,robust_value,full_value",
    "branching_radius,worst_deletion_radius,effective_sample_size",
    "jackknife_instability,deletion_code,audit_signature",
    sep = ","
  ),
  output_file
)
