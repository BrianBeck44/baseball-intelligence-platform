import type { PlayerSeasonCaOps } from "./playerSeasonCaOps";

export interface SeasonCaOpsAnalytics {
  season_id: number;
  season_year: number | null;
  players: PlayerSeasonCaOps[];
}
