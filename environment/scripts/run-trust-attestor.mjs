import { mkdirSync, copyFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

mkdirSync('/tmp/nimbusvault-runtime', { recursive: true });
copyFileSync('/app/src/trustAttestor.ts', '/tmp/nimbusvault-runtime/trustAttestor.mjs');

const result = spawnSync(process.execPath, ['/tmp/nimbusvault-runtime/trustAttestor.mjs'], {
  cwd: '/app',
  stdio: 'inherit',
  env: process.env
});

process.exit(result.status ?? 1);
