import { readFileSync } from "node:fs";

// What this must read, decide and print is set out in /app/docs/rules.md.

// A Row is one row of a position: colour is "b", "r" or "g", or null for an empty row, and n
// is the number of dominoes standing in it.
export type Row = {
  colour: string | null;
  n: number;
};

// A Table holds the settings read from a table file and answers one position line at a time.
// limit is the largest number of dominoes any one row may hold; hasLimit says whether a limit
// was given at all.
export type Table = {
  limit: bigint;
  hasLimit: boolean;
  evalLine(line: string): string | null;
};

const INT64_MAX = 9223372036854775807n;

// firstWord returns the text up to the first space or tab.
function firstWord(s: string): string {
  const k = s.search(/[ \t]/);
  return k >= 0 ? s.slice(0, k) : s;
}

// allDigits reports whether s is a nonempty run of decimal digits.
function allDigits(s: string): boolean {
  if (s.length === 0) {
    return false;
  }
  for (const c of s) {
    if (c < "0" || c > "9") {
      return false;
    }
  }
  return true;
}

// other names the player who is not p.
function other(p: string): string {
  return p === "blue" ? "red" : "blue";
}

// canPush reports whether player p is allowed to push a domino in row r.
function canPush(r: Row, p: string): boolean {
  if (r.n <= 0 || r.colour === null) {
    return false;
  }
  if (r.colour === "g") {
    return true;
  }
  if (r.colour === "b") {
    return p === "blue";
  }
  return p === "red";
}

// load reads the table file and records the row limit. Comments run from the first # to the
// end of a line. A line beginning rowlimit: reads the first word after it: a run of decimal
// digits that fits a signed 64-bit integer sets the limit, and anything else leaves the
// setting where it stood. The last rowlimit: line that sets a value stands, and a file that
// never sets one plays with no limit.
export function load(path: string): Table {
  const data = readFileSync(path, "utf8");
  let limit = 0n;
  let hasLimit = false;

  for (const raw of data.split("\n")) {
    let line = raw;
    const hash = line.indexOf("#");
    if (hash >= 0) {
      line = line.slice(0, hash);
    }
    line = line.trim();
    if (!line.startsWith("rowlimit:")) {
      continue;
    }
    const w = firstWord(line.slice("rowlimit:".length).trim());
    if (allDigits(w)) {
      const v = BigInt(w);
      if (v <= INT64_MAX) {
        limit = v;
        hasLimit = true;
      }
    }
  }

  // evalLine reads one position line and reports the winner. A line with no fields, a line
  // whose first field is not blue or red, and a line carrying a row field that is neither a
  // dot nor a run of b, r and g return null and no output.
  function evalLine(line: string): string | null {
    const fields = line.split(/\s+/).filter((f) => f.length > 0);
    if (fields.length === 0) {
      return null;
    }
    const mover = fields[0].toLowerCase();
    if (mover !== "blue" && mover !== "red") {
      return null;
    }

    const echo: string[] = [mover];
    const rows: Row[] = [];
    let illegal = false;

    for (const f of fields.slice(1)) {
      const w = f.toLowerCase();
      if (w === ".") {
        echo.push(w);
        rows.push({ colour: null, n: 0 });
        continue;
      }
      for (const c of w) {
        if (c !== "b" && c !== "r" && c !== "g") {
          return null;
        }
      }
      echo.push(w);
      let mono = true;
      for (let i = 1; i < w.length; i++) {
        if (w[i] !== w[0]) {
          mono = false;
          break;
        }
      }
      if (!mono) {
        illegal = true;
        rows.push({ colour: null, n: 0 });
        continue;
      }
      if (hasLimit && BigInt(w.length) > limit) {
        illegal = true;
      }
      rows.push({ colour: w[0], n: w.length });
    }

    const head = echo.join(" ") + " | ";
    if (illegal) {
      return head + "ILLEGAL";
    }

    let fold = 0;
    for (const r of rows) {
      fold ^= r.n;
    }
    if (fold === 0) {
      return head + other(mover).toUpperCase();
    }
    for (let i = 0; i < rows.length; i++) {
      const r = rows[i];
      if (!canPush(r, mover)) {
        continue;
      }
      const k = fold ^ r.n;
      if (k < r.n) {
        return head + mover.toUpperCase() + ` topple row ${i + 1} down to ${k}`;
      }
    }
    return head + mover.toUpperCase();
  }

  return { limit, hasLimit, evalLine };
}
