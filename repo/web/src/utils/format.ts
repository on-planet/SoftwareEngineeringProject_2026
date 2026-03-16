export function formatNumber(value: number) {
  return new Intl.NumberFormat("zh-CN").format(value);
}

export function formatPercent(value: number, digits = 2) {
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatSigned(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}`;
}

export function formatNullableNumber(value?: number | null, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return Number(value).toFixed(digits);
}

export function normalizePercentRatio(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return null;
  }
  return Math.abs(value) > 1 ? value / 100 : value;
}

export function formatLoosePercent(value?: number | null, digits = 2) {
  const normalized = normalizePercentRatio(value);
  if (normalized === null) {
    return "--";
  }
  return formatPercent(normalized, digits);
}

export const formatSmartPercent = formatLoosePercent;
