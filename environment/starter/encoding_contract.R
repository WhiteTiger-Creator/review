missing_token <- function(values) {
  text <- trimws(as.character(values))
  text[is.na(values) | text %in% c("", "?", "MISSING", "NA", "NaN")] <- "__missing__"
  text
}

full_level_order <- function(values, append_other = TRUE) {
  levels <- sort(unique(missing_token(values)))
  if (!("__missing__" %in% levels)) {
    levels <- c(levels, "__missing__")
  }
  if (append_other && !("__other__" %in% levels)) {
    levels <- c(levels, "__other__")
  }
  levels
}
