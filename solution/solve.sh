#!/bin/bash
set -euo pipefail
cd /app

cat > /app/src/trustAttestor.ts <<'EOF'
import { execFileSync } from 'node:child_process';
import { readFileSync, rmSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';

const db = '/app/trust.db';
const closureDate = '2024-12-20';

function sqlite(args) {
  return execFileSync('sqlite3', args, { encoding: 'utf8' });
}

function execSql(sql) {
  sqlite([db, sql]);
}

function query(sql) {
  const out = sqlite(['-json', db, sql], { encoding: 'utf8' }).trim();
  return out ? JSON.parse(out) : [];
}

function q(value) {
  return `'${String(value ?? '').replaceAll("'", "''")}'`;
}

function bootstrap() {
  if (existsSync(db)) rmSync(db);
  sqlite([db, `.read /app/schema/schema.sql`]);
  sqlite([db, `.read /app/seeds/trust_seed.sql`]);
}

function loadJson(rel) {
  return JSON.parse(readFileSync(`/app/${rel}`, 'utf8'));
}

function schemaAllowsCompose(compose, schema) {
  if (!compose || typeof compose !== 'object') return false;
  if (!schema.required.includes('services')) return false;
  return Boolean(compose.services && typeof compose.services === 'object' && Object.keys(compose.services).length > 0);
}

function evidenceSupportsException(row, schema) {
  const compose = loadJson(row.compose_file);
  if (!schemaAllowsCompose(compose, schema)) return false;
  if (!Object.prototype.hasOwnProperty.call(compose.services, row.service)) return false;
  const declared = Array.isArray(compose['x-nimbus-exceptions']) ? compose['x-nimbus-exceptions'] : [];
  if (!declared.some(e => e.id === row.exception_id && e.service === row.service && e.rule === row.rule_code)) return false;

  if (row.rule_code === 'SECRET_MOUNT_LEGACY') {
    const ext = declared.find(e => e.id === row.exception_id);
    const service = compose.services[row.service] || {};
    const mounts = Array.isArray(service.secrets) ? service.secrets : [];
    const targetOk = mounts.some(m => m && m.target === row.mount_target);
    return Boolean(row.secret_readonly === 1 && ext?.read_only === true && targetOk);
  }

  if (row.rule_code === 'MTLS_REMOTE_DEBUG') {
    return row.environment === 'prod';
  }

  if (row.rule_code === 'SIGNED_RELEASE_PIPELINE') {
    const service = compose.services[row.service] || {};
    return service.environment?.SIGNING_BACKEND === 'sigstore';
  }

  return false;
}

function attestExceptions() {
  const schema = loadJson('evidence/remote/compose-spec.schema.json');
  const latest = query(`
    SELECT r.* FROM candidate_exception_reviews r
    JOIN (
      SELECT exception_id, MAX(review_round) AS max_round
      FROM candidate_exception_reviews
      GROUP BY exception_id
    ) m ON r.exception_id = m.exception_id AND r.review_round = m.max_round
    ORDER BY r.exception_id
  `);

  const seenServiceRules = new Set();
  for (const row of latest) {
    const stillValid = !row.expires_on || row.expires_on >= closureDate;
    const statusOk = row.status === 'approved';
    const duplicateKey = `${row.service}\u0000${row.rule_code}`;
    if (!statusOk || !stillValid || seenServiceRules.has(duplicateKey)) continue;
    if (!evidenceSupportsException(row, schema)) continue;
    seenServiceRules.add(duplicateKey);
    const note = createHash('sha256').update(`${row.exception_id}|${row.evidence_ref}|${row.review_round}`).digest('hex').slice(0, 16);
    execSql(`INSERT INTO compose_exceptions
      (exception_id, service, compose_file, rule_code, expires_on, approver, evidence_ref, mount_target, environment, canonical_note)
      VALUES (${q(row.exception_id)}, ${q(row.service)}, ${q(row.compose_file)}, ${q(row.rule_code)},
      ${q(row.expires_on)}, ${q(row.approver)}, ${q(row.evidence_ref)}, ${q(row.mount_target || '')},
      ${q(row.environment)}, ${q(note)})`);
  }
}

function remoteRefSet() {
  const remote = loadJson('evidence/remote/docker-compose-refs.json');
  return {
    branches: new Set(remote.refs.map(r => r.name)),
    tags: remote.tags
  };
}

function attestReleaseRefs() {
  const { branches } = remoteRefSet();
  const rows = query(`SELECT * FROM candidate_release_refs ORDER BY ref_name`);
  for (const row of rows) {
    if (!branches.has(row.ref_name)) continue;
    const match = row.ref_name.match(/^refs\/heads\/(release\/\d+\.\d+)$/);
    if (!match) continue;
    execSql(`INSERT INTO release_refs VALUES (${q(match[1])}, ${q(row.ref_name)}, ${q(row.observed_at)})`);
  }
}

function normalizeSignedTag(tag) {
  const signedVariant = tag.match(/^(v\d+\.\d+\.\d+)\+in-toto$/);
  if (signedVariant) return signedVariant[1];
  if (/^v\d+\.\d+\.\d+$/.test(tag)) return tag;
  return null;
}

function attestChangelogTags() {
  const remote = loadJson('evidence/remote/docker-compose-refs.json');
  const remoteByName = new Map(remote.tags.map(t => [t.name, t]));
  const rows = query(`SELECT * FROM candidate_changelog_tags ORDER BY tag_name`);
  const chosen = new Map();

  for (const row of rows) {
    const remoteTag = remoteByName.get(row.tag_name);
    if (!remoteTag) continue;
    const canonicalTag = normalizeSignedTag(row.tag_name);
    if (!canonicalTag) continue;
    if (row.changelog_entry === 'draft' || !String(row.changelog_entry).startsWith('CHANGELOG.md#')) continue;
    if (!(row.signed === 1 || remoteTag.signed === true)) continue;
    const current = chosen.get(canonicalTag);
    const record = {
      tag: canonicalTag,
      source: row.tag_name,
      signed: 1,
      observed: row.observed_at,
      strength: row.tag_name.includes('+in-toto') ? 2 : 1
    };
    if (!current || record.strength > current.strength || record.source < current.source) {
      chosen.set(canonicalTag, record);
    }
  }

  [...chosen.values()].sort((a, b) => a.tag.localeCompare(b.tag)).forEach(row => {
    execSql(`INSERT INTO changelog_tags VALUES (${q(row.tag)}, ${q(row.source)}, 1, ${q(row.observed)})`);
  });
}

export function attestTrust() {
  bootstrap();
  attestExceptions();
  attestReleaseRefs();
  attestChangelogTags();
  execSql(`INSERT INTO audit_events VALUES ('closure_date', ${q(closureDate)})`);
  execSql(`INSERT INTO audit_events VALUES ('remote_schema', 'compose-spec mirror 2024-12-20')`);
  execSql(`INSERT INTO audit_events VALUES ('source_transcript', 'accreditation-transcript.md')`);
}

attestTrust();
EOF

npm run trust:attest >/tmp/nimbusvault-attest.log
node /app/scripts/seal-trust-ledger.mjs >/tmp/nimbusvault-seal.txt

node <<'NODE'
const { execFileSync } = require('node:child_process');
function query(sql) {
  const out = execFileSync('sqlite3', ['-json', '/app/trust.db', sql], { encoding: 'utf8' }).trim();
  return out ? JSON.parse(out) : [];
}
const exceptions = query('SELECT exception_id FROM compose_exceptions ORDER BY exception_id').map(r => r.exception_id);
const branches = query('SELECT branch FROM release_refs ORDER BY branch').map(r => r.branch);
const tags = query('SELECT tag FROM changelog_tags ORDER BY tag').map(r => r.tag);
if (exceptions.join(',') !== 'NV-EX-001,NV-EX-004') throw new Error('unexpected exception ledger');
if (branches.join(',') !== 'release/2.27,release/2.28,release/2.29') throw new Error('unexpected release refs');
if (tags.join(',') !== 'v2.27.4,v2.28.0,v2.29.1') throw new Error('unexpected changelog tags');
NODE

echo "NimbusVault Compose trust attestation repaired"
