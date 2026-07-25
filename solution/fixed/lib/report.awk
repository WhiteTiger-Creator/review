function hs_report_reset() {
    delete hs_report_events
    hs_report_event_count = 0
}
function hs_report_load_index(path,    line, block, in_event) {
    hs_report_reset()
    block = ""
    in_event = 0
    while ((getline line < path) > 0) {
        if (line ~ /"event_id"/) {
            if (in_event && block != "") {
                hs_report_event_count++
                hs_report_parse_event_block(hs_report_event_count, block)
            }
            block = line
            in_event = 1
            continue
        }
        if (in_event) {
            block = block "\n" line
            if (line ~ /\}/) {
                hs_report_event_count++
                hs_report_parse_event_block(hs_report_event_count, block)
                block = ""
                in_event = 0
            }
        }
    }
    close(path)
}
function hs_report_parse_event_block(idx, block,    m) {
    if (match(block, /"event_id"[[:space:]]*:[[:space:]]*"([^"]+)"/, m)) hs_re_id[idx] = m[1]
    if (match(block, /"service_scope"[[:space:]]*:[[:space:]]*"([^"]+)"/, m)) hs_re_scope[idx] = m[1]
    if (match(block, /"environment"[[:space:]]*:[[:space:]]*"([^"]+)"/, m)) hs_re_env[idx] = m[1]
    if (match(block, /"host_class"[[:space:]]*:[[:space:]]*"([^"]+)"/, m)) hs_re_host[idx] = m[1]
    if (match(block, /"decision_type"[[:space:]]*:[[:space:]]*"([^"]+)"/, m)) hs_re_type[idx] = m[1]
    if (match(block, /"profile"[[:space:]]*:[[:space:]]*"([^"]+)"/, m)) hs_re_profile[idx] = m[1]
    if (match(block, /"report_section"[[:space:]]*:[[:space:]]*"([^"]+)"/, m)) hs_re_section[idx] = m[1]
    if (match(block, /"effective_from"[[:space:]]*:[[:space:]]*"([^"]+)"/, m)) hs_re_from[idx] = m[1]
    if (match(block, /"effective_until"[[:space:]]*:[[:space:]]*null/)) hs_re_until[idx] = ""
    else if (match(block, /"effective_until"[[:space:]]*:[[:space:]]*"([^"]+)"/, m)) hs_re_until[idx] = m[1]
    if (match(block, /"inherit_to_descendants"[[:space:]]*:[[:space:]]*true/)) hs_re_inherit[idx] = 1
    else hs_re_inherit[idx] = 0
    if (match(block, /"supersedes"[[:space:]]*:[[:space:]]*\[\s*"([^"]+)"/, m)) hs_re_supersedes[idx] = m[1]
    else hs_re_supersedes[idx] = ""
}
function hs_report_scope_matches(scope, svc,    prefix) {
    if (scope == svc) return 1
    if (substr(scope, length(scope), 1) == "*") {
        prefix = substr(scope, 1, length(scope) - 1)
        if (prefix == "") return 0
        return index(svc, prefix) == 1 && (length(svc) == length(prefix) || substr(svc, length(prefix) + 1, 1) == "/")
    }
    return 0
}
function hs_report_is_superseded(idx,    i, target) {
    for (i = 1; i <= hs_report_event_count; i++) {
        if (hs_re_supersedes[i] == "") continue
        target = hs_re_supersedes[i]
        if (target == hs_re_id[idx]) return 1
    }
    return 0
}
function hs_report_event_applies(svc, idx) {
    if (hs_re_env[idx] != "" && hs_re_env[idx] != hs_cfg_environment) return 0
    if (hs_re_host[idx] != "" && hs_re_host[idx] != hs_cfg_host_class) return 0
    if (hs_re_type[idx] != "provider_profile") return 0
    if (!hs_report_scope_matches(hs_re_scope[idx], svc)) return 0
    if (hs_re_from[idx] > hs_cfg_migration_instant) return 0
    if (hs_re_until[idx] != "" && hs_re_until[idx] <= hs_cfg_migration_instant) return 0
    if (hs_report_is_superseded(idx)) return 0
    return 1
}
function hs_report_pick_winner(svc,    events, n, i, idx, best, best_specific, best_from, specific) {
    delete events
    delete hs_result_sections
    hs_result_profile = ""
    hs_result_reason = ""
    hs_result_nsections = 0
    n = 0
    for (i = 1; i <= hs_report_event_count; i++) {
        if (!hs_report_event_applies(svc, i)) continue
        n++
        events[n] = i
    }
    if (n == 0) { hs_result_reason = "no_profile_decision"; return 0 }
    best = 0
    best_specific = 0
    best_from = ""
    for (i = 1; i <= n; i++) {
        idx = events[i]
        specific = (hs_re_scope[idx] == svc) ? 2 : 1
        if (specific > best_specific || (specific == best_specific && hs_re_from[idx] > best_from)) {
            best = idx
            best_specific = specific
            best_from = hs_re_from[idx]
        }
    }
    if (best == 0) { hs_result_reason = "no_profile_decision"; return 0 }
    hs_result_profile = hs_re_profile[best]
    hs_result_sections[1] = hs_re_section[best]
    hs_result_nsections = 1
    return 1
}
