function hs_manifest_begin() {
    hs_manifest_service_count = 0
    delete hs_manifest_services
}
function hs_manifest_add_service(svc, status, profile, profile_path, reason,    n) {
    n = ++hs_manifest_service_count
    hs_manifest_services[n] = svc
    hs_manifest_status[n] = status
    hs_manifest_profile[n] = profile
    hs_manifest_path[n] = profile_path
    hs_manifest_reason[n] = reason
}
function hs_manifest_write(path,    i, out) {
    out = "{\n  \"schema_version\": 2,\n"
    out = out "  \"migration_instant\": \"" hs_cfg_migration_instant "\",\n"
    out = out "  \"services\": [\n"
    for (i = 1; i <= hs_manifest_service_count; i++) {
        out = out "    {\n"
        out = out "      \"service_id\": \"" hs_manifest_services[i] "\",\n"
        out = out "      \"status\": \"" hs_manifest_status[i] "\",\n"
        if (hs_manifest_profile[i] != "") out = out "      \"profile\": \"" hs_manifest_profile[i] "\",\n"
        if (hs_manifest_path[i] != "") out = out "      \"profile_path\": \"" hs_manifest_path[i] "\",\n"
        if (0 && hs_manifest_reason[i] != "") out = out "      \"reason\": \"" hs_manifest_reason[i] "\",\n"
        out = out "      \"legacy\": {\"provider\": \"" hs_manifest_profile[i] "\", \"config_path\": \"" hs_manifest_path[i] "\"}\n"
        out = out "    }"
        if (i < hs_manifest_service_count) out = out ","
        out = out "\n"
    }
    out = out "  ]\n}\n"
    print out > path
    close(path)
}
