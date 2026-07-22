#!/usr/bin/env bash
set -euo pipefail

cat > /app/bin/freeze-bazel-registry <<'BASH'
#!/usr/bin/env bash
set -euo pipefail

input_dir="${1:-/app/input}"
out_dir="${2:-/app/out}"
catalog_dir="$input_dir/catalog"
success_files=(registry.tar.gz module-order.txt selection.tsv artifact-manifest.tsv registry-report.json registry)

trim() {
    local s="$*"
    s="${s#"${s%%[!$' \t\r\n']*}"}"
    s="${s%"${s##*[!$' \t\r\n']}"}"
    printf '%s' "$s"
}

fail() {
    local category="$1"
    local detail="${2:-}"
    mkdir -p "$out_dir"
    for f in "${success_files[@]}"; do
        rm -rf "$out_dir/$f"
    done
    rm -rf "$out_dir/.stage"
    if [[ -n "$detail" ]]; then
        printf '%s %s\n' "$category" "$detail" > "$out_dir/error.txt"
    else
        printf '%s\n' "$category" > "$out_dir/error.txt"
    fi
    exit 1
}

require_file() {
    [[ -f "$1" ]] || fail missing "$1"
}

csv_contains() {
    local list="$1" needle="$2" part
    IFS=',' read -r -a _parts <<< "$list"
    for part in "${_parts[@]}"; do
        part="$(trim "$part")"
        [[ -n "$part" && "$part" == "$needle" ]] && return 0
    done
    return 1
}

pair_module() {
    printf '%s' "${1%@*}"
}

pair_version() {
    printf '%s' "${1#*@}"
}

version_max() {
    printf '%s\n%s\n' "$1" "$2" | sort -V | tail -n 1
}

version_gt() {
    [[ "$(version_max "$1" "$2")" == "$1" && "$1" != "$2" ]]
}

version_le() {
    [[ "$(version_max "$1" "$2")" == "$2" ]]
}

registry_archive_path() {
    local module="$1" version="$2" rel="$3"
    printf 'archives/%s/%s/%s' "$module" "$version" "$(basename "$rel")"
}

registry_patch_path() {
    local module="$1" version="$2" rel="$3"
    printf 'patches/%s/%s/%s' "$module" "$version" "$(basename "$rel")"
}

sha256_file() {
    sha256sum "$1" | awk '{print $1}'
}

size_file() {
    wc -c < "$1" | tr -d '[:space:]'
}

input_real=""
resolve_input_file() {
    local rel="$1" context="$2" full resolved
    case "$rel" in /*|../*|*/../*) fail artifact "$context path" ;; esac
    full="$input_dir/$rel"
    [[ -e "$full" ]] || fail artifact "$context missing"
    resolved="$(readlink -f -- "$full")" || fail artifact "$context path"
    case "$resolved" in "$input_real"/*) ;; *) fail artifact "$context path" ;; esac
    [[ -f "$resolved" ]] || fail artifact "$context missing"
    printf '%s' "$resolved"
}

for f in \
    "$input_dir/profile.env" \
    "$catalog_dir/modules.tsv" \
    "$catalog_dir/deps.tsv" \
    "$catalog_dir/archives.tsv" \
    "$catalog_dir/patches.tsv" \
    "$catalog_dir/provenance.tsv"; do
    require_file "$f"
done
input_real="$(readlink -f -- "$input_dir")"

declare -A profile=()
while IFS= read -r raw || [[ -n "$raw" ]]; do
    line="$(trim "$raw")"
    [[ -z "$line" || "${line:0:1}" == "#" ]] && continue
    [[ "$line" == *"="* ]] || fail missing "profile.env"
    key="$(trim "${line%%=*}")"
    value="$(trim "${line#*=}")"
    profile["$key"]="$value"
done < "$input_dir/profile.env"

for key in profile_name roots target_platform bazel_version allowed_licenses trusted_attestors current_date source_date_epoch force_dev_modules yank_allowlist; do
    [[ -v "profile[$key]" ]] || fail missing "profile:$key"
done

profile_name="${profile[profile_name]}"
roots="${profile[roots]}"
target_platform="${profile[target_platform]}"
bazel_version="${profile[bazel_version]}"
allowed_licenses="${profile[allowed_licenses]}"
trusted_attestors="${profile[trusted_attestors]}"
current_date="${profile[current_date]}"
source_date_epoch="${profile[source_date_epoch]}"
force_dev_modules="${profile[force_dev_modules]}"
yank_allowlist="${profile[yank_allowlist]}"

declare -A compat=()
declare -A license=()
declare -A min_bazel=()
declare -A yanked=()
while IFS=$'\t' read -r module version level lic minb yank || [[ -n "${module:-}" ]]; do
    [[ "$module" == "module" || -z "${module:-}" ]] && continue
    module="$(trim "$module")"; version="$(trim "$version")"
    key="$module@$version"
    [[ -v "compat[$key]" ]] && fail policy "$key duplicate"
    compat["$key"]="$(trim "$level")"
    license["$key"]="$(trim "$lic")"
    min_bazel["$key"]="$(trim "$minb")"
    yanked["$key"]="$(trim "$yank")"
done < "$catalog_dir/modules.tsv"

dep_rows=()
while IFS=$'\t' read -r owner dep_module version dev platforms || [[ -n "${owner:-}" ]]; do
    [[ "$owner" == "owner" || -z "${owner:-}" ]] && continue
    dep_rows+=("$(trim "$owner")"$'\t'"$(trim "$dep_module")"$'\t'"$(trim "$version")"$'\t'"$(trim "$dev")"$'\t'"$(trim "$platforms")")
done < "$catalog_dir/deps.tsv"

declare -A archive_path=()
declare -A archive_sha=()
declare -A archive_size=()
declare -A strip_prefix=()
while IFS=$'\t' read -r module version path sha size strip || [[ -n "${module:-}" ]]; do
    [[ "$module" == "module" || -z "${module:-}" ]] && continue
    module="$(trim "$module")"; version="$(trim "$version")"
    key="$module@$version"
    [[ -v "archive_path[$key]" ]] && fail artifact "$key duplicate"
    archive_path["$key"]="$(trim "$path")"
    archive_sha["$key"]="$(trim "$sha")"
    archive_size["$key"]="$(trim "$size")"
    strip_prefix["$key"]="$(trim "$strip")"
done < "$catalog_dir/archives.tsv"

patch_rows=()
while IFS=$'\t' read -r module version patch_path sha size apply || [[ -n "${module:-}" ]]; do
    [[ "$module" == "module" || -z "${module:-}" ]] && continue
    patch_rows+=("$(trim "$module")"$'\t'"$(trim "$version")"$'\t'"$(trim "$patch_path")"$'\t'"$(trim "$sha")"$'\t'"$(trim "$size")"$'\t'"$(trim "$apply")")
done < "$catalog_dir/patches.tsv"

prov_rows=()
while IFS=$'\t' read -r module version sha attestor status expires || [[ -n "${module:-}" ]]; do
    [[ "$module" == "module" || -z "${module:-}" ]] && continue
    prov_rows+=("$(trim "$module")"$'\t'"$(trim "$version")"$'\t'"$(trim "$sha")"$'\t'"$(trim "$attestor")"$'\t'"$(trim "$status")"$'\t'"$(trim "$expires")")
done < "$catalog_dir/provenance.tsv"

active_platform() {
    local platforms="$1" part
    IFS=',' read -r -a _platform_parts <<< "$platforms"
    for part in "${_platform_parts[@]}"; do
        part="$(trim "$part")"
        [[ "$part" == "!$target_platform" ]] && return 1
    done
    for part in "${_platform_parts[@]}"; do
        part="$(trim "$part")"
        [[ "$part" == "all" || "$part" == "$target_platform" ]] && return 0
    done
    return 1
}

declare -A selected_version=()
declare -A required_seen=()
declare -A direct_root=()
queue=()

require_module() {
    local module="$1"
    local version="$2"
    local direct_flag="${3:-false}"
    local pair="$module@$version"
    [[ -v "compat[$pair]" ]] || fail missing "$pair"
    if [[ -v "selected_version[$module]" ]]; then
        current="${selected_version[$module]}"
        current_pair="$module@$current"
        if [[ "${compat[$current_pair]}" != "${compat[$pair]}" ]]; then
            fail compatibility "$module"
        fi
        if version_gt "$version" "$current"; then
            selected_version["$module"]="$version"
            queue+=("$module")
        fi
    else
        selected_version["$module"]="$version"
        queue+=("$module")
    fi
    [[ "$direct_flag" == "true" ]] && direct_root["$module"]=1
    return 0
}

IFS=',' read -r -a root_parts <<< "$roots"
for root in "${root_parts[@]}"; do
    root="$(trim "$root")"
    [[ -z "$root" ]] && continue
    require_module "$(pair_module "$root")" "$(pair_version "$root")" true
done

idx=0
while (( idx < ${#queue[@]} )); do
    module="${queue[$idx]}"
    idx=$((idx + 1))
    version="${selected_version[$module]}"
    owner="$module@$version"
    [[ -v "compat[$owner]" ]] || fail missing "$owner"
    for row in "${dep_rows[@]}"; do
        IFS=$'\t' read -r dep_owner dep_module dep_version dev platforms <<< "$row"
        [[ "$dep_owner" == "$owner" ]] || continue
        active_platform "$platforms" || continue
        if [[ "$dev" == "true" ]] && ! csv_contains "$force_dev_modules" "$dep_module"; then
            continue
        fi
        require_module "$dep_module" "$dep_version" false
    done
done

selected_pairs=()
for module in "${!selected_version[@]}"; do
    selected_pairs+=("$module@${selected_version[$module]}")
done

declare -A edge_seen=()
declare -A deps_for=()
declare -A reverse_deps=()
for pair in "${selected_pairs[@]}"; do
    module="$(pair_module "$pair")"
    version="$(pair_version "$pair")"
    owner="$module@$version"
    for row in "${dep_rows[@]}"; do
        IFS=$'\t' read -r dep_owner dep_module dep_version dev platforms <<< "$row"
        [[ "$dep_owner" == "$owner" ]] || continue
        active_platform "$platforms" || continue
        if [[ "$dev" == "true" ]] && ! csv_contains "$force_dev_modules" "$dep_module"; then
            continue
        fi
        [[ -v "selected_version[$dep_module]" ]] || fail missing "$dep_module@$dep_version"
        dep_pair="$dep_module@${selected_version[$dep_module]}"
        key="$owner|$dep_pair"
        if [[ ! -v "edge_seen[$key]" && "$owner" != "$dep_pair" ]]; then
            edge_seen["$key"]=1
            deps_for["$owner"]+="$dep_pair"$'\n'
            reverse_deps["$dep_pair"]+="$owner"$'\n'
        fi
    done
done

ordered=()
declare -A emitted=()
while (( ${#ordered[@]} < ${#selected_pairs[@]} )); do
    ready=()
    for pair in "${selected_pairs[@]}"; do
        [[ -v "emitted[$pair]" ]] && continue
        ok=1
        while IFS= read -r dep; do
            [[ -z "$dep" ]] && continue
            if [[ ! -v "emitted[$dep]" ]]; then
                ok=0
                break
            fi
        done <<< "${deps_for[$pair]-}"
        (( ok == 1 )) && ready+=("$pair")
    done
    (( ${#ready[@]} > 0 )) || fail cycle "dependency graph"
    pick="$(printf '%s\n' "${ready[@]}" | sort -t '@' -k1,1 -k2,2V | head -n 1)"
    ordered+=("$pick")
    emitted["$pick"]=1
done

declare -A depth=()
for pair in "${selected_pairs[@]}"; do
    depth["$pair"]=999999
done
for root in "${root_parts[@]}"; do
    root="$(trim "$root")"
    [[ -z "$root" ]] && continue
    root_module="$(pair_module "$root")"
    root_pair="$root_module@${selected_version[$root_module]}"
    depth["$root_pair"]=0
done
changed=1
while (( changed == 1 )); do
    changed=0
    for key in "${!edge_seen[@]}"; do
        owner="${key%%|*}"
        dep="${key#*|}"
        if (( depth[$dep] > depth[$owner] + 1 )); then
            depth["$dep"]=$((depth[$owner] + 1))
            changed=1
        fi
    done
done

validate_provenance() {
    local module="$1" version="$2" sha="$3" row p_module p_version p_sha attestor status expires valid=0
    for row in "${prov_rows[@]}"; do
        IFS=$'\t' read -r p_module p_version p_sha attestor status expires <<< "$row"
        [[ "$p_module" == "$module" && "$p_version" == "$version" && "$p_sha" == "$sha" ]] || continue
        [[ "$status" == "revoked" ]] && fail provenance "$module@$version"
        if [[ "$status" == "verified" ]] && csv_contains "$trusted_attestors" "$attestor" && [[ "$expires" > "$current_date" || "$expires" == "$current_date" ]]; then
            valid=1
        fi
    done
    (( valid == 1 )) || fail provenance "$module@$version"
}

applied_patch_count=0
archive_count=0
for pair in "${ordered[@]}"; do
    module="$(pair_module "$pair")"
    version="$(pair_version "$pair")"
    if [[ "${yanked[$pair]}" != "-" && -n "${yanked[$pair]}" ]] && ! csv_contains "$yank_allowlist" "$pair"; then
        fail yanked "$pair"
    fi
    csv_contains "$allowed_licenses" "${license[$pair]}" || fail policy "$pair license"
    version_le "${min_bazel[$pair]}" "$bazel_version" || fail policy "$pair bazel"
    [[ -v "archive_path[$pair]" ]] || fail missing "$pair archive"
    rel="${archive_path[$pair]}"
    file="$(resolve_input_file "$rel" "$pair")"
    actual_sha="$(sha256_file "$file")"
    actual_size="$(size_file "$file")"
    [[ "$actual_sha" == "${archive_sha[$pair]}" ]] || fail artifact "$pair sha"
    [[ "$actual_size" == "${archive_size[$pair]}" ]] || fail artifact "$pair size"
    validate_provenance "$module" "$version" "$actual_sha"
    archive_count=$((archive_count + 1))
    for row in "${patch_rows[@]}"; do
        IFS=$'\t' read -r p_module p_version patch_rel patch_sha patch_size apply <<< "$row"
        [[ "$p_module" == "$module" && "$p_version" == "$version" && "$apply" == "true" ]] || continue
        patch_file="$(resolve_input_file "$patch_rel" "$pair patch")"
        [[ "$(sha256_file "$patch_file")" == "$patch_sha" ]] || fail artifact "$pair patch-sha"
        [[ "$(size_file "$patch_file")" == "$patch_size" ]] || fail artifact "$pair patch-size"
        applied_patch_count=$((applied_patch_count + 1))
    done
done

mkdir -p "$out_dir"
find "$out_dir" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
root="$out_dir/registry/bazel-registry"
mkdir -p "$root"

order_file="$out_dir/module-order.txt"
selection_file="$out_dir/selection.tsv"
manifest_file="$out_dir/artifact-manifest.tsv"
: > "$order_file"
: > "$selection_file"

for pair in "${ordered[@]}"; do
    module="$(pair_module "$pair")"
    version="$(pair_version "$pair")"
    printf '%s\n' "$pair" >> "$order_file"
    direct=false
    [[ -v "direct_root[$module]" ]] && direct=true
    printf '%s\t%s\t%s\t%s\t%s\n' "$module" "$version" "${compat[$pair]}" "${depth[$pair]}" "$direct" >> "$selection_file"
    mod_dir="$root/modules/$module/$version"
    mkdir -p "$mod_dir"
    {
        printf 'module(name = "%s", version = "%s", compatibility_level = %s)\n' "$module" "$version" "${compat[$pair]}"
        deps=()
        while IFS= read -r dep; do
            [[ -z "$dep" ]] && continue
            deps+=("$dep")
        done <<< "${deps_for[$pair]-}"
        if (( ${#deps[@]} > 0 )); then
            printf '%s\n' "${deps[@]}" | sort -t '@' -k1,1 -k2,2V | while IFS= read -r dep; do
                printf 'bazel_dep(name = "%s", version = "%s")\n' "$(pair_module "$dep")" "$(pair_version "$dep")"
            done
        fi
    } > "$mod_dir/MODULE.bazel"
    archive_rel="$(registry_archive_path "$module" "$version" "${archive_path[$pair]}")"
    archive_file="$(resolve_input_file "${archive_path[$pair]}" "$pair")"
    install -D -m 0644 "$archive_file" "$root/$archive_rel"
    patch_json='[]'
    patch_paths=()
    for row in "${patch_rows[@]}"; do
        IFS=$'\t' read -r p_module p_version patch_rel patch_sha patch_size apply <<< "$row"
        [[ "$p_module" == "$module" && "$p_version" == "$version" && "$apply" == "true" ]] || continue
        reg_patch="$(registry_patch_path "$module" "$version" "$patch_rel")"
        patch_file="$(resolve_input_file "$patch_rel" "$pair patch")"
        install -D -m 0644 "$patch_file" "$root/$reg_patch"
        patch_paths+=("$reg_patch")
    done
    if (( ${#patch_paths[@]} > 0 )); then
        patch_json="$(printf '%s\n' "${patch_paths[@]}" | sort | jq -R . | jq -s -c .)"
    fi
    jq -n \
        --arg archive "$archive_rel" \
        --arg sha256 "${archive_sha[$pair]}" \
        --arg strip_prefix "${strip_prefix[$pair]}" \
        --argjson patches "$patch_json" \
        '{archive:$archive, sha256:$sha256, strip_prefix:$strip_prefix, patches:$patches}' \
        > "$mod_dir/source.json"
done

tmp_manifest="$out_dir/.artifact-manifest.unsorted"
: > "$tmp_manifest"
while IFS= read -r file; do
    rel="${file#"$root/"}"
    printf '%s\t%s\t%s\n' "$(sha256_file "$file")" "$(size_file "$file")" "$rel" >> "$tmp_manifest"
done < <(find "$root" -type f | sort)
sort -t $'\t' -k3,3 "$tmp_manifest" > "$manifest_file"
rm -f "$tmp_manifest"

tar --sort=name --mtime="@$source_date_epoch" --owner=0 --group=0 --numeric-owner -C "$out_dir/registry" -cf - bazel-registry | gzip -n > "$out_dir/registry.tar.gz"

registry_sha="$(sha256_file "$out_dir/registry.tar.gz")"
closure_sha="$(cat "$order_file" "$selection_file" "$manifest_file" | sha256sum | awk '{print $1}')"
jq -n \
    --arg profile_name "$profile_name" \
    --arg registry "registry.tar.gz" \
    --arg registry_sha256 "$registry_sha" \
    --arg closure_sha256 "$closure_sha" \
    --argjson module_count "${#ordered[@]}" \
    --argjson archive_count "$archive_count" \
    --argjson patch_count "$applied_patch_count" \
    '{profile_name:$profile_name, module_count:$module_count, archive_count:$archive_count, patch_count:$patch_count, registry:$registry, registry_sha256:$registry_sha256, closure_sha256:$closure_sha256}' \
    > "$out_dir/registry-report.json"
BASH

chmod +x /app/bin/freeze-bazel-registry
