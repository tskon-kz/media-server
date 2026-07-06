export function bytes(n: number): string {
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(1)} GB`;
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(0)} MB`;
  if (n >= 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${n} B`;
}

export function speed(bytesPerSec: number): string {
  return `${bytes(bytesPerSec)}/s`;
}

export function pct(progress: number): string {
  return `${Math.round(progress * 100)}%`;
}
