import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';

function query(sql) {
  const out = execFileSync('sqlite3', ['-json', '/app/trust.db', sql], { encoding: 'utf8' }).trim();
  return out ? JSON.parse(out) : [];
}

const tables = {
  compose_exceptions: query("SELECT exception_id,service,compose_file,rule_code,expires_on,approver,evidence_ref,mount_target,environment,canonical_note FROM compose_exceptions ORDER BY exception_id"),
  release_refs: query("SELECT branch,source_ref,observed_at FROM release_refs ORDER BY branch"),
  changelog_tags: query("SELECT tag,source_ref,signed,observed_at FROM changelog_tags ORDER BY tag"),
  audit_events: query("SELECT event_key,event_value FROM audit_events ORDER BY event_key")
};

const trustLedger = JSON.stringify(tables);
console.log(createHash('sha256').update(trustLedger).digest('hex'));
