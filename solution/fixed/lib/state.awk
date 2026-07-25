function hs_state_load(path,    line) {
    hs_state_status = "DISCOVERING"
    if ((getline line < path) > 0 && line ~ /FINISHED/) hs_state_status = "FINISHED"
    close(path)
}
function hs_state_save(path) {
    print "{\"status\":\"" hs_state_status "\"}" > path
    close(path)
}
