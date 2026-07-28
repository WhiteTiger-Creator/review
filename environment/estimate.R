args <- commandArgs(trailingOnly=TRUE)
output_file <- if (length(args) >= 2) args[[2]] else "/app/outputs/results.csv"
dir.create(dirname(output_file), recursive=TRUE, showWarnings=FALSE)
writeLines(
  paste(
    "case_id,selected_portfolio,feasible_count,robust_value,full_value",
    "branching_radius,worst_deletion_radius,worst_pair_radius",
    "effective_sample_size,pair_effective_sample_size",
    "jackknife_instability,second_order_instability,policy_dispersion",
    "mixture_concentration,deletion_code,pair_deletion_code,audit_signature",
    sep = ","
  ),
  output_file
)
