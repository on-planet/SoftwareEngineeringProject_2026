export const marketTheme = {
  trend: {
    rise: "#d92d20",
    riseSoft: "rgba(217, 45, 32, 0.14)",
    fall: "#039855",
    fallSoft: "rgba(3, 152, 85, 0.14)",
    neutral: "#475467",
    neutralSoft: "rgba(71, 84, 103, 0.12)",
  },
  chart: {
    benchmark: "#155eef",
    worldBank: "#0f766e",
    akshare: "#c2410c",
    grid: "rgba(100, 116, 139, 0.18)",
    axis: "#64748b",
    surface: "#f8fafc",
    warmArea: "rgba(194, 65, 12, 0.18)",
    coolArea: "rgba(15, 118, 110, 0.18)",
    benchmarkArea: "rgba(21, 94, 239, 0.16)",
  },
  surface: {
    page: "#eef2f8",
    card: "#ffffff",
    panel: "linear-gradient(180deg, #ffffff 0%, #f8fbff 100%)",
    warmPanel: "linear-gradient(180deg, #fff7ed 0%, #ffffff 100%)",
    coolPanel: "linear-gradient(180deg, #ecfeff 0%, #ffffff 100%)",
    sticky: "rgba(255, 255, 255, 0.88)",
    empty: "linear-gradient(135deg, rgba(21, 94, 239, 0.06) 0%, rgba(248, 250, 252, 0.96) 100%)",
  },
  skeleton: {
    base: "#e2e8f0",
    shine: "rgba(255, 255, 255, 0.7)",
  },
  shadow: {
    sm: "0 10px 24px rgba(15, 23, 42, 0.06)",
    md: "0 18px 40px rgba(15, 23, 42, 0.08)",
    lg: "0 24px 60px rgba(15, 23, 42, 0.16)",
  },
} as const;
