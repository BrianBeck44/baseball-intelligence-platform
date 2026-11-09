import { getApiBaseUrl } from "./config";
import { ApiError, fetchJson } from "./http";
import type { SeasonCaOpsAnalytics } from "../types/playerSeasonCaOpsAnalytics";

export class SeasonCaOpsAnalyticsApiError extends ApiError {
  constructor(status: number, detail: string) {
    super(status, detail);
    this.name = "SeasonCaOpsAnalyticsApiError";
  }
}

export async function fetchSeasonCaOpsAnalytics(
  seasonId: number,
  signal?: AbortSignal,
): Promise<SeasonCaOpsAnalytics> {
  const url = new URL(`${getApiBaseUrl()}/analytics/season-ca-ops`);
  url.searchParams.set("season_id", String(seasonId));

  try {
    return await fetchJson<SeasonCaOpsAnalytics>(url, signal);
  } catch (error) {
    if (error instanceof ApiError) {
      throw new SeasonCaOpsAnalyticsApiError(error.status, error.detail);
    }
    throw error;
  }
}
