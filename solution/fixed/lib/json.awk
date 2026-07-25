# Minimal deterministic JSON helpers for HarborSeal
function hs_json_trim(s) { sub(/^[ \t\r\n]+/, "", s); sub(/[ \t\r\n]+$/, "", s); return s }
function hs_json_unescape(s,    out, i, c, hex) {
    out = ""
    for (i = 1; i <= length(s); i++) {
        c = substr(s, i, 1)
        if (c != "\\") { out = out c; continue }
        i++
        c = substr(s, i, 1)
        if (c == "n") out = out "\n"
        else if (c == "t") out = out "\t"
        else if (c == "r") out = out "\r"
        else if (c == "\\" || c == "\"" || c == "/") out = out c
        else if (c == "u") {
            hex = substr(s, i + 1, 4)
            out = out sprintf("%c", strtonum("0x" hex))
            i += 4
        } else out = out c
    }
    return out
}
function hs_json_parse_string(raw,    s) {
    s = substr(raw, 2, length(raw) - 2)
    return hs_json_unescape(s)
}
