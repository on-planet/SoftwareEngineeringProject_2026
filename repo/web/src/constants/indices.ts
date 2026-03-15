export type MarketIndex = {
  symbol: string;
  label: string;
  market: "A" | "HK";
  hasConstituents?: boolean;
};

export const INDEX_OPTIONS: MarketIndex[] = [
  { symbol: "000001.SH", label: "上证指数", market: "A" },
  { symbol: "399001.SZ", label: "深证成指", market: "A" },
  { symbol: "399006.SZ", label: "创业板指", market: "A" },
  { symbol: "000016.SH", label: "上证50", market: "A" },
  { symbol: "000300.SH", label: "沪深300", market: "A" },
  { symbol: "000688.SH", label: "科创50", market: "A" },
  { symbol: "899050.BJ", label: "北证50", market: "A" },
  { symbol: "HKHSI", label: "恒生指数", market: "HK", hasConstituents: true },
  { symbol: "HKHSCEI", label: "国企指数", market: "HK", hasConstituents: true },
  { symbol: "HKHSTECH", label: "恒生科技指数", market: "HK", hasConstituents: true },
];

export const INDEX_NAME_MAP = Object.fromEntries(INDEX_OPTIONS.map((item) => [item.symbol, item.label])) as Record<string, string>;

export const INDEX_CONSTITUENT_OPTIONS = INDEX_OPTIONS.filter((item) => item.hasConstituents);

export function inferIndexMarket(symbol: string): MarketIndex["market"] {
  const upper = symbol.trim().toUpperCase();
  return upper.startsWith("HK") ? "HK" : "A";
}
