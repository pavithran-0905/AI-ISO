const usdFormatter = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 4 });
const percentFormatter = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 });

export function formatUsd(value: number): string {
  return usdFormatter.format(value);
}

export function formatPercent(fraction: number): string {
  return percentFormatter.format(fraction);
}
