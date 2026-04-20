export function formatCurrency(value: number): string {
  if (value === undefined || value === null) return "$0.00";
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);
}

export function formatPct(value: number): string {
  if (value === undefined || value === null) return "0.0%";
  return new Intl.NumberFormat('en-US', { style: 'percent', minimumFractionDigits: 1 }).format(value / 100);
}
