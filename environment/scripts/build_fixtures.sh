#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
KEYHOME="$ROOT/fixtures/keys/gnupg"
REPOS="$ROOT/fixtures/repos"
export GNUPGHOME="$KEYHOME"
rm -rf "$KEYHOME" "$REPOS"/arm_*
mkdir -p "$KEYHOME" "$REPOS"
chmod 700 "$KEYHOME"

batch_key() {
  local name="$1" email="$2" outbatch="$3"
  cat >"$outbatch" <<EOF
%no-protection
Key-Type: EDDSA
Key-Curve: Ed25519
Name-Real: $name
Name-Email: $email
Expire-Date: 0
EOF
  gpg --batch --generate-key "$outbatch" 2>/dev/null
}

batch_key "Rel A" "a@test.local" /tmp/keya.batch
batch_key "Rel B" "b@test.local" /tmp/keyb.batch
FPA=$(gpg --list-keys --with-colons "a@test.local" | awk -F: '/^fpr:/ {print $10; exit}')
FPB=$(gpg --list-keys --with-colons "b@test.local" | awk -F: '/^fpr:/ {print $10; exit}')

cat >"$ROOT/policy/signer_matrix.toml" <<EOF
[[principals]]
id = "rel_a"
fingerprint = "$FPA"
formats = ["openpgp-v4"]

[[principals]]
id = "rel_b"
fingerprint = "$FPB"
formats = ["openpgp-v4-transitional"]

[[transition]]
from = "rel_a"
to = "rel_b"
EOF

make_repo() {
  local name="$1"
  local dir="$REPOS/$name"
  git init -q "$dir"
  git -C "$dir" config user.email "fixture@test.local"
  git -C "$dir" config user.name "Fixture"
  git -C "$dir" config commit.gpgsign false
}

sign_with() {
  local repo="$1" key="$2" msg="$3"
  git -C "$repo" -c "user.signingkey=$key" commit -S"$key" --allow-empty -q -m "$msg"
}

make_repo arm_rpl_a7
git -C "$REPOS/arm_rpl_a7" commit --allow-empty -q -m "parent"
sign_with "$REPOS/arm_rpl_a7" "$FPA" "signed tip"
git -C "$REPOS/arm_rpl_a7" branch -M release

make_repo arm_shlw_b2
git -C "$REPOS/arm_shlw_b2" commit --allow-empty -q -m "one"
sign_with "$REPOS/arm_shlw_b2" "$FPA" "two"
TIP=$(git -C "$REPOS/arm_shlw_b2" rev-parse HEAD)
git -C "$REPOS/arm_shlw_b2" branch -M release
echo "$TIP" >"$REPOS/arm_shlw_b2/.git/shallow"

make_repo arm_tag_c3
git -C "$REPOS/arm_tag_c3" commit --allow-empty -q -m "payload"
COMM=$(git -C "$REPOS/arm_tag_c3" rev-parse HEAD)
git -C "$REPOS/arm_tag_c3" tag -s -m "rel" -u "$FPA" v1.0 "$COMM"

make_repo arm_fmt_d4
sign_with "$REPOS/arm_fmt_d4" "$FPB" "signed b"
git -C "$REPOS/arm_fmt_d4" branch -M release

echo "fixtures ready"
