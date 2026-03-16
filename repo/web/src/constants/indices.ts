export type MarketIndex = {
  symbol: string;
  label: string;
  market: "A" | "HK";
  hasConstituents?: boolean;
};

export const INDEX_OPTIONS: MarketIndex[] = [
  { symbol: "000001.SH", label: "\u4e0a\u8bc1\u6307\u6570", market: "A" },
  { symbol: "399001.SZ", label: "\u6df1\u8bc1\u6210\u6307", market: "A" },
  { symbol: "399006.SZ", label: "\u521b\u4e1a\u677f\u6307", market: "A" },
  { symbol: "000016.SH", label: "\u4e0a\u8bc150", market: "A", hasConstituents: true },
  { symbol: "000300.SH", label: "\u6caa\u6df1300", market: "A", hasConstituents: true },
  { symbol: "000688.SH", label: "\u79d1\u521b50", market: "A", hasConstituents: true },
  { symbol: "899050.BJ", label: "\u5317\u8bc150", market: "A", hasConstituents: true },
  { symbol: "HKHSI", label: "\u6052\u751f\u6307\u6570", market: "HK", hasConstituents: true },
  { symbol: "HKHSCEI", label: "\u56fd\u4f01\u6307\u6570", market: "HK", hasConstituents: true },
  { symbol: "HKHSTECH", label: "\u6052\u751f\u79d1\u6280\u6307\u6570", market: "HK", hasConstituents: true },
];

export const INDEX_NAME_MAP = Object.fromEntries(INDEX_OPTIONS.map((item) => [item.symbol, item.label])) as Record<string, string>;

export const INDEX_CONSTITUENT_OPTIONS = INDEX_OPTIONS.filter((item) => item.hasConstituents);

export function inferIndexMarket(symbol: string): MarketIndex["market"] {
  const upper = symbol.trim().toUpperCase();
  return upper.startsWith("HK") ? "HK" : "A";
}
