export const PREFERRED_FUTURES_SYMBOLS = ["CU", "AU", "AG", "AO", "SC", "FU"] as const;

export const FUTURES_LABELS: Record<string, string> = {
  CU: "铜",
  AU: "黄金",
  AG: "白银",
  AO: "氧化铝",
  SC: "原油",
  FU: "燃料油",
};

const SYMBOL_ORDER = new Map<string, number>(
  PREFERRED_FUTURES_SYMBOLS.map((symbol, index) => [symbol, index])
);

export function sortPreferredFutures<T extends { symbol: string }>(items: T[]): T[] {
  return [...items].sort((a, b) => {
    const aOrder = SYMBOL_ORDER.get(a.symbol) ?? Number.MAX_SAFE_INTEGER;
    const bOrder = SYMBOL_ORDER.get(b.symbol) ?? Number.MAX_SAFE_INTEGER;
    if (aOrder !== bOrder) {
      return aOrder - bOrder;
    }
    return a.symbol.localeCompare(b.symbol);
  });
}

export function formatContractMonth(value?: string | null) {
  const text = `${value ?? ""}`.trim();
  if (!/^\d{4}$/.test(text)) {
    return "--";
  }
  return `20${text.slice(0, 2)}-${text.slice(2)}`;
}
