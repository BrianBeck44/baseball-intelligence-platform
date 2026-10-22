import { getApiBaseUrl } from "./config";
import { fetchJson } from "./http";
import type {
  PlayerListResponse,
  SeasonListResponse,
  TeamListResponse,
} from "../types/lookups";

export async function fetchSeasons(
  signal?: AbortSignal,
): Promise<SeasonListResponse> {
  const url = new URL(`${getApiBaseUrl()}/seasons`);
  return fetchJson<SeasonListResponse>(url, signal);
}

export async function fetchTeams(
  seasonId: number,
  signal?: AbortSignal,
): Promise<TeamListResponse> {
  const url = new URL(`${getApiBaseUrl()}/teams`);
  url.searchParams.set("season_id", String(seasonId));
  return fetchJson<TeamListResponse>(url, signal);
}

export async function fetchPlayers(
  seasonId: number,
  teamId?: number,
  signal?: AbortSignal,
): Promise<PlayerListResponse> {
  const url = new URL(`${getApiBaseUrl()}/players`);
  url.searchParams.set("season_id", String(seasonId));
  if (teamId !== undefined) {
    url.searchParams.set("team_id", String(teamId));
  }
  return fetchJson<PlayerListResponse>(url, signal);
}
