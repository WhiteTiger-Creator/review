function hs_profile_emit(svc, profile, out_path,    body) {
    body = "openssl_conf = hs_init\n\n[hs_init]\nproviders = hs_providers\n"
    if (profile == "fips") {
        body = body "\n[hs_providers]\ndefault = hs_default\nbase = hs_base\nfips = hs_fips\n\n"
        body = body "[hs_default]\nactivate = 1\n\n[hs_base]\nactivate = 1\n\n[hs_fips]\nactivate = 1\nmodule = ${OPENSSL_MODULES}/hs-fips.so\n\n"
        body = body "[hs_algorithms]\ndefault_properties = fips=yes\n"
    } else if (profile == "legacy" || profile == "legacy_verify_only") {
        body = body "\n[hs_providers]\ndefault = hs_default\nlegacy = hs_legacy\n\n"
        body = body "[hs_default]\nactivate = 1\n\n[hs_legacy]\nactivate = 1\nmodule = ${OPENSSL_MODULES}/legacy.so\n"
        if (profile == "legacy_verify_only") {
            body = body "\n# verification-only legacy restrictions\n"
        }
    } else {
        body = body "\n[hs_providers]\ndefault = hs_default\n\n[hs_default]\nactivate = 1\n"
    }
    print body > out_path
    close(out_path)
}
function hs_profile_validate(path, profile,    f) {
    if ((getline f < path) <= 0) return 0
    close(path)
    if (profile == "fips" && f !~ /fips=yes/) return 0
    return 1
}
