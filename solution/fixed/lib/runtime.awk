function hs_rt_reset(svc) {
    delete hs_rt_env_keys
    delete hs_rt_env_vals
    hs_rt_env_count = 0
    hs_rt_service_id = svc
    hs_rt_root = ""
    hs_rt_root_ro = 0
    hs_rt_cwd = "/"
    hs_rt_user_uid = 0
    hs_rt_user_gid = 0
    hs_rt_uid_map_count = 0
    hs_rt_gid_map_count = 0
    delete hs_rt_mount_dest_idx
    delete hs_rt_mount_src_idx
    delete hs_rt_mount_type_idx
    hs_rt_mount_obj = 0
    hs_rt_mount_dest_cur = ""
    hs_rt_mount_src_cur = ""
    hs_rt_mount_type_cur = ""
}
function hs_rt_store_mount(    dest) {
    if (hs_rt_mount_dest_cur == "" || hs_rt_mount_type_cur == "") return
    dest = hs_path_normalize(hs_rt_mount_dest_cur)
    hs_rt_mount_dest_idx[dest] = 1
    hs_rt_mount_src_idx[dest] = hs_rt_mount_src_cur
    hs_rt_mount_type_idx[dest] = hs_rt_mount_type_cur
}
function hs_rt_load_bundle(bundle_dir, config_path,    line, in_env, key, val, eq, i, m, in_mounts, in_uid_maps, in_gid_maps, map_idx, mounts_depth) {
    hs_rt_reset("")
    in_mounts = 0
    in_uid_maps = 0
    in_gid_maps = 0
    map_idx = 0
    mounts_depth = 0
    while ((getline line < config_path) > 0) {
        if (match(line, /"io\.harborseal\.service\/id"[[:space:]]*:[[:space:]]*"([^"]+)"/, m)) hs_rt_service_id = m[1]
        if (match(line, /"path"[[:space:]]*:[[:space:]]*"([^"]+)"/, m) && line ~ /"root"/) hs_rt_root = m[1]
        if (line ~ /"readonly"[[:space:]]*:[[:space:]]*true/ && line ~ /"root"/) hs_rt_root_ro = 1
        if (match(line, /"cwd"[[:space:]]*:[[:space:]]*"([^"]+)"/, m)) hs_rt_cwd = m[1]
        if (match(line, /"uid"[[:space:]]*:[[:space:]]*([0-9]+)/, m)) hs_rt_user_uid = m[1] + 0
        if (match(line, /"gid"[[:space:]]*:[[:space:]]*([0-9]+)/, m)) hs_rt_user_gid = m[1] + 0
        if (line ~ /"uidMappings"[[:space:]]*:[[:space:]]*\[/) in_uid_maps = 1
        if (in_uid_maps && match(line, /"containerID"[[:space:]]*:[[:space:]]*([0-9]+)/, m)) {
            map_idx = ++hs_rt_uid_map_count
            hs_rt_uid_map_cid[map_idx] = m[1] + 0
        }
        if (in_uid_maps && match(line, /"hostID"[[:space:]]*:[[:space:]]*([0-9]+)/, m)) hs_rt_uid_map_hid[map_idx] = m[1] + 0
        if (in_uid_maps && match(line, /"size"[[:space:]]*:[[:space:]]*([0-9]+)/, m)) hs_rt_uid_map_size[map_idx] = m[1] + 0
        if (in_uid_maps && line ~ /\]/) in_uid_maps = 0
        if (line ~ /"gidMappings"[[:space:]]*:[[:space:]]*\[/) in_gid_maps = 1
        if (in_gid_maps && match(line, /"containerID"[[:space:]]*:[[:space:]]*([0-9]+)/, m)) {
            map_idx = ++hs_rt_gid_map_count
            hs_rt_gid_map_cid[map_idx] = m[1] + 0
        }
        if (in_gid_maps && match(line, /"hostID"[[:space:]]*:[[:space:]]*([0-9]+)/, m)) hs_rt_gid_map_hid[map_idx] = m[1] + 0
        if (in_gid_maps && match(line, /"size"[[:space:]]*:[[:space:]]*([0-9]+)/, m)) hs_rt_gid_map_size[map_idx] = m[1] + 0
        if (in_gid_maps && line ~ /\]/) in_gid_maps = 0
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
        if (line ~ /"mounts"[[:space:]]*:[[:space:]]*\[/) {
            in_mounts = 1
            mounts_depth = 1
        }
        if (in_mounts) {
            if (line ~ /\[/ && line !~ /"mounts"[[:space:]]*:[[:space:]]*\[/) mounts_depth++
            if (line ~ /\]/) {
                mounts_depth--
                if (mounts_depth == 0) {
                    if (hs_rt_mount_obj) {
                        hs_rt_store_mount()
                        hs_rt_mount_obj = 0
                    }
                    in_mounts = 0
                }
            }
        }
        if (in_mounts && line ~ /\{/) {
            hs_rt_mount_obj = 1
            hs_rt_mount_dest_cur = ""
            hs_rt_mount_src_cur = ""
            hs_rt_mount_type_cur = ""
        }
        if (in_mounts && hs_rt_mount_obj && match(line, /"destination"[[:space:]]*:[[:space:]]*"([^"]+)"/, m)) hs_rt_mount_dest_cur = m[1]
        if (in_mounts && hs_rt_mount_obj && match(line, /"source"[[:space:]]*:[[:space:]]*"([^"]+)"/, m)) hs_rt_mount_src_cur = m[1]
        if (in_mounts && hs_rt_mount_obj && match(line, /"type"[[:space:]]*:[[:space:]]*"([^"]+)"/, m)) hs_rt_mount_type_cur = m[1]
        if (in_mounts && hs_rt_mount_obj && line ~ /\}/) {
            hs_rt_store_mount()
            hs_rt_mount_obj = 0
        }
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
function hs_rt_cert_mounts_json(    dest, out, n) {
    out = "["
    n = 0
    for (dest in hs_rt_mount_dest_idx) {
        if (hs_rt_mount_type_idx[dest] != "bind") continue
        if (!hs_path_prefix_match("/etc/ssl/certs", dest)) continue
        if (hs_rt_mount_src_idx[dest] == "") continue
        if (n > 0) out = out ","
        n++
        out = out "{\"destination\": \"" dest "\", \"source\": \"" hs_rt_mount_src_idx[dest] "\"}"
    }
    out = out "]"
    return out
}
