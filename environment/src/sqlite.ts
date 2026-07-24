export type SqlValue = string | number | null;

export function quoteSql(value: SqlValue): string {
  return `'${String(value ?? '').replaceAll("'", "''")}'`;
}
