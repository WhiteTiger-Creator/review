/*
 * Empirical Mode Decomposition (Huang 1998): sift a signal into Intrinsic
 * Mode Functions (IMFs) plus a residual.
 *
 * Complete `decompose` so that, given one input signal and a maximum IMF
 * count, it returns the list of IMFs and the residual, matching the reference
 * decomposition to a floating-point tolerance.
 *
 * `EmdInput` carries:
 *   - `signal`: the samples of the series, in order
 *   - `maxImf`: the largest number of IMFs to extract; a negative value means
 *     "as many as the decomposition yields".
 *
 * Return an `EmdResult(imfs, residual)` where `imfs` is a list of IMF series
 * (each the same length as `signal`) and `residual` is the trend left over.
 */

export interface EmdInput {
    signal: number[];
    maxImf: number;
}

export interface EmdResult {
    imfs: number[][];
    residual: number[];
}

// The stub returns a single "IMF" equal to the raw signal and a zero
// residual, which is not a correct decomposition.
export function decompose(inp: EmdInput): EmdResult {
    const n = inp.signal.length;
    const signal = new Array<number>(n);
    for (let i = 0; i < n; i++) signal[i] = inp.signal[i];
    const residual = new Array<number>(n).fill(0.0);
    return { imfs: [signal], residual };
}
