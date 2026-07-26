function hs_uid_map_value(container_id, kind,    i, cid, hid, size, count) {
    if (kind == "uid") count = hs_rt_uid_map_count
    else count = hs_rt_gid_map_count
    for (i = 1; i <= count; i++) {
        if (kind == "uid") {
            cid = hs_rt_uid_map_cid[i]
            hid = hs_rt_uid_map_hid[i]
            size = hs_rt_uid_map_size[i]
        } else {
            cid = hs_rt_gid_map_cid[i]
            hid = hs_rt_gid_map_hid[i]
            size = hs_rt_gid_map_size[i]
        }
        if (container_id >= cid && container_id < cid + size) {
            return hid + (container_id - cid)
        }
    }
    return container_id
}
function hs_users_effective_uid(bundle_dir, config_path) {
    return hs_uid_map_value(hs_rt_user_uid, "uid")
}
function hs_users_effective_gid(bundle_dir, config_path) {
    return hs_uid_map_value(hs_rt_user_gid, "gid")
}
