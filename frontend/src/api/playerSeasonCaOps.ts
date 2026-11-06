import { getApiBaseUrl } from "./config";
import { ApiError, fetchJson } from "./http";
import type { PlayerSeasonCaOps } from "../types/playerSeasonCaOps";

export class PlayerSeasonCaOpsApiError extends ApiError {
  constructor(status: number, detail: string) {
    super(status, detail);
    this.name = "PlayerSeasonCaOpsApiError";
  }
}

export async function fetchPlayerSeasonCaOps(
  playerId: number,
  seasonId: number,
  signal?: AbortSignal,
): Promise<PlayerSeasonCaOps> {
  const url = new URL(
    `${getApiBaseUrl()}/players/${playerId}/season-ca-ops`,
  );
  url.searchParams.set("season_id", String(seasonId));

  try {
    return await fetchJson<PlayerSeasonCaOps>(url, signal);
  } catch (error) {
    if (error instanceof ApiError) {
      throw new PlayerSeasonCaOpsApiError(error.status, error.detail);
    }
    throw error;
  }
}
