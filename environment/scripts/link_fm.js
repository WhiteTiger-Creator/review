const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const srcMain = path.join(root, "dist", "m3", "k72", "src", "main.js");
const distDir = path.join(root, "m3", "k72", "dist");
fs.mkdirSync(distDir, { recursive: true });
const wrapper = `#!/usr/bin/env node
require(${JSON.stringify(srcMain)});
`;
const out = path.join(distDir, "fm");
fs.writeFileSync(out, wrapper, { mode: 0o755 });
console.log("linked", out);
