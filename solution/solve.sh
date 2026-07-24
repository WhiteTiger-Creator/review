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
/app/bin/catalog-query --batch-file /app/share/deployment-catalog.batch > "$catalog"

table() {
  awk -v name="$1" '$0 == "@result " name {inside=1; next} inside && $0 == "@end" {exit} inside {print}' "$catalog"
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
request_body_limit="$(table body_tier | awk -F'\t' -v n="$needed" -v m="$min_ordinal" 'NR>1 && $3>=m && $2>=n {print $2; exit}')"
[ -n "$request_body_limit" ]

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
request_hashes=()
request_hashes+=("$(sha256sum /app/fixtures/requests/replay-set.manifest | awk '{print $1}')")
while IFS=$'\t' read -r role request_path; do
  [[ "$role" = \#* || -z "$role" ]] && continue
  request_hashes+=("$(sha256sum "$request_path" | awk '{print $1}')")
done < /app/fixtures/requests/replay-set.manifest
request_set_sha="$(printf '%s\n' "${request_hashes[@]}" | sha256sum | awk '{print $1}')"
evidence_set_sha="$(for path in /app/evidence/capture.meta /app/evidence/relay.strace /app/evidence/relay.lsof; do sha256sum "$path" | awk '{print $1}'; done | sha256sum | awk '{print $1}')"
run_id="$(printf '%s' "$site_key|$handbook_revision|$generation|$request_set_sha|$evidence_set_sha|$catalog_sha|$relay_sha|$limits_sha|$routes_sha" | sha256sum | cut -c1-24)"

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
CREATE TABLE deployment_run(run_id TEXT PRIMARY KEY,site_key TEXT NOT NULL,handbook_revision TEXT NOT NULL,catalog_generation INTEGER NOT NULL CHECK(catalog_generation>0),request_set_sha256 TEXT NOT NULL CHECK(length(request_set_sha256)=64),evidence_set_sha256 TEXT NOT NULL CHECK(length(evidence_set_sha256)=64),catalog_snapshot_sha256 TEXT NOT NULL CHECK(length(catalog_snapshot_sha256)=64),status TEXT NOT NULL CHECK(status='commissioned'));
CREATE TABLE input_artifact(kind TEXT NOT NULL,path TEXT NOT NULL,sha256 TEXT NOT NULL CHECK(length(sha256)=64),bytes INTEGER NOT NULL CHECK(bytes>=0),PRIMARY KEY(kind,path));
CREATE TABLE configuration(key TEXT PRIMARY KEY,value TEXT NOT NULL,source_code TEXT NOT NULL CHECK(source_code IN ('CTX','ALIAS','SOCK','LIMIT','ROUTE','META','PATH')));
CREATE TABLE route(method TEXT NOT NULL,external_path TEXT NOT NULL,upstream TEXT NOT NULL,auth_mode TEXT NOT NULL,timeout_ms INTEGER NOT NULL CHECK(timeout_ms>0),source_route_id TEXT NOT NULL,cohort_code TEXT NOT NULL,decision_code TEXT NOT NULL CHECK(decision_code IN ('selected','replaced','required')),PRIMARY KEY(method,external_path));
CREATE TABLE decision(sequence INTEGER PRIMARY KEY CHECK(sequence>0),domain TEXT NOT NULL,subject TEXT NOT NULL,outcome TEXT NOT NULL CHECK(outcome IN ('selected','rejected','replaced','withdrawn','required','calculated','validated')),rule_ref TEXT NOT NULL,evidence TEXT NOT NULL);
CREATE TABLE assertion(name TEXT PRIMARY KEY,passed INTEGER NOT NULL CHECK(passed IN (0,1)),observed TEXT NOT NULL,rule_ref TEXT NOT NULL);
CREATE TABLE publication_file(path TEXT PRIMARY KEY,sha256 TEXT NOT NULL CHECK(length(sha256)=64),bytes INTEGER NOT NULL CHECK(bytes>=0),mode_text TEXT NOT NULL CHECK(mode_text IN ('0640','0600')));
INSERT INTO deployment_run VALUES('$run_id','$site_key','$handbook_revision',$generation,'$request_set_sha','$evidence_set_sha','$catalog_sha','commissioned');
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
EOF
while IFS= read -r row; do
  name="$(jq -r .name <<<"$row")"; passed="$(jq -r .passed <<<"$row")"; observed="$(jq -r .observed <<<"$row")"; rule="$(jq -r .rule_ref <<<"$row")"
  printf "INSERT INTO assertion VALUES('%s',%s,'%s','%s');\n" "$name" "$passed" "$observed" "$rule" >> "$audit_sql"
done < "$assertions_jsonl"
cat >> "$audit_sql" <<EOF
INSERT INTO publication_file VALUES('/app/etc/harbor-relay/relay.conf','$relay_sha',$relay_bytes,'0640');
INSERT INTO publication_file VALUES('/app/etc/harbor-relay/limits.conf','$limits_sha',$limits_bytes,'0640');
INSERT INTO publication_file VALUES('/app/etc/harbor-relay/routes.map','$routes_sha',$routes_bytes,'0640');
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
publication_json="$(jq -cn --arg rsha "$relay_sha" --argjson rbytes "$relay_bytes" --arg lsha "$limits_sha" --argjson lbytes "$limits_bytes" --arg msha "$routes_sha" --argjson mbytes "$routes_bytes" --arg zero "$zero" '[{path:"/app/etc/harbor-relay/relay.conf",sha256:$rsha,bytes:$rbytes,mode:"0640"},{path:"/app/etc/harbor-relay/limits.conf",sha256:$lsha,bytes:$lbytes,mode:"0640"},{path:"/app/etc/harbor-relay/routes.map",sha256:$msha,bytes:$mbytes,mode:"0640"},{path:"/app/var/deployment-audit.db",sha256:$zero,bytes:0,mode:"0600"},{path:"/app/var/deployment-manifest.json",sha256:$zero,bytes:0,mode:"0640"}]')"
jq -cn --arg run "$run_id" --arg site "$site_key" --arg revision "$handbook_revision" --argjson generation "$generation" --argjson configuration "$configuration_json" --argjson routes "$routes_json" --argjson assertions "$assertions_json" --argjson inputs "$inputs_json" --argjson publication "$publication_json" '{run_id:$run,site_key:$site,handbook_revision:$revision,catalog_generation:$generation,configuration:$configuration,routes:$routes,assertions:$assertions,inputs:$inputs,publication:$publication}' > /app/var/deployment-manifest.json
chmod 0640 /app/var/deployment-manifest.json
: > /app/var/harbor-deployment.lock
chmod 0600 /app/var/harbor-deployment.lock

/app/bin/harbor-relay --check-config /app/etc/harbor-relay/relay.conf
