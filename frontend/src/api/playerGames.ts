import { getApiBaseUrl } from "./config";
import { ApiError, fetchJson } from "./http";
import type { PlayerGameHistoryResponse } from "../types/playerGames";

export class PlayerGamesApiError extends ApiError {
  constructor(status: number, detail: string) {
    super(status, detail);
    this.name = "PlayerGamesApiError";
  }
}

export async function fetchPlayerGames(
  playerId: number,
  seasonId: number,
  limit = 50,
  signal?: AbortSignal,
): Promise<PlayerGameHistoryResponse> {
  const url = new URL(
    `${getApiBaseUrl()}/players/${playerId}/games`,
  );
  url.searchParams.set("season_id", String(seasonId));
  url.searchParams.set("limit", String(limit));

  try {
    return await fetchJson<PlayerGameHistoryResponse>(url, signal);
  } catch (error) {
    if (error instanceof ApiError) {
      throw new PlayerGamesApiError(error.status, error.detail);
    }
    throw error;
  }
}
