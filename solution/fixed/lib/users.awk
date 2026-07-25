function hs_uid_map(container_id, mappings,    i, cid, hid, size, start, end) {
    for (i = 1; i <= mappings_count; i++) {
        cid = mappings_cid[i]
        hid = mappings_hid[i]
        size = mappings_size[i]
        start = cid
        end = cid + size - 1
        if (container_id >= start && container_id <= end) {
            return hid + (container_id - cid)
        }
    }
    return container_id
}
function hs_users_effective_uid(bundle_dir, config_path,    uid) {
    uid = hs_rt_user_uid
    if (hs_rt_uid_map_count > 0) {
        uid = hs_uid_map(uid, "uid")
    }
    return uid
}
