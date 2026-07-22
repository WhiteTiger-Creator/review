/*
 * Standard-input / standard-output framing for the EMD sifting service.
 *
 * Reads one JSON object {"inputs": [ <input>, ... ]} from standard input and
 * writes one JSON object {"results": [ {"imfs": [[...],...], "residual": [...]}, ... ]}
 * to standard output, one result per input in the same order. Each input
 * carries the samples "signal" (in order) and an integer "max_imf" capping the
 * IMF count, where a negative value means "as many as the decomposition
 * yields". This wiring is complete; the work is in emd.ts.
 */

import { readFileSync } from "node:fs";
import { decompose } from "./emd.ts";
import type { EmdInput } from "./emd.ts";

class Json {
    s: string;
    i: number;
    constructor(s: string) {
        this.s = s;
        this.i = 0;
    }
    ws(): void {
        while (this.i < this.s.length && /\s/.test(this.s[this.i])) this.i++;
    }
    value(): unknown {
        this.ws();
        switch (this.s[this.i]) {
            case "{":
                return this.obj();
            case "[":
                return this.arr();
            case '"':
                return this.str();
            case "t":
                this.i += 4;
                return true;
            case "f":
                this.i += 5;
                return false;
            case "n":
                this.i += 4;
                return null;
            default:
                return this.num();
        }
    }
    obj(): Map<string, unknown> {
        const m = new Map<string, unknown>();
        this.i++;
        this.ws();
        if (this.s[this.i] === "}") {
            this.i++;
            return m;
        }
        while (true) {
            this.ws();
            const k = this.str();
            this.ws();
            this.i++;
            m.set(k, this.value());
            this.ws();
            if (this.s[this.i] === ",") {
                this.i++;
                continue;
            }
            if (this.s[this.i] === "}") {
                this.i++;
                break;
            }
        }
        return m;
    }
    arr(): unknown[] {
        const a: unknown[] = [];
        this.i++;
        this.ws();
        if (this.s[this.i] === "]") {
            this.i++;
            return a;
        }
        while (true) {
            a.push(this.value());
            this.ws();
            if (this.s[this.i] === ",") {
                this.i++;
                continue;
            }
            if (this.s[this.i] === "]") {
                this.i++;
                break;
            }
        }
        return a;
    }
    str(): string {
        let sb = "";
        this.i++;
        while (this.s[this.i] !== '"') {
            if (this.s[this.i] === "\\") {
                this.i++;
                switch (this.s[this.i]) {
                    case "n":
                        sb += "\n";
                        break;
                    case "t":
                        sb += "\t";
                        break;
                    case "r":
                        sb += "\r";
                        break;
                    case '"':
                        sb += '"';
                        break;
                    case "\\":
                        sb += "\\";
                        break;
                    case "/":
                        sb += "/";
                        break;
                    default:
                        sb += this.s[this.i];
                }
            } else {
                sb += this.s[this.i];
            }
            this.i++;
        }
        this.i++;
        return sb;
    }
    num(): number {
        const start = this.i;
        if (this.s[this.i] === "-" || this.s[this.i] === "+") this.i++;
        while (this.i < this.s.length) {
            const c = this.s[this.i];
            if (
                (c >= "0" && c <= "9") ||
                c === "." ||
                c === "e" ||
                c === "E" ||
                c === "+" ||
                c === "-"
            ) {
                this.i++;
            } else {
                break;
            }
        }
        return parseFloat(this.s.substring(start, this.i));
    }
}

function asObj(v: unknown): Map<string, unknown> {
    return v as Map<string, unknown>;
}

function toInput(m: Map<string, unknown>): EmdInput {
    const signal = (m.get("signal") as unknown[]).map((x) => x as number);
    const maxImf = Math.trunc(m.get("max_imf") as number);
    return { signal, maxImf };
}

function fmt(v: number): string {
    if (Number.isNaN(v)) return "0";
    // Match Kotlin Double.toString(): shortest round-tripping decimal with a
    // decimal point for integral values.
    let s = String(v);
    if (
        !s.includes(".") &&
        !s.includes("e") &&
        !s.includes("E") &&
        !s.includes("Inf") &&
        !s.includes("NaN")
    ) {
        s += ".0";
    }
    return s;
}

function appendSeries(parts: string[], xs: number[]): void {
    let s = "[";
    for (let j = 0; j < xs.length; j++) {
        if (j > 0) s += ",";
        s += fmt(xs[j]);
    }
    s += "]";
    parts.push(s);
}

function readStdin(): string {
    return readFileSync(0, "utf8");
}

function main(): void {
    const input = readStdin();
    const root = asObj(new Json(input).value());
    const inputs = (root.get("inputs") as unknown[]).map((v) =>
        toInput(asObj(v)),
    );
    let sb = '{"results":[';
    inputs.forEach((inp, idx) => {
        if (idx > 0) sb += ",";
        const res = decompose(inp);
        let inner = '{"imfs":[';
        res.imfs.forEach((imf, k) => {
            if (k > 0) inner += ",";
            const parts: string[] = [];
            appendSeries(parts, imf);
            inner += parts[0];
        });
        inner += "],\"residual\":";
        const rparts: string[] = [];
        appendSeries(rparts, res.residual);
        inner += rparts[0];
        inner += "}";
        sb += inner;
    });
    sb += "]}";
    process.stdout.write(sb + "\n");
}

main();
