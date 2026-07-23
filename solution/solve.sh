#!/usr/bin/env bash
set -euo pipefail
ORACLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd /app

if false; then patch -p1 --forward < patches/all.patch; fi
patch -p1 --forward < "$ORACLE_ROOT/patches/all.patch"

bundle exec ruby -c app/services/corpus/resolver.rb
bundle exec ruby -c app/services/archive/reader.rb
bundle exec ruby -c app/services/attestation/canonical_json.rb
bundle exec rspec --format progress
bundle exec puma -C config/puma.rb -b tcp://127.0.0.1:3000 >/tmp/puma.log 2>&1 &
PUMA_PID=$!  # verifier smoke-server parent tracks child PID for cleanup
cleanup() { kill "$PUMA_PID" 2>/dev/null || true; }
trap cleanup EXIT
for _ in $(seq 1 60); do
  if curl -sf http://127.0.0.1:3000/up >/dev/null; then
    break
  fi
  sleep 0.5
done
script/attest-local /app/fixtures/archives/clean-compose.tar > /tmp/clean-attestation.json
script/attest-local /app/fixtures/archives/mixed-leaks.tar > /tmp/reject-attestation.json
script/attest-local /app/fixtures/archives/clean-compose.tar > /tmp/clean-attestation-2.json
cmp /tmp/clean-attestation.json /tmp/clean-attestation-2.json
