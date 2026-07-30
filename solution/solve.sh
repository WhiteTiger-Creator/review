#!/bin/bash
set -euo pipefail

cat > /app/src/topple.ts << 'EOF'
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

// A Standing is a position boiled down to what settling it needs: the two stores, the lengths
// of the grey rows longest first, which sorted place each row of the position holds among
// them, and running sums of what the grey rows pour into the player taking them at an even
// place (p0) and at an odd place (p1).
type Standing = {
  blue: number;
  red: number;
  greys: number[];
  place: number[];
  p0: number[];
  p1: number[];
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

// settle names the winner of a position that has come down to a store of blue dominoes, a
// store of red dominoes and greys rows still to be claimed, where mover is to move and the
// claiming brings first more dominoes to the mover and second more to the other player.
//
// A row of one player's colour is a row only that player can push in, and pushing in it
// leaves a shorter row of the same colour, so the whole run of a coloured row is a store of
// turns that player can spend one at a time and the other player can never touch or hurry.
// Whichever player holds the larger store outlasts the other, whoever started; on equal
// stores the player who has to move runs out first. Grey rows do not sit apart from that
// count, because claiming a grey row of g dominoes leaves up to g-1 of them standing in the
// claimer's own colour and so pours that many turns into the claimer's own store while
// putting the row for ever out of the other player's reach. So the grey rows are shared out a
// row at a time, turn about, the player to move taking the row that pours the most, and every
// grey row spends one turn, so the player left to move once the grey is gone is the starter
// only when the number of grey rows is even.
function settle(
  blue: number,
  red: number,
  first: number,
  second: number,
  greys: number,
  mover: string,
): string {
  let b = blue;
  let r = red;
  if (mover === "blue") {
    b += first;
    r += second;
  } else {
    r += first;
    b += second;
  }
  let last = mover;
  if (greys % 2 === 1) {
    last = other(mover);
  }
  if (b > r) {
    return "blue";
  }
  if (r > b) {
    return "red";
  }
  return other(last);
}

function newStanding(rows: Row[]): Standing {
  const place: number[] = new Array(rows.length).fill(-1);
  let blue = 0;
  let red = 0;
  const idx: number[] = [];
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    if (r.colour === "b") {
      blue += r.n;
    } else if (r.colour === "r") {
      red += r.n;
    } else if (r.colour === "g") {
      idx.push(i);
    }
  }
  idx.sort((a, b) => rows[b].n - rows[a].n);
  const greys: number[] = new Array(idx.length);
  for (let j = 0; j < idx.length; j++) {
    greys[j] = rows[idx[j]].n;
    place[idx[j]] = j;
  }
  const m = greys.length;
  const p0: number[] = new Array(m + 1).fill(0);
  const p1: number[] = new Array(m + 1).fill(0);
  for (let j = 0; j < m; j++) {
    p0[j + 1] = p0[j];
    p1[j + 1] = p1[j];
    if (j % 2 === 0) {
      p0[j + 1] += greys[j] - 1;
    } else {
      p1[j + 1] += greys[j] - 1;
    }
  }
  return { blue, red, greys, place, p0, p1 };
}

// winnerOf names the player who wins the whole position with mover to move.
function winnerOf(s: Standing, mover: string): string {
  const m = s.greys.length;
  return settle(s.blue, s.red, s.p0[m], s.p1[m], m, mover);
}

// afterKeeping names the winner once the mover has toppled in one of their own rows, leaving
// it lost dominoes shorter, with the grey rows untouched.
function afterKeeping(s: Standing, lost: number, mover: string): string {
  let blue = s.blue;
  let red = s.red;
  if (mover === "blue") {
    blue -= lost;
  } else {
    red -= lost;
  }
  const m = s.greys.length;
  return settle(blue, red, s.p0[m], s.p1[m], m, other(mover));
}

// afterClaiming names the winner once the mover has toppled in the grey row holding sorted
// place j and left keep dominoes standing there, which are now the mover's own.
function afterClaiming(s: Standing, j: number, keep: number, mover: string): string {
  let blue = s.blue;
  let red = s.red;
  if (mover === "blue") {
    blue += keep;
  } else {
    red += keep;
  }
  const m = s.greys.length;
  const first = s.p0[j] + (s.p1[m] - s.p1[j + 1]);
  const second = s.p1[j] + (s.p0[m] - s.p0[j + 1]);
  return settle(blue, red, first, second, m - 1, other(mover));
}

// winningTopple names one topple for the player to move that leaves the other player, now to
// move, a losing position. The position handed in is a win for the mover, so such a topple
// exists. Rows are tried in the order they stand and each row at every length it may be left
// at.
function winningTopple(s: Standing, rows: Row[], mover: string): string {
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    if (!canPush(r, mover)) {
      continue;
    }
    if (r.colour === "g") {
      const j = s.place[i];
      for (let k = 0; k < r.n; k++) {
        if (afterClaiming(s, j, k, mover) === mover) {
          return `topple row ${i + 1} down to ${k}`;
        }
      }
      continue;
    }
    for (let k = 0; k < r.n; k++) {
      if (afterKeeping(s, r.n - k, mover) === mover) {
        return `topple row ${i + 1} down to ${k}`;
      }
    }
  }
  return "";
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

    const s = newStanding(rows);
    const w = winnerOf(s, mover);
    if (w !== mover) {
      return head + w.toUpperCase();
    }
    return head + w.toUpperCase() + " " + winningTopple(s, rows, mover);
  }

  return { limit, hasLimit, evalLine };
}
EOF

node --experimental-strip-types --check /app/src/topple.ts
node --experimental-strip-types --check /app/src/main.ts

# Play a few positions and confirm the close ones now come out right. One red domino beside a
# grey row of two is Blue's with Blue to move, a lone grey domino rescues nobody, and two grey
# rows of a length leave the player to move without a turn to spare.
cfg=$(mktemp)
printf '# no limit\n' > "$cfg"
got=$(printf 'blue r gg\nblue r g\nblue gg gg\nblue rr\n' | node --experimental-strip-types /app/src/main.ts "$cfg")
want='blue r gg | BLUE topple row 2 down to 1
blue r g | RED
blue gg gg | RED
blue rr | RED'
rm -f "$cfg"
if [ "$got" != "$want" ]; then
  echo "topple did not answer the sample positions as expected" >&2
  echo "got:"; echo "$got"
  echo "want:"; echo "$want"
  exit 1
fi
echo "topple answered the sample positions correctly"
