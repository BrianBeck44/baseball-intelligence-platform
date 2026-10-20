import { getApiBaseUrl } from "./config";
import type { PlayerGameHistoryResponse } from "../types/playerGames";

export class PlayerGamesApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "PlayerGamesApiError";
    this.status = status;
    this.detail = detail;
  }
}

function readErrorDetail(payload: unknown): string | null {
  if (
    payload !== null &&
    typeof payload === "object" &&
    "detail" in payload &&
    typeof payload.detail === "string"
  ) {
    return payload.detail;
  }
  return null;
}

export async function fetchPlayerGames(
  playerId: number,
  seasonId: number,
  limit = 50,
): Promise<PlayerGameHistoryResponse> {
  const url = new URL(
    `${getApiBaseUrl()}/players/${playerId}/games`,
  );
  url.searchParams.set("season_id", String(seasonId));
  url.searchParams.set("limit", String(limit));

  const response = await fetch(url);

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}.`;
    try {
      const payload: unknown = await response.json();
      detail = readErrorDetail(payload) ?? detail;
    } catch {
      // Keep the status fallback when the body is not JSON.
    }
    throw new PlayerGamesApiError(response.status, detail);
  }

  return (await response.json()) as PlayerGameHistoryResponse;
}
