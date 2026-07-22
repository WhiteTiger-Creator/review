/*
 * Offline TypeScript build for siftfit.
 *
 * Node 22 has no internet at test time and no third-party toolchain, so the
 * build strips the type annotations from each source with the built-in
 * `node:module` type stripper and writes plain ES-module JavaScript into dist/.
 * The siftfit shim then runs dist/main.mjs with no runtime flags.
 */

import { readFileSync, writeFileSync, mkdirSync, readdirSync } from "node:fs";
import { stripTypeScriptTypes } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const srcDir = join(here, "src");
const distDir = join(here, "dist");

mkdirSync(distDir, { recursive: true });

for (const name of readdirSync(srcDir)) {
    if (!name.endsWith(".ts")) continue;
    const src = readFileSync(join(srcDir, name), "utf8");
    // Strip types and rewrite the ".ts" import specifiers to ".mjs".
    let js = stripTypeScriptTypes(src, { mode: "strip" });
    js = js.replace(/(\.\/[A-Za-z0-9_]+)\.ts(["'])/g, "$1.mjs$2");
    const out = name.replace(/\.ts$/, ".mjs");
    writeFileSync(join(distDir, out), js);
}
