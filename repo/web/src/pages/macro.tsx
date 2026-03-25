import React from "react";

import { MacroDashboardView } from "../components/macro/MacroDashboardView";
import { useMacroDashboard } from "../hooks/useMacroDashboard";

export default function MacroPage() {
  const model = useMacroDashboard();

  return <MacroDashboardView model={model} />;
}
