import { getApiBaseUrl } from "./config";
import { ApiError, fetchJson } from "./http";
import type { PlayerSeasonBatting } from "../types/playerSeasonBatting";

export class PlayerSeasonBattingApiError extends ApiError {
  constructor(status: number, detail: string) {
    super(status, detail);
    this.name = "PlayerSeasonBattingApiError";
  }
}

export async function fetchPlayerSeasonBatting(
  playerId: number,
  seasonId: number,
  signal?: AbortSignal,
): Promise<PlayerSeasonBatting> {
  const url = new URL(
    `${getApiBaseUrl()}/players/${playerId}/season-batting`,
  );
  url.searchParams.set("season_id", String(seasonId));

  try {
    return await fetchJson<PlayerSeasonBatting>(url, signal);
  } catch (error) {
    if (error instanceof ApiError) {
      throw new PlayerSeasonBattingApiError(error.status, error.detail);
    }
    throw error;
  }
}
