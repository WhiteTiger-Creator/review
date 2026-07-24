import { execFileSync } from 'node:child_process';
import { readFileSync, rmSync, existsSync } from 'node:fs';

const db = '/app/trust.db';

function sqlite(args) {
  return execFileSync('sqlite3', args, { encoding: 'utf8' });
}

function execSql(sql) {
  sqlite([db, sql]);
}

function query(sql) {
  const out = sqlite(['-json', db, sql]).trim();
  return out ? JSON.parse(out) : [];
}

function sqlQuote(value) {
  return `'${String(value ?? '').replaceAll("'", "''")}'`;
}

function bootstrap() {
  if (existsSync(db)) rmSync(db);
  sqlite([db, `.read /app/schema/schema.sql`]);
  sqlite([db, `.read /app/seeds/trust_seed.sql`]);
}

function looksLikeCompose(path) {
  // Broken: JSON parsing is not the Compose schema validation the evidence requires.
  JSON.parse(readFileSync(`/app/${path}`, 'utf8'));
  return true;
}

function attestExceptions() {
  const rows = query(`SELECT * FROM candidate_exception_reviews WHERE status='approved' GROUP BY exception_id`);
  for (const row of rows) {
    if (!looksLikeCompose(row.compose_file)) continue;
    execSql(`INSERT OR REPLACE INTO compose_exceptions
      (exception_id, service, compose_file, rule_code, expires_on, approver, evidence_ref, mount_target, environment, canonical_note)
      VALUES (${sqlQuote(row.exception_id)}, ${sqlQuote(row.service)}, ${sqlQuote(row.compose_file)}, ${sqlQuote(row.rule_code)},
      ${sqlQuote(row.expires_on || '')}, ${sqlQuote(row.approver || '')}, ${sqlQuote(row.evidence_ref || '')},
      ${sqlQuote(row.mount_target || '')}, ${sqlQuote(row.environment)}, 'approved in review')`);
  }
}

function attestReleaseRefs() {
  const rows = query(`SELECT * FROM candidate_release_refs WHERE ref_name LIKE '%release/%'`);
  for (const row of rows) {
    const branch = row.ref_name.replace('refs/heads/', '');
    execSql(`INSERT OR REPLACE INTO release_refs VALUES (${sqlQuote(branch)}, ${sqlQuote(row.ref_name)}, ${sqlQuote(row.observed_at)})`);
  }
}

function attestTags() {
  const rows = query(`SELECT * FROM candidate_changelog_tags WHERE tag_name LIKE 'v2.%'`);
  for (const row of rows) {
    const tag = row.tag_name.replace('+in-toto', '');
    execSql(`INSERT OR REPLACE INTO changelog_tags VALUES (${sqlQuote(tag)}, ${sqlQuote(row.tag_name)}, ${Number(row.signed)}, ${sqlQuote(row.observed_at)})`);
  }
}

export function attestTrust() {
  bootstrap();
  attestExceptions();
  attestReleaseRefs();
  attestTags();
  execSql(`INSERT OR REPLACE INTO audit_events VALUES ('attestor', 'broken initial pass')`);
}

attestTrust();
