export const PREFERRED_FUTURES_SYMBOLS = [
  "CU",
  "AL",
  "ZN",
  "AU",
  "AG",
  "AO",
  "RB",
  "HC",
  "SC",
  "FU",
  "BU",
  "RU",
  "I",
  "M",
  "Y",
  "CF",
  "SR",
  "TA",
  "MA",
  "IF",
  "IH",
  "IC",
  "IM",
  "T",
  "TF",
  "TS",
  "TL",
] as const;

export const FUTURES_LABELS: Record<string, string> = {
  CU: "铜",
  AU: "黄金",
  AG: "白银",
  AO: "氧化铝",
  SC: "原油",
  FU: "燃料油",
};

Object.assign(FUTURES_LABELS, {
  AL: "沪铝",
  ZN: "沪锌",
  PB: "沪铅",
  NI: "沪镍",
  SN: "沪锡",
  RB: "螺纹钢",
  HC: "热卷",
  SS: "不锈钢",
  RU: "橡胶",
  BR: "丁二烯橡胶",
  BU: "沥青",
  SP: "纸浆",
  LU: "低硫燃油",
  NR: "20号胶",
  BC: "国际铜",
  M: "豆粕",
  Y: "豆油",
  A: "豆一",
  B: "豆二",
  C: "玉米",
  CS: "玉米淀粉",
  P: "棕榈油",
  I: "铁矿石",
  J: "焦炭",
  JM: "焦煤",
  L: "塑料",
  PP: "聚丙烯",
  V: "PVC",
  EG: "乙二醇",
  EB: "苯乙烯",
  PG: "液化石油气",
  LH: "生猪",
  CF: "棉花",
  SR: "白糖",
  TA: "PTA",
  MA: "甲醇",
  OI: "菜油",
  RM: "菜粕",
  FG: "玻璃",
  SA: "纯碱",
  PF: "短纤",
  AP: "苹果",
  CJ: "红枣",
  PK: "花生",
  UR: "尿素",
  SM: "锰硅",
  SF: "硅铁",
  IF: "沪深300期指",
  IH: "上证50期指",
  IC: "中证500期指",
  IM: "中证1000期指",
  T: "10年国债",
  TF: "5年国债",
  TS: "2年国债",
  TL: "30年国债",
});

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

export const FUTURES_CATEGORIES = ["全部", "金属", "能源化工", "黑色建材", "农产品", "金融"] as const;

const CATEGORY_MAP: Record<string, string> = {
  CU: "金属", AL: "金属", ZN: "金属", PB: "金属", NI: "金属", SN: "金属", AU: "金属", AG: "金属", AO: "金属", SS: "金属", BC: "金属",
  SC: "能源化工", FU: "能源化工", LU: "能源化工", BU: "能源化工", RU: "能源化工", BR: "能源化工", NR: "能源化工", L: "能源化工", PP: "能源化工", V: "能源化工", EG: "能源化工", EB: "能源化工", PG: "能源化工", TA: "能源化工", MA: "能源化工", PF: "能源化工", FG: "能源化工", SA: "能源化工",
  RB: "黑色建材", HC: "黑色建材", I: "黑色建材", J: "黑色建材", JM: "黑色建材", SP: "黑色建材",
  M: "农产品", Y: "农产品", A: "农产品", B: "农产品", C: "农产品", CS: "农产品", P: "农产品", CF: "农产品", SR: "农产品", OI: "农产品", RM: "农产品", LH: "农产品", AP: "农产品", CJ: "农产品", PK: "农产品", UR: "农产品", SM: "农产品", SF: "农产品",
  IF: "金融", IH: "金融", IC: "金融", IM: "金融", T: "金融", TF: "金融", TS: "金融", TL: "金融",
};

export function getFuturesCategory(symbol: string): string {
  return CATEGORY_MAP[symbol] || "其他";
}

export function formatContractMonth(value?: string | null) {
  const text = `${value ?? ""}`.trim();
  if (!/^\d{4}$/.test(text)) {
    return "--";
  }
  return `20${text.slice(0, 2)}-${text.slice(2)}`;
}
