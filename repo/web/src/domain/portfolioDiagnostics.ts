import {
  ApiQueryOptions,
  PortfolioDiagnosticsResponse,
  getMyBoughtTargetDiagnostics,
  getMyWatchTargetDiagnostics,
} from "../services/api";

export type PortfolioTargetScope = "watch" | "bought";

function hashIdentity(value: string) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) | 0;
  }
  return Math.abs(hash).toString(36);
}


export function buildPortfolioDiagnosticsQueryKey(
  token: string,
  targetType: PortfolioTargetScope = "bought",
) {
  return `user:portfolio-diagnostics:${targetType}:${hashIdentity(token)}`;
}


export function getPortfolioDiagnosticsQueryOptions(
  targetType: PortfolioTargetScope = "bought",
): ApiQueryOptions {
  return {
    staleTimeMs: 60_000,
    cacheTimeMs: 5 * 60_000,
    retry: 1,
    label: `${targetType}-portfolio-diagnostics`,
  };
}


export async function loadPortfolioDiagnostics(
  token: string,
  targetType: PortfolioTargetScope = "bought",
): Promise<PortfolioDiagnosticsResponse> {
  return targetType === "watch" ? getMyWatchTargetDiagnostics(token) : getMyBoughtTargetDiagnostics(token);
}
