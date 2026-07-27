function hs_canon_sort_ids(list, n,    i, j, tmp) {
    for (i = 2; i <= n; i++) {
        tmp = list[i]
        j = i - 1
        while (j >= 1 && list[j] > tmp) { list[j + 1] = list[j]; j-- }
        list[j + 1] = tmp
    }
}
function hs_json_escape(s,    out, i, c) {
    out = ""
    for (i = 1; i <= length(s); i++) {
        c = substr(s, i, 1)
        if (c == "\\") out = out "\\\\"
        else if (c == "\"") out = out "\\\""
        else if (c == "\n") out = out "\\n"
        else if (c == "\r") out = out "\\r"
        else if (c == "\t") out = out "\\t"
        else out = out c
    }
    return out
}
function hs_sanitize_id(s,    out, i, c) {
    out = ""
    for (i = 1; i <= length(s); i++) {
        c = substr(s, i, 1)
        if (c ~ /[A-Za-z0-9._-]/) out = out c
        else out = out "_"
    }
    return out
}
