import { readFileSync } from "node:fs";

import { load } from "./topple.ts";

// topple takes the path to a table file as its single command-line word, then reads one
// position per line from standard input and prints one line per position it answers. The
// table file gives the longest row this table allows. How a position is read, which player
// wins it under best play and which topple is named are all handled by the topple module
// this calls into.
function main(): void {
  const args = process.argv.slice(2);
  if (args.length !== 1) {
    process.exit(2);
  }

  let table: ReturnType<typeof load> | null = null;
  try {
    table = load(args[0]);
  } catch {
    table = null;
  }
  if (table === null) {
    process.exit(2);
  }

  let data = "";
  try {
    data = readFileSync(0, "utf8");
  } catch {
    data = "";
  }

  const lines = data.split("\n");
  if (lines.length > 0 && lines[lines.length - 1] === "") {
    lines.pop();
  }

  const out: string[] = [];
  for (const line of lines) {
    const res = table.evalLine(line);
    if (res !== null) {
      out.push(res + "\n");
    }
  }
  process.stdout.write(out.join(""));
}

main();
