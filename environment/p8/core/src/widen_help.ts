export function to_hex16(n: bigint): string {
  return (n & 0xffffffffffffffffn).toString(16).padStart(16, "0");
}

export function to_hex8(n: number): string {
  return (n >>> 0).toString(16).padStart(8, "0");
}
