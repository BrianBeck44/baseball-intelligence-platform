export interface PlayerSeasonCaOps {
  player_id: number;
  full_name: string;
  season_id: number;
  season_year: number | null;
  plate_appearances: number | null;
  observed_ops: number | null;
  league_ops: number | null;
  expected_opponent_ops: number | null;
  ca_ops: number | null;
}
