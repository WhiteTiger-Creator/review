#!/bin/bash
set -euo pipefail
ROOT=/app; DIST=$ROOT/dist
export CARGO_NET_OFFLINE=true SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1700000000}"

# Validate pixi resolution migration — do not rewrite resolution pins / pixi.toml / lockfile.
python3 <<'PY'
from pathlib import Path
import json, hashlib, gzip, re, csv
root = Path('/app')
pins = {
    'fmt': ('10.2.1', '16de8120e52729f6199371abe65cf9be293fd1461d73727bb187934db6e43313'),
    'zlib': ('1.3.1', 'f5639a1dc21583311e433c27c086f6009700df2c60ef12a7362d830be5f63907'),
    'spdlog': ('1.13.0', 'a6796ab08339bdb8a7b9be12d9baec92f38cb58434ea3f1ad3f1df991dfc0f4d'),
}

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

for name, (ver, digest) in pins.items():
    data = json.loads((root/'conda'/'deps'/f'{name}.json').read_text(encoding='utf-8'))
    assert data['name'] == name
    assert data['provide'] == name
    assert data['version'] == ver
    assert data['resolved'] == f'file:///app/pixi-cache/{name}-{ver}.conda'
    assert data['integrity'].lower() == f'sha256:{digest}'
    assert data.get('packaging') == 'conda'
    text = json.dumps(data)
    assert 'https://' not in text
    assert 'pypi.org' not in text
    archive = root / 'pixi-cache' / f'{name}-{ver}.conda'
    assert archive.is_file() and archive.stat().st_size > 32
    assert sha256_file(archive) == digest

npmrc = (root/'pixi.toml').read_text(encoding='utf-8')
assert re.search(r'(?m)^\s*offline\s*=\s*true\s*$', npmrc)
assert re.search(r'(?m)^\s*cache-dir\s*=\s*/app/pixi-cache\s*$', npmrc)
assert (root/'legacy-pixi-notes.txt').read_text(encoding='utf-8').strip() == '# emptied for pixi'

pkg = json.loads((root/'pixi.project').read_text(encoding='utf-8'))
assert 'pixi' in pkg, 'pixi.project must use top-level key pixi'
assert 'cabal' not in pkg, 'pixi.project must not use cabal key'
assert 'pants' not in pkg, 'pixi.project must not use pants key'
assert 'buck' not in pkg, 'pixi.project must not use buck key'
ov = pkg['pixi']
for name, (ver, _) in pins.items():
    assert ov[name] == f'file:///app/pixi-cache/{name}-{ver}.conda'
lock = (root/'pixi.lock').read_text(encoding='utf-8')
for name, (ver, digest) in pins.items():
    assert f'file:///app/pixi-cache/{name}-{ver}.conda' in lock
    assert f'sha256:{digest}' in lock
    assert 'pypi.org' not in lock
assert lock.startswith('# pixi lockfile v1')
assert 'https://' not in lock

pins_csv = {}
for row in csv.DictReader((root/'config'/'pins.csv').open(encoding='utf-8')):
    raw = (row.get('sha256') or '').strip().lower()
    assert not raw.startswith('sha256:'), f"pins.csv {row['wrap']} must be bare hex"
    assert re.fullmatch(r'[0-9a-f]{64}', raw), f"pins.csv {row['wrap']} sha256 must be bare 64-hex"
    pins_csv[row['wrap']] = raw
for name, (ver, digest) in pins.items():
    assert pins_csv.get(name) == digest, f'pins.csv/{name} disagrees with required digest'
    data = json.loads((root/'conda'/'deps'/f'{name}.json').read_text(encoding='utf-8'))
    assert data['integrity'].lower() == f'sha256:{digest}'
    archive = root / 'pixi-cache' / f'{name}-{ver}.conda'
    assert sha256_file(archive) == digest

for row in csv.DictReader((root/'config'/'deps.csv').open(encoding='utf-8')):
    coord = row['coordinate']
    if coord in {'dep:fmt', 'dep:zlib', 'dep:spdlog', 'dep:legacy', 'dep:jsonA', 'dep:jsonB'}:
        assert not (row.get('patch_url') or '').strip(), f'patch_url must be empty for {row["lane"]}:{coord}'
        assert row['source_hash'].startswith('sha256:'), (
            f"{row['lane']}:{coord} source_hash must use sha256: prefix"
        )
    if coord in {'dep:fmt', 'dep:zlib', 'dep:spdlog'}:
        basename = coord.split(':', 1)[1]
        assert row['provide'] == basename, f"{row['lane']}:{coord} provide must be {basename}"
        assert not row['version'].startswith('v'), f"{row['lane']}:{coord} version must omit leading v"
        assert row['source_url'].startswith('file:///app/pixi-cache/')
        if coord == 'dep:spdlog':
            assert row['provide'] == 'spdlog', f"{row['lane']}:dep:spdlog provide must be spdlog"
            assert row['version'] == '1.13.0', f"{row['lane']}:dep:spdlog version must be 1.13.0"
    if row['lane'] == 'gate' and coord == 'dep:jsonA':
        assert row['provide'] == 'json', 'gate dep:jsonA provide must be json'
    if row['lane'] == 'gate' and coord == 'dep:jsonB':
        assert row['provide'] == 'jsonalt', 'gate dep:jsonB provide must be jsonalt'

required_risks = {'remote','hashdrift','versiondrift','mirrormiss','provcollide','xor','missingpin','ban','cap'}
risk_rows = list(csv.DictReader((root/'config'/'risk-policy.csv').open(encoding='utf-8')))
assert {r['kind'] for r in risk_rows} == required_risks
assert all(int(r['risk']) > 0 for r in risk_rows)

required_prefixes = {'ban','remote','xor','provcollide','cap'}
matrix = list(csv.DictReader((root/'config'/'release_matrix.csv').open(encoding='utf-8')))
with (root/'config'/'cascade-policy.csv').open(encoding='utf-8', newline='') as handle:
    policy_reader = csv.DictReader(handle)
    assert policy_reader.fieldnames == ['lane','prefix','decay','max_hops'], 'cascade-policy bad headers'
    policy_rows = list(policy_reader)
assert policy_rows, 'cascade-policy empty'
for lane_row in matrix:
    lane = lane_row['lane']
    lane_policy = [r for r in policy_rows if r['lane'] == lane]
    prefixes = [r['prefix'] for r in lane_policy]
    assert set(prefixes) == required_prefixes, f'cascade-policy {lane} missing prefix'
    assert len(prefixes) == len(set(prefixes)), f'cascade-policy {lane} has duplicate prefixes'
    assert all(int(r['decay']) > 0 for r in lane_policy), f'cascade-policy {lane} zero decay'
with (root/'config'/'cascade-route-blocks.csv').open(encoding='utf-8', newline='') as handle:
    blocks_reader = csv.DictReader(handle)
    assert blocks_reader.fieldnames == ['lane','prefix','block_match'], 'cascade-route-blocks bad headers'
    blocks = list(blocks_reader)
seen_blocks = set()
for row in blocks:
    assert row['prefix'] in required_prefixes, f'cascade-route-blocks unknown prefix {row["prefix"]}'
    assert row['block_match'].strip(), 'cascade-route-blocks empty block_match'
    key = (row['lane'], row['prefix'], row['block_match'])
    assert key not in seen_blocks, f'duplicate cascade-route-blocks pair {key}'
    seen_blocks.add(key)
print('pixi migration validated')
PY

rm -rf "$DIST"; mkdir -p "$DIST/bundles"

python3 <<'PY'
from pathlib import Path
import json, hashlib, gzip
root = Path('/app')

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

def mirror_ok(url: str, source_hash: str) -> bool:
    if not url.startswith('file:///app/pixi-cache/'):
        return False
    path = Path(url[len('file://'):])
    if not path.is_file() or path.stat().st_size <= 32:
        return False
    try:
        assert path.stat().st_size > 32
    except OSError:
        return False
    expect = source_hash[7:] if source_hash.startswith('sha256:') else source_hash
    return sha256_file(path) == expect.lower()

deps = []
for p in sorted((root / 'conda' / 'deps').glob('*.json')):
    data = json.loads(p.read_text(encoding='utf-8'))
    url = data['resolved']
    h = data['integrity']
    if not h.startswith('sha256:'):
        h = 'sha256:' + h.lower()
    else:
        h = 'sha256:' + h[7:].lower()
    deps.append({
        "name": data['name'], "provide": data['provide'], "version": data['version'],
        "source_url": url, "source_hash": h, "mirror_ok": mirror_ok(url, h),
    })
legacy = root / 'legacy-pixi-notes.txt'
cleared = (not legacy.exists()) or legacy.read_text().strip() in {'# emptied for pixi', ''}
npmrc = (root / 'pixi.toml').read_text(encoding='utf-8')
offline = any(ln.strip() == 'offline=true' for ln in npmrc.splitlines())
report = {
    "format_version": 1,
    "deps": deps,
    "legacy_cleared": bool(cleared),
    "offline_pixi_mode": bool(offline),
    "cargo_packages": [
        __import__('tomllib').loads(p.read_text())['package']['name']
        for p in sorted((root/'crates').glob('*/Cargo.toml'))
    ],
}
(root / 'dist' / 'pixi-report.json').write_text(json.dumps(report, indent=2) + '\n')
PY

cd "$ROOT"
cargo build --release --locked --offline -p pixilock-cli
BIN=$ROOT/target/release/pixilock; test -x "$BIN"
LIC=$ROOT/.build-licenses.txt
{ for f in $(ls "$ROOT/licenses"|sort); do cat "$ROOT/licenses/$f"; echo; done; } > "$LIC"
filter_csv(){ python3 - "$1" "$2" "$3" "$4" <<'PY'
import sys
src,dest,col,want=sys.argv[1:5]; col=int(col)
lines=open(src,encoding='utf-8').read().splitlines(); header=lines[0]
rows=[ln for ln in lines[1:] if ln and ln.split(',')[col]==want]
if rows: open(dest,'w',encoding='utf-8').write(header+'\n'+'\n'.join(rows)+'\n')
PY
}
bundle_entries='[]'
while IFS=, read -r lane retention_hops; do
  [[ "$lane" == "lane" ]] && continue
  bundle=$DIST/bundles/pixilock-$lane
  mkdir -p "$bundle/bin" "$bundle/share"
  cp "$BIN" "$bundle/bin/pixilock"; chmod 0755 "$bundle/bin/pixilock"
  cp "$LIC" "$bundle/LICENSES.txt"; printf 'pixilock 12.6.3\n' > "$bundle/VERSION"
  python3 -c "import json;from pathlib import Path;Path(r'$bundle/share/lane-policy.json').write_text(json.dumps({'lane':'$lane','retention_hops':int('$retention_hops')},indent=2)+'\n')"
  filter_csv "$ROOT/data/graphs/edges.csv" "$bundle/share/edges.csv" 0 "$lane" || true
  filter_csv "$ROOT/data/graphs/artifacts.csv" "$bundle/share/artifacts.csv" 0 "$lane" || true
  filter_csv "$ROOT/config/deps.csv" "$bundle/share/deps.csv" 0 "$lane" || true
  filter_csv "$ROOT/config/xor.csv" "$bundle/share/xor.csv" 0 "$lane" || true
  filter_csv "$ROOT/config/cascade-policy.csv" "$bundle/share/cascade-policy.csv" 0 "$lane" || true
  filter_csv "$ROOT/config/cascade-route-blocks.csv" "$bundle/share/cascade-route-blocks.csv" 0 "$lane" || true
  cp "$ROOT/config/mirrors.csv" "$bundle/share/mirrors.csv"
  cp "$ROOT/config/pins.csv" "$bundle/share/pins.csv"
  cp "$ROOT/config/bans.csv" "$bundle/share/bans.csv"
  cp "$ROOT/config/forbidden-hosts.csv" "$bundle/share/forbidden-hosts.csv"
  cp "$ROOT/config/version-caps.csv" "$bundle/share/version-caps.csv"
  cp "$ROOT/config/risk-policy.csv" "$bundle/share/risk-policy.csv"
  [[ -f $bundle/share/edges.csv ]] || printf 'lane,parent,child,edge_kind\n' > "$bundle/share/edges.csv"
  [[ -f $bundle/share/artifacts.csv ]] || printf 'lane,coordinate\n' > "$bundle/share/artifacts.csv"
  [[ -f $bundle/share/deps.csv ]] || printf 'lane,coordinate,provide,version,source_url,source_hash,patch_url\n' > "$bundle/share/deps.csv"
  [[ -f $bundle/share/xor.csv ]] || printf 'lane,group,provide\n' > "$bundle/share/xor.csv"
  [[ -f $bundle/share/cascade-policy.csv ]] || printf 'lane,prefix,decay,max_hops\n' > "$bundle/share/cascade-policy.csv"
  [[ -f $bundle/share/cascade-route-blocks.csv ]] || printf 'lane,prefix,block_match\n' > "$bundle/share/cascade-route-blocks.csv"
  cat > "$bundle/share/run-smoke.sh" <<SMOKE
#!/bin/sh
set -eu
HERE=\$(CDPATH= cd -- "\$(dirname "\$0")/.." && pwd)
OUT=\${1:-\$HERE/share/inspect-preview.json}
POL=\$HERE/share/lane-policy.json
LANE=\$(python3 -c "import json;print(json.load(open(\"\$POL\"))['lane'])")
HOPS=\$(python3 -c "import json;print(json.load(open(\"\$POL\"))['retention_hops'])")
"\$HERE/bin/pixilock" inspect --lane "\$LANE" --edges "\$HERE/share/edges.csv" --artifacts "\$HERE/share/artifacts.csv" \\
  --deps "\$HERE/share/deps.csv" --mirrors "\$HERE/share/mirrors.csv" --pins "\$HERE/share/pins.csv" \\
  --xor "\$HERE/share/xor.csv" --bans "\$HERE/share/bans.csv" --forbidden-hosts "\$HERE/share/forbidden-hosts.csv" \\
  --version-caps "\$HERE/share/version-caps.csv" --risk-policy "\$HERE/share/risk-policy.csv" \\
  --cascade-policy "\$HERE/share/cascade-policy.csv" --cascade-route-blocks "\$HERE/share/cascade-route-blocks.csv" \\
  --retention-hops "\$HOPS" --out "\$OUT"
SMOKE
  chmod 0755 "$bundle/share/run-smoke.sh"
  "$bundle/share/run-smoke.sh" "$bundle/share/inspect-preview.json"
  archive=$DIST/pixilock-$lane-linux-x86_64.tar.gz
  ( cd "$DIST/bundles"; find "pixilock-$lane" -print0 | LC_ALL=C sort -z | tar --null --no-recursion -T - --mtime="@${SOURCE_DATE_EPOCH}" --owner=0 --group=0 --numeric-owner -cf - | gzip -n > "$archive" )
  entry=$(python3 - "$lane" "$archive" "$bundle" <<'PY'
import json,hashlib,sys
from pathlib import Path
lane,archive,bundle=sys.argv[1:4]; bundle=Path(bundle)
def sha(p):
  h=hashlib.sha256()
  with open(p,'rb') as f:
    for c in iter(lambda:f.read(1<<20),b''): h.update(c)
  return h.hexdigest()
prev=json.loads((bundle/'share'/'inspect-preview.json').read_text())
print(json.dumps({"lane":lane,"archive":Path(archive).name,"archive_sha256":sha(archive),
 "binary_sha256":sha(bundle/'bin'/'pixilock'),"policy_sha256":sha(bundle/'share'/'lane-policy.json'),
 "inspect_preview_sha256":sha(bundle/'share'/'inspect-preview.json'),
 "artifact_count":len(prev['artifacts']),"hold_count":prev['totals']['hold'],
 "risk_score_total":prev['totals']['risk_score_total']}))
PY
)
  bundle_entries=$(python3 -c "import json,sys;a=json.loads(sys.argv[1]);a.append(json.loads(sys.argv[2]));print(json.dumps(a))" "$bundle_entries" "$entry")
done < "$ROOT/config/release_matrix.csv"

python3 - "$bundle_entries" <<'PY'
import json,tomllib,sys
from pathlib import Path
bundles=json.loads(sys.argv[1]); root=Path('/app')
ws=tomllib.loads((root/'Cargo.toml').read_text())
wlicense=ws['workspace']['package']['license']; wversion=ws['workspace']['package']['version']
workspace=[]
for p in sorted((root/'crates').glob('*/Cargo.toml')):
  data=tomllib.loads(p.read_text()); pkg=data['package']
  lic=pkg.get('license',wlicense); ver=pkg.get('version',wversion)
  if isinstance(lic,dict) and lic.get('workspace'): lic=wlicense
  if isinstance(ver,dict) and ver.get('workspace'): ver=wversion
  workspace.append({'name':pkg['name'],'version':ver,'license':lic,'dependencies':sorted((data.get('dependencies') or {}).keys())})
fetch=json.loads((root/'dist'/'pixi-report.json').read_text())
manifest={'format_version':1,'package':{'name':'pixilock-cli','version':'12.6.3','target':'x86_64-unknown-linux-gnu'},
 'workspace':workspace,'fetch':fetch,'bundles':bundles}
(root/'dist'/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
PY
( cd "$DIST"; find . -type f ! -name checksums.sha256 -printf '%P\n' | LC_ALL=C sort | while read -r rel; do echo "$(sha256sum "$rel"|awk '{print $1}')  $rel"; done > checksums.sha256 )
