# harborseal public orchestration
function hs_reset() {
    hs_cfg_environment = "staging"
    hs_cfg_host_class = "harborseal"
    hs_cfg_migration_instant = "2026-04-01T00:00:00Z"
    hs_report_reset()
    hs_manifest_begin()
    hs_state_status = "DISCOVERING"
}
function hs_load_report_index(path) { hs_report_load_index(path) }
function hs_configure(ctx, key, value) {
    if (key == "environment") hs_cfg_environment = value
    else if (key == "host_class") hs_cfg_host_class = value
    else if (key == "migration_instant") hs_cfg_migration_instant = value
}
function hs_resolve_service(bundle_dir, config_path, output_dir,    svc, out_file, ok) {
    hs_rt_load_bundle(bundle_dir, config_path)
    svc = hs_rt_service_id
    if (svc == "") svc = "unknown"
    ok = hs_report_pick_winner(svc)
    if (!ok) {
        hs_manifest_add_service(svc, "error", "", "", hs_result_reason)
        return 0
    }
    out_file = output_dir "/" hs_sanitize_id(svc) ".cnf"
    hs_profile_emit(svc, hs_result_profile, out_file)
    if (!hs_profile_validate(out_file, hs_result_profile)) {
        hs_manifest_add_service(svc, "error", hs_result_profile, "", "provider_validation_failed")
        return 0
    }
    hs_manifest_add_service(svc, "ready", hs_result_profile, "profiles/" hs_sanitize_id(svc) ".cnf", "")
    return 1
}
function hs_emit_manifest(path) { hs_manifest_write(path) }
function hs_save_state(path) { hs_state_save(path) }
function hs_error_count() { return 0 }
