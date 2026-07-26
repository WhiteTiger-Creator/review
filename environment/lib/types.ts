export type RawRow = {
  id: string;
  grp: string;
  tier: string;
  mag: number;
  tgt: number | null;
};

export type EncodedVec = { v: number[] };

export type LayoutBlob = {
  tag: string;
  dim: number;
  r0: number;
  r1: number;
  offs: { g: number; t: number; nx: number };
  vocab: { g: string[]; t: string[] };
  scale: number;
  max_l0: number;
  max_n: number;
};

export type FitBundle = {
  layout: LayoutBlob;
  w: number[];
  b: number;
};

export type Caps = { maxL0: number; maxN: number };

export type MutCell = { k: string; a: string | number; b: string | number };

export type CfRow = {
  id: string;
  y0: number;
  y1: number;
  mut: MutCell[];
  l0: number;
  nbytes: number;
  enc_digest: string;
};
