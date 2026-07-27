function hs_manifest_begin() {
    hs_manifest_service_count = 0
    delete hs_manifest_services
}
function hs_manifest_add_service(svc, status, profile, profile_path, reason, uid, gid, cert_mounts, report_sections, setup_actions,    n) {
    n = ++hs_manifest_service_count
    hs_manifest_services[n] = svc
    hs_manifest_status[n] = status
    hs_manifest_profile[n] = profile
    hs_manifest_path[n] = profile_path
    hs_manifest_reason[n] = reason
    hs_manifest_uid[n] = uid
    hs_manifest_gid[n] = gid
    hs_manifest_cert_mounts[n] = cert_mounts
    hs_manifest_report_sections[n] = report_sections
    hs_manifest_setup_actions[n] = setup_actions
}
function hs_manifest_sort_indices(    i, j, n, tmp) {
    n = hs_manifest_service_count
    for (i = 1; i <= n; i++) hs_manifest_order[i] = i
    for (i = 1; i <= n; i++) {
        for (j = i + 1; j <= n; j++) {
            if (hs_manifest_services[hs_manifest_order[i]] > hs_manifest_services[hs_manifest_order[j]]) {
                tmp = hs_manifest_order[i]
                hs_manifest_order[i] = hs_manifest_order[j]
                hs_manifest_order[j] = tmp
            }
        }
    }
}
function hs_manifest_write(path,    i, idx, out) {
    hs_manifest_sort_indices()
    out = "{\n  \"schema_version\": 2,\n"
    out = out "  \"migration_instant\": \"" hs_cfg_migration_instant "\",\n"
    out = out "  \"services\": [\n"
    for (i = 1; i <= hs_manifest_service_count; i++) {
        idx = hs_manifest_order[i]
        out = out "    {\n"
        out = out "      \"service_id\": \"" hs_manifest_services[idx] "\",\n"
        out = out "      \"status\": \"" hs_manifest_status[idx] "\",\n"
        if (hs_manifest_profile[idx] != "") out = out "      \"profile\": \"" hs_manifest_profile[idx] "\",\n"
        if (hs_manifest_path[idx] != "") out = out "      \"profile_path\": \"" hs_manifest_path[idx] "\",\n"
        if (hs_manifest_status[idx] == "ready") {
            out = out "      \"effective_uid\": " hs_manifest_uid[idx] ",\n"
            out = out "      \"effective_gid\": " hs_manifest_gid[idx] ",\n"
            out = out "      \"certificate_mounts\": " hs_manifest_cert_mounts[idx] ",\n"
            out = out "      \"report_sections\": " hs_manifest_report_sections[idx] ",\n"
            out = out "      \"setup_actions\": " hs_manifest_setup_actions[idx] ",\n"
        }
        if (hs_manifest_reason[idx] != "") out = out "      \"reason\": \"" hs_manifest_reason[idx] "\",\n"
        out = out "      \"legacy\": {\"provider\": \"" hs_manifest_profile[idx] "\", \"config_path\": \"" hs_manifest_path[idx] "\"}\n"
        out = out "    }"
        if (i < hs_manifest_service_count) out = out ","
        out = out "\n"
    }
    out = out "  ]\n}\n"
    print out > path
    close(path)
}
