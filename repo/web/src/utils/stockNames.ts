const STOCK_NAME_CN_MAP: Record<string, string> = {
  "00005.HK": "汇丰控股",
  "00700.HK": "腾讯控股",
  "00939.HK": "建设银行",
  "00941.HK": "中国移动",
  "00981.HK": "中芯国际",
  "01211.HK": "比亚迪股份",
  "01810.HK": "小米集团-W",
  "02318.HK": "中国平安",
  "03690.HK": "美团-W",
  "03888.HK": "金山软件",
  "09618.HK": "京东集团-SW",
  "09626.HK": "哔哩哔哩-W",
  "09888.HK": "百度集团-SW",
  "09988.HK": "阿里巴巴-W",
  "09999.HK": "网易-S",
};

function normalizeStockSymbol(symbol: string): string {
  const upper = symbol.trim().toUpperCase();
  if (upper.endsWith(".HK")) {
    const code = upper.slice(0, -3);
    if (/^\d+$/.test(code)) {
      return `${code.padStart(5, "0")}.HK`;
    }
  }
  return upper;
}

function hasChinese(text?: string | null): boolean {
  return /[\u4e00-\u9fff]/.test(String(text || ""));
}

export function getPrimaryStockName(symbol: string, name?: string | null): string {
  if (hasChinese(name)) {
    return String(name);
  }
  return STOCK_NAME_CN_MAP[normalizeStockSymbol(symbol)] || String(name || symbol);
}

export function getSecondaryStockName(symbol: string, name?: string | null): string | null {
  const primary = getPrimaryStockName(symbol, name);
  const original = String(name || "").trim();
  if (!original || original === primary || original === symbol) {
    return null;
  }
  return original;
}
