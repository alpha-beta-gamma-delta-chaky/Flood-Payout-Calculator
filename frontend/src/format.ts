export function usd(n: number): string {
  return "$" + Math.round(n).toLocaleString("en-US");
}

export function percent(p: number): string {
  if (p > 0 && p < 0.005) return "<1%";
  return `${Math.round(p * 100)}%`;
}
