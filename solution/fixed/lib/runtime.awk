function hs_rt_reset(svc) {
    delete hs_rt_env_keys
    delete hs_rt_env_vals
    hs_rt_env_count = 0
    hs_rt_service_id = svc
    hs_rt_root = ""
    hs_rt_root_ro = 0
    hs_rt_cwd = "/"
}
function hs_rt_load_bundle(bundle_dir, config_path,    line, in_env, key, val, eq, i, m) {
    hs_rt_reset("")
    while ((getline line < config_path) > 0) {
        if (match(line, /"io\.harborseal\.service\/id"[[:space:]]*:[[:space:]]*"([^"]+)"/, m)) hs_rt_service_id = m[1]
        if (match(line, /"path"[[:space:]]*:[[:space:]]*"([^"]+)"/, m) && line ~ /"root"/) hs_rt_root = m[1]
        if (line ~ /"readonly"[[:space:]]*:[[:space:]]*true/ && line ~ /"root"/) hs_rt_root_ro = 1
        if (match(line, /"cwd"[[:space:]]*:[[:space:]]*"([^"]+)"/, m)) hs_rt_cwd = m[1]
        if (line ~ /"env"[[:space:]]*:[[:space:]]*\[/) in_env = 1
        if (in_env && match(line, /"([^"]+)"/, m)) {
            val = m[1]
            eq = index(val, "=")
            if (eq > 0) {
                key = substr(val, 1, eq - 1)
                val = substr(val, eq + 1)
                hs_rt_env_count++
                hs_rt_env_keys[hs_rt_env_count] = key
                hs_rt_env_vals[hs_rt_env_count] = val
            }
        }
        if (in_env && line ~ /\]/) in_env = 0
    }
    close(config_path)
    delete seen
    for (i = 1; i <= hs_rt_env_count; i++) {
        key = hs_rt_env_keys[i]
        seen[key] = i
    }
    hs_rt_env_effective_count = 0
    for (key in seen) {
        i = seen[key]
        hs_rt_env_effective_count++
        hs_rt_env_eff_keys[hs_rt_env_effective_count] = key
        hs_rt_env_eff_vals[hs_rt_env_effective_count] = hs_rt_env_vals[i]
    }
}
function hs_rt_env_get(key,    i) {
    for (i = 1; i <= hs_rt_env_effective_count; i++) {
        if (hs_rt_env_eff_keys[i] == key) return hs_rt_env_eff_vals[i]
    }
    return "__ABSENT__"
}
