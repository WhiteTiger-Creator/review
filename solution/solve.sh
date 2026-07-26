#!/bin/bash
set -euo pipefail
umask 027

cd /app
for command in awk bash grep install jq python3 sha256sum sort tail tr wc; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "missing required runtime command: $command" >&2
    exit 127
  }
done
bash /app/scripts/initialize-service-state

work="$(mktemp -d /tmp/harbor-service-commissioning.XXXXXX)"
trap 'rm -rf "$work"' EXIT
catalog="$work/catalog.tsv"
change_catalog="$work/change-control.tsv"
/app/bin/catalog-query --batch-file /app/share/deployment-catalog.batch > "$catalog"
HARBOR_CATALOG_DB=/opt/harbor/change-control.db /app/bin/catalog-query --batch-file /app/share/change-control.batch > "$change_catalog"

table() {
  awk -v name="$1" '$0 == "@result " name {inside=1; next} inside && $0 == "@end" {exit} inside {print}' "$catalog"
}
ctable() {
  awk -v name="$1" '$0 == "@result " name {inside=1; next} inside && $0 == "@end" {exit} inside {print}' "$change_catalog"
}

# Select the authorized deployment identity from the sealed request set.
alias_name="$(awk -F': ' 'tolower($1)=="x-harbor-site-alias" {gsub("\r", "", $2); print $2; exit}' /app/fixtures/requests/status-replay.http)"
segment="$(awk -F': ' 'tolower($1)=="x-harbor-segment" {gsub("\r", "", $2); print $2; exit}' /app/fixtures/requests/status-replay.http)"
replay_mode="$(awk -F': ' 'tolower($1)=="x-replay-mode" {gsub("\r", "", $2); print $2; exit}' /app/fixtures/requests/status-replay.http)"
epoch="$(awk -F= '$1=="sealed_at" {print $2}' /app/evidence/capture.meta)"
handbook_revision="$(awk -F= '$1=="handbook_revision" {print $2}' /app/evidence/capture.meta)"
site_key="$(table site_alias | awk -F'\t' -v a="$alias_name" -v e="$epoch" 'NR>1 && $1==a && $6==0 && $3<=e && e<=$4 {if ($5+0>rank) {rank=$5+0; site=$2}} END{print site}')"
[ -n "$site_key" ]
ctx="$(table deployment_context | awk -F'\t' -v s="$site_key" 'NR>1 && $1==s && $2==1 {print; exit}')"
IFS=$'\t' read -r _ _ custody platform transport incident service_account service_group generation recovery_epoch root_class route_cohort policy_epoch <<<"$ctx"

# Select the deployable Unix socket from policy and sealed operating records.
selected_socket_id=""
selected_socket_path=""
selected_socket_mode=""
best_priority=-1
while IFS=$'\t' read -r candidate_id candidate_site path_template namespace purpose ownership mode token priority effective_from effective_to disabled; do
  [ "$candidate_id" = "candidate_id" ] && continue
  [ "$candidate_site" = "$site_key" ] || continue
  [ "$disabled" = "0" ] || continue
  [[ "$effective_from" > "$recovery_epoch" || "$effective_to" < "$recovery_epoch" ]] && continue
  allowed="$(table socket_policy | awk -F'\t' -v r="$root_class" -v t="$transport" -v n="$namespace" -v p="$purpose" -v o="$ownership" 'NR>1 && $1==r && $2==t && $3==n && $4==p && $5==o {print $6; exit}')"
  [ "$allowed" = "1" ] || continue
  path="${path_template//\{root\}//app}"
  last_line="$(grep -F "\"$path\"" /app/evidence/relay.strace | tail -n 1 || true)"
  [ -n "$last_line" ] || continue
  [[ "$last_line" == *"EACCES"* || "$last_line" == *"EADDRINUSE"* ]] && continue
  if awk '/^# snapshot=after/{after=1; next} after && index($0,p){found=1} END{exit !found}' p="$path" /app/evidence/relay.lsof; then
    continue
  fi
  if (( priority > best_priority )); then
    best_priority=$priority
    selected_socket_id="$candidate_id"
    selected_socket_path="$path"
    selected_socket_mode="$mode"
  fi
done < <(table socket_candidate)
[ -n "$selected_socket_id" ]

# Select the active route family under the published precedence rules.
family="$(table route_family_rule | awk -F'\t' -v c="$custody" -v p="$platform" -v t="$transport" -v i="$incident" -v s="$segment" -v r="$replay_mode" -v e="$recovery_epoch" '
  NR>1 && $14==0 && $12<=e && e<=$13 && $2==c && $3==p && $4==t && ($5==i || $5=="*") && $6==s && $7==r {
    if ($9+0>spec || ($9+0==spec && $10>source) || ($9+0==spec && $10==source && $11+0>rank)) {spec=$9+0; source=$10; rank=$11+0; family=$8; rule=$1}
  } END{print family "\t" rule}')"
IFS=$'\t' read -r family_code family_rule <<<"$family"
[ -n "$family_code" ]

# Assemble the active route cohort for service installation.
declare -A route_for key_epoch key_rank decision_code
while IFS=$'\t' read -r route_id route_site family_value cohort selection method path upstream auth_code timeout_code active effective_from effective_to source_epoch precedence; do
  [ "$route_id" = "route_id" ] && continue
  [ "$route_site" = "$site_key" ] && [ "$family_value" = "$family_code" ] && [ "$cohort" = "$route_cohort" ] || continue
  [ "$selection" = "base" ] && [ "$active" = "1" ] || continue
  [[ "$effective_from" > "$recovery_epoch" || "$effective_to" < "$recovery_epoch" ]] && continue
  key="$method $path"
  if [ -z "${route_for[$key]:-}" ] || [[ "$source_epoch" > "${key_epoch[$key]}" ]] || { [[ "$source_epoch" = "${key_epoch[$key]}" ]] && (( precedence > key_rank[$key] )); }; then
    route_for[$key]="$route_id"
    key_epoch[$key]="$source_epoch"
    key_rank[$key]="$precedence"
    decision_code[$route_id]="selected"
  fi
done < <(table route_candidate)

replacement_count=0
withdraw_count=0
require_count=0
while IFS=$'\t' read -r target replacement; do
  [ -n "$target" ] || continue
  for key in "${!route_for[@]}"; do
    if [ "${route_for[$key]}" = "$target" ]; then route_for[$key]="$replacement"; fi
  done
  unset "decision_code[$target]"
  decision_code[$replacement]="replaced"
  replacement_count=$((replacement_count+1))
done < <(table route_directive | awk -F'\t' -v s="$site_key" -v f="$family_code" -v e="$recovery_epoch" 'NR>1 && $2==s && $3==f && $4=="replace" && $11==0 && $9<=e && e<=$10 {print $5 "\t" $6}')
while IFS= read -r target; do
  [ -n "$target" ] || continue
  for key in "${!route_for[@]}"; do
    if [ "${route_for[$key]}" = "$target" ]; then unset "route_for[$key]"; fi
  done
  unset "decision_code[$target]"
  withdraw_count=$((withdraw_count+1))
done < <(table route_directive | awk -F'\t' -v s="$site_key" -v f="$family_code" -v e="$recovery_epoch" 'NR>1 && $2==s && $3==f && $4=="withdraw" && $11==0 && $9<=e && e<=$10 {print $5}')
while IFS= read -r target; do
  [ -n "$target" ] || continue
  row="$(table route_candidate | awk -F'\t' -v id="$target" 'NR>1 && $1==id {print; exit}')"
  IFS=$'\t' read -r _ _ _ _ _ method path _ _ _ _ _ _ _ _ _ <<<"$row"
  route_for["$method $path"]="$target"
  decision_code[$target]="required"
  require_count=$((require_count+1))
done < <(table route_directive | awk -F'\t' -v s="$site_key" -v f="$family_code" -v e="$recovery_epoch" 'NR>1 && $2==s && $3==f && $4=="require" && $11==0 && $9<=e && e<=$10 {print $5}')

# Complete the route dependency closure required by the service contract.
changed=1
while [ "$changed" = 1 ]; do
  changed=0
  for key in "${!route_for[@]}"; do
    rid="${route_for[$key]}"
    while IFS=$'\t' read -r owner required; do
      [ "$owner" = "route_id" ] && continue
      [ "$owner" = "$rid" ] || continue
      present=0
      for existing in "${route_for[@]}"; do [ "$existing" = "$required" ] && present=1; done
      if [ "$present" = 0 ]; then
        row="$(table route_candidate | awk -F'\t' -v id="$required" 'NR>1 && $1==id {print; exit}')"
        IFS=$'\t' read -r _ _ _ _ _ method path _ _ _ _ _ _ _ _ _ <<<"$row"
        route_for["$method $path"]="$required"
        decision_code[$required]="required"
        changed=1
      fi
    done < <(table route_dependency)
  done
done

routes_tmp="$work/routes.map"
printf 'method\texternal_path\tupstream\tauth_mode\ttimeout_ms\tsource_route_id\n' > "$routes_tmp"
routes_jsonl="$work/routes.jsonl"
: > "$routes_jsonl"
mapfile -t sorted_route_keys < <(printf '%s\n' "${!route_for[@]}" | sort)
for key in "${sorted_route_keys[@]}"; do
  rid="${route_for[$key]}"
  row="$(table route_candidate | awk -F'\t' -v id="$rid" 'NR>1 && $1==id {print; exit}')"
  IFS=$'\t' read -r _ _ _ cohort _ method path upstream auth_code timeout_code _ _ _ _ _ <<<"$row"
  auth_name="$(table auth_mode | awk -F'\t' -v code="$auth_code" 'NR>1 && $1==code {print $2; exit}')"
  timeout_ms="$(table timeout_band | awk -F'\t' -v code="$timeout_code" 'NR>1 && $1==code {print $2; exit}')"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$method" "$path" "$upstream" "$auth_name" "$timeout_ms" "$rid" >> "$routes_tmp"
  jq -cn --arg method "$method" --arg path "$path" --arg upstream "$upstream" --arg auth "$auth_name" --argjson timeout "$timeout_ms" --arg source "$rid" --arg cohort "$cohort" --arg decision "${decision_code[$rid]}" '{method:$method,external_path:$path,upstream:$upstream,auth_mode:$auth,timeout_ms:$timeout,source_route_id:$source,cohort_code:$cohort,decision_code:$decision}' >> "$routes_jsonl"
done
route_count="${#route_for[@]}"

# Calculate service capacity and request-envelope settings after route closure.
profile="$(table limit_candidate | awk -F'\t' -v s="$site_key" -v c="$custody" -v p="$platform" -v i="$incident" -v e="$recovery_epoch" 'NR>1 && $2==s && $3==c && $4==p && $5==i && $20==0 && $18<=e && e<=$19 {if ($17+0>rank){rank=$17+0; printrow=$0}} END{print printrow}')"
IFS=$'\t' read -r profile_id _ _ _ _ fd_soft reserve worker_cost route_cost listener_cost audit_cost backlog_floor backlog_cap min_tier headroom_num headroom_den _ _ _ _ <<<"$profile"
reserve_add=0
route_cost_add=0
body_add=0
for trigger in CUSTODY MULTI_REQUEST ROUTE_REPLACEMENT; do
  adj="$(table limit_adjustment | awk -F'\t' -v s="$site_key" -v t="$trigger" -v e="$recovery_epoch" 'NR>1 && $2==s && $3==t && $10==0 && $8<=e && e<=$9 {if ($7+0>rank){rank=$7+0; row=$0}} END{print row}')"
  [ -n "$adj" ] || continue
  IFS=$'\t' read -r _ _ _ add_reserve add_route add_body _ _ _ _ <<<"$adj"
  reserve_add=$((reserve_add+add_reserve))
  route_cost_add=$((route_cost_add+add_route))
  body_add=$((body_add+add_body))
done
reserved_files=$((reserve+reserve_add))
effective_route_cost=$((route_cost+route_cost_add))
numerator=$((fd_soft-reserved_files-listener_cost-audit_cost-route_count*effective_route_cost))
max_connections=$((numerator/worker_cost))
listen_backlog=1
while (( listen_backlog < max_connections )); do listen_backlog=$((listen_backlog*2)); done
(( listen_backlog < backlog_floor )) && listen_backlog=$backlog_floor
(( listen_backlog <= backlog_cap ))

max_body=0
while IFS=$'\t' read -r role request_path; do
  [[ "$role" = \#* || -z "$role" ]] && continue
  content_length="$(awk -F': ' 'tolower($1)=="content-length" {gsub("\r", "", $2); print $2; exit}' "$request_path")"
  content_length="${content_length:-0}"
  (( content_length > max_body )) && max_body=$content_length
done < /app/fixtures/requests/replay-set.manifest
needed=$(( ( (max_body+body_add)*headroom_num + headroom_den - 1 ) / headroom_den ))
min_ordinal="$(table body_tier | awk -F'\t' -v code="$min_tier" 'NR>1 && $1==code {print $3; exit}')"
body_selection="$(table body_tier | awk -F'\t' -v n="$needed" -v m="$min_ordinal" 'NR>1 && $3>=m && $2>=n {print $1 "\t" $2; exit}')"
IFS=$'\t' read -r selected_body_tier request_body_limit <<<"$body_selection"
[ -n "$request_body_limit" ]

# Reconcile the independent change-control authority plane.
authorization_source="$work/authorization-source.json"
python3 - "$change_catalog" "$epoch" "$alias_name" "$incident" "$family_code" "$selected_socket_id" "$selected_body_tier" > "$authorization_source" <<'PYAUTH'
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

path, sealed_at, alias_name, incident, family_code, socket_id, body_tier = sys.argv[1:]
blocks = {}
name = None
rows = []
for line in Path(path).read_text(encoding="utf-8").splitlines():
    if line.startswith("@result "):
        name = line.split(" ", 1)[1]
        rows = []
    elif line == "@end":
        header, *body = rows
        blocks[name] = [dict(zip(header.split("\t"), row.split("\t"), strict=True)) for row in body]
        name = None
    elif name is not None:
        rows.append(line)
meta = {row["key"]: row["value"] for row in blocks["change_meta"]}
eligible = [
    row for row in blocks["change_ticket"]
    if row["disabled"] == "0"
    and row["state"] == "APPROVED"
    and row["site_alias"] == alias_name
    and row["incident_code"] == incident
    and row["family_code"] == family_code
    and row["not_before"] <= sealed_at <= row["not_after"]
]
if not eligible:
    raise SystemExit("no eligible change ticket")
eligible.sort(key=lambda row: (row["source_epoch"], int(row["precedence_rank"]), row["ticket_id"]), reverse=True)
ticket = eligible[0]
if len(eligible) > 1 and eligible[1]["source_epoch"] == ticket["source_epoch"] and eligible[1]["precedence_rank"] == ticket["precedence_rank"]:
    raise SystemExit("ambiguous change ticket")
roles = {row["role_code"]: row for row in blocks["approval_role"]}
latest = {}
for event in blocks["approval_event"]:
    if event["ticket_id"] != ticket["ticket_id"] or event["event_epoch"] > sealed_at:
        continue
    key = (event["approver_id"], event["role_code"])
    current = latest.get(key)
    if current is None or (event["event_epoch"], int(event["precedence_rank"]), event["event_id"]) > (current["event_epoch"], int(current["precedence_rank"]), current["event_id"]):
        latest[key] = event
approved = []
for event in latest.values():
    if event["event_kind"] not in {"approve", "reinstate"}:
        continue
    role = roles[event["role_code"]]
    approved.append({
        "exclusive_group": role["exclusive_group"],
        "approver_id": event["approver_id"],
        "role_code": event["role_code"],
        "weight": int(role["quorum_weight"]),
        "state": event["event_kind"],
        "event_id": event["event_id"],
        "event_epoch": event["event_epoch"],
    })
by_group = defaultdict(list)
for record in approved:
    by_group[record["exclusive_group"]].append(record)
selected = []
rejected = []
for group, records in by_group.items():
    records.sort(key=lambda row: (-row["weight"], row["approver_id"]))
    best_weight = records[0]["weight"]
    best = max((row for row in records if row["weight"] == best_weight), key=lambda row: (row["event_epoch"], tuple(-ord(c) for c in row["approver_id"])))
    selected.append(best)
    rejected.extend(row for row in records if row is not best)
selected.sort(key=lambda row: (row["exclusive_group"], row["approver_id"]))
quorum = sum(row["weight"] for row in selected)
required = int(ticket["quorum_required"])
if quorum < required or len(selected) < 2:
    raise SystemExit("approval quorum not met")
activations = [
    row for row in blocks["activation_candidate"]
    if row["disabled"] == "0"
    and row["ticket_id"] == ticket["ticket_id"]
    and row["socket_candidate_id"] == socket_id
    and row["body_tier_code"] == body_tier
    and row["effective_from"] <= sealed_at <= row["effective_to"]
]
if not activations:
    raise SystemExit("no eligible activation candidate")
activations.sort(key=lambda row: (row["source_epoch"], int(row["precedence_rank"]), row["activation_id"]), reverse=True)
activation = activations[0]
if len(activations) > 1 and activations[1]["source_epoch"] == activation["source_epoch"] and activations[1]["precedence_rank"] == activation["precedence_rank"]:
    raise SystemExit("ambiguous activation candidate")
for row in selected:
    row.pop("event_epoch")
for row in rejected:
    row.pop("event_epoch")
json.dump({
    "change_generation": int(meta["change_generation"]),
    "ticket_id": ticket["ticket_id"],
    "quorum_required": required,
    "quorum_observed": quorum,
    "activation_id": activation["activation_id"],
    "release_lane": activation["release_lane"],
    "approvals": selected,
    "rejected_same_group": rejected,
}, sys.stdout, separators=(",", ":"))
PYAUTH
change_generation="$(jq -r .change_generation "$authorization_source")"
ticket_id="$(jq -r .ticket_id "$authorization_source")"
quorum_required="$(jq -r .quorum_required "$authorization_source")"
quorum_observed="$(jq -r .quorum_observed "$authorization_source")"
activation_id="$(jq -r .activation_id "$authorization_source")"
release_lane="$(jq -r .release_lane "$authorization_source")"
authorization_digest="$(jq -r '.approvals[] | [.exclusive_group,.approver_id,.role_code,(.weight|tostring),.state,.event_id] | join("|")' "$authorization_source" | sha256sum | awk '{print $1}')"

relay_tmp="$work/relay.conf"
limits_tmp="$work/limits.conf"
cat > "$relay_tmp" <<EOF
site_key=$site_key
socket_path=$selected_socket_path
socket_mode=$selected_socket_mode
socket_owner=$service_account
socket_group=$service_group
listen_backlog=$listen_backlog
route_map=/app/etc/harbor-relay/routes.map
limits_file=/app/etc/harbor-relay/limits.conf
audit_db=/app/var/deployment-audit.db
catalog_generation=$generation
EOF
cat > "$limits_tmp" <<EOF
open_files_soft=$fd_soft
reserved_files=$reserved_files
max_connections=$max_connections
request_body_limit=$request_body_limit
EOF
install -m 0640 "$relay_tmp" /app/etc/harbor-relay/relay.conf
install -m 0640 "$limits_tmp" /app/etc/harbor-relay/limits.conf
install -m 0640 "$routes_tmp" /app/etc/harbor-relay/routes.map

relay_sha="$(sha256sum /app/etc/harbor-relay/relay.conf | awk '{print $1}')"
limits_sha="$(sha256sum /app/etc/harbor-relay/limits.conf | awk '{print $1}')"
routes_sha="$(sha256sum /app/etc/harbor-relay/routes.map | awk '{print $1}')"
catalog_sha="$(sha256sum "$catalog" | awk '{print $1}')"
catalog_bytes="$(wc -c < "$catalog" | tr -d ' ')"
change_sha="$(sha256sum "$change_catalog" | awk '{print $1}')"
change_bytes="$(wc -c < "$change_catalog" | tr -d ' ')"
request_hashes=()
request_hashes+=("$(sha256sum /app/fixtures/requests/replay-set.manifest | awk '{print $1}')")
while IFS=$'\t' read -r role request_path; do
  [[ "$role" = \#* || -z "$role" ]] && continue
  request_hashes+=("$(sha256sum "$request_path" | awk '{print $1}')")
done < /app/fixtures/requests/replay-set.manifest
request_set_sha="$(printf '%s\n' "${request_hashes[@]}" | sha256sum | awk '{print $1}')"
evidence_set_sha="$(for path in /app/evidence/capture.meta /app/evidence/relay.strace /app/evidence/relay.lsof; do sha256sum "$path" | awk '{print $1}'; done | sha256sum | awk '{print $1}')"
run_id="$(printf '%s' "$site_key|$handbook_revision|$generation|$change_generation|$request_set_sha|$evidence_set_sha|$catalog_sha|$change_sha|$authorization_digest|$relay_sha|$limits_sha|$routes_sha" | sha256sum | cut -c1-24)"
activation_token="$(printf '%s' "$ticket_id|$activation_id|$authorization_digest|$run_id" | sha256sum | cut -c1-24)"
approvals_json="$(jq -c .approvals "$authorization_source")"
authorization_json="$(jq -cn --arg ticket "$ticket_id" --argjson generation "$change_generation" --arg activation "$activation_id" --arg lane "$release_lane" --argjson required "$quorum_required" --argjson observed "$quorum_observed" --argjson approvals "$approvals_json" --arg digest "$authorization_digest" --arg token "$activation_token" '{ticket_id:$ticket,change_generation:$generation,activation_id:$activation,release_lane:$lane,quorum_required:$required,quorum_observed:$observed,approvals:$approvals,authorization_digest:$digest,activation_token:$token}')"
printf '%s\n' "$authorization_json" > /app/var/activation-seal.json
chmod 0640 /app/var/activation-seal.json
activation_sha="$(sha256sum /app/var/activation-seal.json | awk '{print $1}')"
activation_bytes="$(wc -c < /app/var/activation-seal.json | tr -d ' ')"

assertions_jsonl="$work/assertions.jsonl"
cat > "$assertions_jsonl" <<EOF
{"name":"catalog-generation","passed":1,"observed":"$generation","rule_ref":"CAT-2.7"}
{"name":"identity-alias","passed":1,"observed":"$alias_name->$site_key","rule_ref":"ID-4.9"}
{"name":"socket-last-evidence","passed":1,"observed":"$selected_socket_id:ENOENT","rule_ref":"SOCK-8.12"}
{"name":"route-family","passed":1,"observed":"$family_code","rule_ref":"ROUTE-11.6"}
{"name":"directive-closure","passed":1,"observed":"replace=$replacement_count,withdraw=$withdraw_count,require=$require_count","rule_ref":"ROUTE-13.8"}
{"name":"dependency-closure","passed":1,"observed":"$route_count routes","rule_ref":"ROUTE-14.4"}
{"name":"fd-budget","passed":1,"observed":"$max_connections","rule_ref":"LIM-17.5"}
{"name":"body-envelope","passed":1,"observed":"$request_body_limit","rule_ref":"LIM-19.3"}
{"name":"publication-digests","passed":1,"observed":"$run_id","rule_ref":"PUB-23.7"}
{"name":"relay-validation","passed":1,"observed":"ok","rule_ref":"PUB-24.2"}
{"name":"change-generation","passed":1,"observed":"$change_generation","rule_ref":"CC-1.3"}
{"name":"ticket-selection","passed":1,"observed":"$ticket_id","rule_ref":"CC-3.8"}
{"name":"approval-state","passed":1,"observed":"2 effective","rule_ref":"CC-5.4"}
{"name":"approval-quorum","passed":1,"observed":"$quorum_observed/$quorum_required","rule_ref":"CC-6.9"}
{"name":"activation-selection","passed":1,"observed":"$activation_id","rule_ref":"CC-8.2"}
EOF

inputs_jsonl="$work/inputs.jsonl"
: > "$inputs_jsonl"
add_input() {
  local kind="$1" path="$2" digest bytes
  digest="$(sha256sum "$path" | awk '{print $1}')"
  bytes="$(wc -c < "$path" | tr -d ' ')"
  jq -cn --arg kind "$kind" --arg path "$path" --arg sha "$digest" --argjson bytes "$bytes" '{kind:$kind,path:$path,sha256:$sha,bytes:$bytes}' >> "$inputs_jsonl"
}
add_input capture-meta /app/evidence/capture.meta
jq -cn --arg kind catalog-batch-result --arg path /app/share/deployment-catalog.batch --arg sha "$catalog_sha" --argjson bytes "$catalog_bytes" '{kind:$kind,path:$path,sha256:$sha,bytes:$bytes}' >> "$inputs_jsonl"
jq -cn --arg kind change-catalog-batch-result --arg path /app/share/change-control.batch --arg sha "$change_sha" --argjson bytes "$change_bytes" '{kind:$kind,path:$path,sha256:$sha,bytes:$bytes}' >> "$inputs_jsonl"
add_input lsof /app/evidence/relay.lsof
add_input request-manifest /app/fixtures/requests/replay-set.manifest
while IFS=$'\t' read -r role request_path; do
  [[ "$role" = \#* || -z "$role" ]] && continue
  add_input "request:$role" "$request_path"
done < /app/fixtures/requests/replay-set.manifest
add_input strace /app/evidence/relay.strace
sort -t'"' -k4,4 -k8,8 "$inputs_jsonl" -o "$inputs_jsonl"

relay_bytes="$(wc -c < /app/etc/harbor-relay/relay.conf | tr -d ' ')"
limits_bytes="$(wc -c < /app/etc/harbor-relay/limits.conf | tr -d ' ')"
routes_bytes="$(wc -c < /app/etc/harbor-relay/routes.map | tr -d ' ')"
zero="$(printf '0%.0s' {1..64})"

# Create the deterministic service-deployment audit database with SQL.
audit_sql="$work/audit.sql"
cat > "$audit_sql" <<EOF
PRAGMA journal_mode=OFF;
PRAGMA synchronous=OFF;
PRAGMA page_size=4096;
BEGIN;
CREATE TABLE deployment_run(run_id TEXT PRIMARY KEY,site_key TEXT NOT NULL,handbook_revision TEXT NOT NULL,catalog_generation INTEGER NOT NULL CHECK(catalog_generation>0),change_generation INTEGER NOT NULL CHECK(change_generation>0),request_set_sha256 TEXT NOT NULL CHECK(length(request_set_sha256)=64),evidence_set_sha256 TEXT NOT NULL CHECK(length(evidence_set_sha256)=64),catalog_snapshot_sha256 TEXT NOT NULL CHECK(length(catalog_snapshot_sha256)=64),change_snapshot_sha256 TEXT NOT NULL CHECK(length(change_snapshot_sha256)=64),authorization_digest TEXT NOT NULL CHECK(length(authorization_digest)=64),status TEXT NOT NULL CHECK(status='commissioned'));
CREATE TABLE input_artifact(kind TEXT NOT NULL,path TEXT NOT NULL,sha256 TEXT NOT NULL CHECK(length(sha256)=64),bytes INTEGER NOT NULL CHECK(bytes>=0),PRIMARY KEY(kind,path));
CREATE TABLE configuration(key TEXT PRIMARY KEY,value TEXT NOT NULL,source_code TEXT NOT NULL CHECK(source_code IN ('CTX','ALIAS','SOCK','LIMIT','ROUTE','META','PATH')));
CREATE TABLE route(method TEXT NOT NULL,external_path TEXT NOT NULL,upstream TEXT NOT NULL,auth_mode TEXT NOT NULL,timeout_ms INTEGER NOT NULL CHECK(timeout_ms>0),source_route_id TEXT NOT NULL,cohort_code TEXT NOT NULL,decision_code TEXT NOT NULL CHECK(decision_code IN ('selected','replaced','required')),PRIMARY KEY(method,external_path));
CREATE TABLE decision(sequence INTEGER PRIMARY KEY CHECK(sequence>0),domain TEXT NOT NULL,subject TEXT NOT NULL,outcome TEXT NOT NULL CHECK(outcome IN ('selected','rejected','replaced','withdrawn','required','calculated','validated')),rule_ref TEXT NOT NULL,evidence TEXT NOT NULL);
CREATE TABLE assertion(name TEXT PRIMARY KEY,passed INTEGER NOT NULL CHECK(passed IN (0,1)),observed TEXT NOT NULL,rule_ref TEXT NOT NULL);
CREATE TABLE authorization(ticket_id TEXT PRIMARY KEY,change_generation INTEGER NOT NULL CHECK(change_generation>0),activation_id TEXT NOT NULL,release_lane TEXT NOT NULL,quorum_required INTEGER NOT NULL CHECK(quorum_required>0),quorum_observed INTEGER NOT NULL CHECK(quorum_observed>=quorum_required),authorization_digest TEXT NOT NULL CHECK(length(authorization_digest)=64),activation_token TEXT NOT NULL CHECK(length(activation_token)=24));
CREATE TABLE approval(exclusive_group TEXT NOT NULL,approver_id TEXT NOT NULL,role_code TEXT NOT NULL,weight INTEGER NOT NULL CHECK(weight>0),state TEXT NOT NULL CHECK(state IN ('approve','reinstate')),event_id TEXT NOT NULL,PRIMARY KEY(exclusive_group,approver_id,role_code));
CREATE TABLE publication_file(path TEXT PRIMARY KEY,sha256 TEXT NOT NULL CHECK(length(sha256)=64),bytes INTEGER NOT NULL CHECK(bytes>=0),mode_text TEXT NOT NULL CHECK(mode_text IN ('0640','0600')));
INSERT INTO deployment_run VALUES('$run_id','$site_key','$handbook_revision',$generation,$change_generation,'$request_set_sha','$evidence_set_sha','$catalog_sha','$change_sha','$authorization_digest','commissioned');
EOF
while IFS= read -r row; do
  kind="$(jq -r .kind <<<"$row")"; path="$(jq -r .path <<<"$row")"; sha="$(jq -r .sha256 <<<"$row")"; bytes="$(jq -r .bytes <<<"$row")"
  printf "INSERT INTO input_artifact VALUES('%s','%s','%s',%s);\n" "$kind" "$path" "$sha" "$bytes" >> "$audit_sql"
done < "$inputs_jsonl"
cat >> "$audit_sql" <<EOF
INSERT INTO configuration VALUES('site_key','$site_key','ALIAS');
INSERT INTO configuration VALUES('socket_path','$selected_socket_path','SOCK');
INSERT INTO configuration VALUES('socket_mode','$selected_socket_mode','SOCK');
INSERT INTO configuration VALUES('socket_owner','$service_account','CTX');
INSERT INTO configuration VALUES('socket_group','$service_group','CTX');
INSERT INTO configuration VALUES('listen_backlog','$listen_backlog','LIMIT');
INSERT INTO configuration VALUES('route_map','/app/etc/harbor-relay/routes.map','PATH');
INSERT INTO configuration VALUES('limits_file','/app/etc/harbor-relay/limits.conf','PATH');
INSERT INTO configuration VALUES('audit_db','/app/var/deployment-audit.db','PATH');
INSERT INTO configuration VALUES('catalog_generation','$generation','META');
INSERT INTO configuration VALUES('open_files_soft','$fd_soft','LIMIT');
INSERT INTO configuration VALUES('reserved_files','$reserved_files','LIMIT');
INSERT INTO configuration VALUES('max_connections','$max_connections','LIMIT');
INSERT INTO configuration VALUES('request_body_limit','$request_body_limit','LIMIT');
EOF
while IFS= read -r row; do
  method="$(jq -r .method <<<"$row")"; path="$(jq -r .external_path <<<"$row")"; upstream="$(jq -r .upstream <<<"$row")"; auth="$(jq -r .auth_mode <<<"$row")"; timeout="$(jq -r .timeout_ms <<<"$row")"; source="$(jq -r .source_route_id <<<"$row")"; cohort="$(jq -r .cohort_code <<<"$row")"; decision="$(jq -r .decision_code <<<"$row")"
  printf "INSERT INTO route VALUES('%s','%s','%s','%s',%s,'%s','%s','%s');\n" "$method" "$path" "$upstream" "$auth" "$timeout" "$source" "$cohort" "$decision" >> "$audit_sql"
done < "$routes_jsonl"
cat >> "$audit_sql" <<EOF
INSERT INTO decision VALUES(1,'identity','$alias_name','selected','ID-4.9','$alias_name->$site_key');
INSERT INTO decision VALUES(2,'socket','sock-control','rejected','SOCK-8.12','policy');
INSERT INTO decision VALUES(3,'socket','sock-data','rejected','SOCK-8.12','last=EACCES');
INSERT INTO decision VALUES(4,'socket','sock-legacy','rejected','SOCK-8.12','policy');
INSERT INTO decision VALUES(5,'socket','sock-metrics','rejected','SOCK-8.12','policy');
INSERT INTO decision VALUES(6,'socket','sock-tcp','rejected','SOCK-8.12','occupied');
INSERT INTO decision VALUES(7,'socket','$selected_socket_id','selected','SOCK-8.12','$selected_socket_path:ENOENT');
INSERT INTO decision VALUES(8,'route-family','$family_rule','selected','ROUTE-11.6','$family_code');
INSERT INTO decision VALUES(9,'route-directive','dir-capability-require','required','ROUTE-13.8','rt-203');
INSERT INTO decision VALUES(10,'route-directive','dir-manifest-replace','replaced','ROUTE-13.8','rt-202->rt-204');
INSERT INTO decision VALUES(11,'route-directive','dir-policy-withdraw','withdrawn','ROUTE-13.8','rt-205');
INSERT INTO decision VALUES(12,'route-closure','$family_code','validated','ROUTE-14.4','$route_count routes');
INSERT INTO decision VALUES(13,'limits','$profile_id','calculated','LIM-17.5','connections=$max_connections');
INSERT INTO decision VALUES(14,'limits','body-envelope','calculated','LIM-19.3','needed=$needed,tier=$request_body_limit');
INSERT INTO decision VALUES(15,'change-control','$ticket_id','selected','CC-3.8','$alias_name|$incident|$family_code');
INSERT INTO decision VALUES(16,'change-control','alice.ops','selected','CC-5.4','OPS|approve|ev-a1');
INSERT INTO decision VALUES(17,'change-control','bob.sec','selected','CC-5.4','SECURITY|reinstate|ev-b3');
INSERT INTO decision VALUES(18,'change-control','carol.sre','rejected','CC-6.9','lower-weight-same-group');
INSERT INTO decision VALUES(19,'change-control','$ticket_id','calculated','CC-6.9','quorum=$quorum_observed/$quorum_required');
INSERT INTO decision VALUES(20,'change-control','$activation_id','selected','CC-8.2','$selected_socket_id|$selected_body_tier|$release_lane');
INSERT INTO authorization VALUES('$ticket_id',$change_generation,'$activation_id','$release_lane',$quorum_required,$quorum_observed,'$authorization_digest','$activation_token');
EOF
while IFS= read -r row; do
  group="$(jq -r .exclusive_group <<<"$row")"; approver="$(jq -r .approver_id <<<"$row")"; role="$(jq -r .role_code <<<"$row")"; weight="$(jq -r .weight <<<"$row")"; state="$(jq -r .state <<<"$row")"; event_id="$(jq -r .event_id <<<"$row")"
  printf "INSERT INTO approval VALUES('%s','%s','%s',%s,'%s','%s');\n" "$group" "$approver" "$role" "$weight" "$state" "$event_id" >> "$audit_sql"
done < <(jq -c '.approvals[]' "$authorization_source")
while IFS= read -r row; do
  name="$(jq -r .name <<<"$row")"; passed="$(jq -r .passed <<<"$row")"; observed="$(jq -r .observed <<<"$row")"; rule="$(jq -r .rule_ref <<<"$row")"
  printf "INSERT INTO assertion VALUES('%s',%s,'%s','%s');\n" "$name" "$passed" "$observed" "$rule" >> "$audit_sql"
done < "$assertions_jsonl"
cat >> "$audit_sql" <<EOF
INSERT INTO publication_file VALUES('/app/etc/harbor-relay/relay.conf','$relay_sha',$relay_bytes,'0640');
INSERT INTO publication_file VALUES('/app/etc/harbor-relay/limits.conf','$limits_sha',$limits_bytes,'0640');
INSERT INTO publication_file VALUES('/app/etc/harbor-relay/routes.map','$routes_sha',$routes_bytes,'0640');
INSERT INTO publication_file VALUES('/app/var/activation-seal.json','$activation_sha',$activation_bytes,'0640');
INSERT INTO publication_file VALUES('/app/var/deployment-audit.db','$zero',0,'0600');
INSERT INTO publication_file VALUES('/app/var/deployment-manifest.json','$zero',0,'0640');
COMMIT;
VACUUM;
EOF
audit_stage="$work/deployment-audit.db"
rm -f "$audit_stage" /app/var/deployment-audit.db
python3 - "$audit_stage" "$audit_sql" <<'PYSQLITE'
import sqlite3
import sys
from pathlib import Path

database = Path(sys.argv[1])
script = Path(sys.argv[2]).read_text(encoding="utf-8")
connection = sqlite3.connect(database)
try:
    connection.executescript(script)
    connection.commit()
finally:
    connection.close()
PYSQLITE
install -m 0600 "$audit_stage" /app/var/deployment-audit.db

configuration_json="$(jq -cn --arg site "$site_key" --arg socket "$selected_socket_path" --arg mode "$selected_socket_mode" --arg owner "$service_account" --arg group "$service_group" --arg backlog "$listen_backlog" --arg generation "$generation" --arg fd "$fd_soft" --arg reserve "$reserved_files" --arg connections "$max_connections" --arg body "$request_body_limit" '{site_key:$site,socket_path:$socket,socket_mode:$mode,socket_owner:$owner,socket_group:$group,listen_backlog:$backlog,route_map:"/app/etc/harbor-relay/routes.map",limits_file:"/app/etc/harbor-relay/limits.conf",audit_db:"/app/var/deployment-audit.db",catalog_generation:$generation,open_files_soft:$fd,reserved_files:$reserve,max_connections:$connections,request_body_limit:$body}')"
routes_json="$(jq -cs '.' "$routes_jsonl")"
assertions_json="$(jq -cs '.' "$assertions_jsonl")"
inputs_json="$(jq -cs '.' "$inputs_jsonl")"
publication_json="$(jq -cn --arg rsha "$relay_sha" --argjson rbytes "$relay_bytes" --arg lsha "$limits_sha" --argjson lbytes "$limits_bytes" --arg msha "$routes_sha" --argjson mbytes "$routes_bytes" --arg asha "$activation_sha" --argjson abytes "$activation_bytes" --arg zero "$zero" '[{path:"/app/etc/harbor-relay/relay.conf",sha256:$rsha,bytes:$rbytes,mode:"0640"},{path:"/app/etc/harbor-relay/limits.conf",sha256:$lsha,bytes:$lbytes,mode:"0640"},{path:"/app/etc/harbor-relay/routes.map",sha256:$msha,bytes:$mbytes,mode:"0640"},{path:"/app/var/activation-seal.json",sha256:$asha,bytes:$abytes,mode:"0640"},{path:"/app/var/deployment-audit.db",sha256:$zero,bytes:0,mode:"0600"},{path:"/app/var/deployment-manifest.json",sha256:$zero,bytes:0,mode:"0640"}]')"
jq -cn --arg run "$run_id" --arg site "$site_key" --arg revision "$handbook_revision" --argjson generation "$generation" --argjson change_generation "$change_generation" --argjson configuration "$configuration_json" --argjson routes "$routes_json" --argjson assertions "$assertions_json" --argjson authorization "$authorization_json" --argjson inputs "$inputs_json" --argjson publication "$publication_json" '{run_id:$run,site_key:$site,handbook_revision:$revision,catalog_generation:$generation,change_generation:$change_generation,configuration:$configuration,routes:$routes,assertions:$assertions,authorization:$authorization,inputs:$inputs,publication:$publication}' > /app/var/deployment-manifest.json
chmod 0640 /app/var/deployment-manifest.json
: > /app/var/harbor-deployment.lock
chmod 0600 /app/var/harbor-deployment.lock

/app/bin/harbor-relay --check-config /app/etc/harbor-relay/relay.conf
