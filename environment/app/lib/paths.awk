function hs_path_normalize(p,    parts, n, i, seg, out) {
    n = split(p, parts, "/")
    delete stack
    sn = 0
    for (i = 1; i <= n; i++) {
        seg = parts[i]
        if (seg == "" || seg == ".") continue
        if (seg == "..") { if (sn > 0) sn--; continue }
        sn++
        stack[sn] = seg
    }
    if (sn == 0) return "/"
    out = ""
    for (i = 1; i <= sn; i++) out = out "/" stack[i]
    return out
}
function hs_path_prefix_match(base, path,    bl, pl) {
    base = hs_path_normalize(base)
    path = hs_path_normalize(path)
    if (base == "/") return 1
    bl = length(base)
    pl = length(path)
    if (pl < bl) return 0
    if (substr(path, 1, bl) != base) return 0
    if (pl == bl) return 1
    return substr(path, bl + 1, 1) == "/"
}
function hs_path_join(a, b) {
    if (b ~ /^\//) return hs_path_normalize(b)
    return hs_path_normalize(a "/" b)
}
