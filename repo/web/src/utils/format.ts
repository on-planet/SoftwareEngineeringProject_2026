export function formatNumber(value: number) {
  return new Intl.NumberFormat("zh-CN").format(value);
}

export function formatPercent(value: number) {
  return `${(value * 100).toFixed(2)}%`;
}

export function formatSigned(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}`;
}
