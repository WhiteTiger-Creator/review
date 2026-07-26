output_dir_from_env <- function() {
  out <- Sys.getenv("OUT_DIR", "")
  if (nzchar(out)) return(out)
  out <- Sys.getenv("OUTPUT_DIR", "")
  if (nzchar(out)) return(out)
  "/app/outputs"
}
