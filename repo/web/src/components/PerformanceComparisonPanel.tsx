import React from "react";

import { usePerformanceComparison } from "../hooks/usePerformanceComparison";
import { BoughtTarget } from "../utils/boughtTargets";
import { PerformanceComparisonView } from "./performance/PerformanceComparisonView";

export function PerformanceComparisonPanel({
  watchSymbols,
  boughtTargets,
}: {
  watchSymbols: string[];
  boughtTargets: BoughtTarget[];
}) {
  const model = usePerformanceComparison({ watchSymbols, boughtTargets });

  return <PerformanceComparisonView model={model} />;
}
