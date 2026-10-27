export interface PlayerSeasonBatting {
  player_id: number;
  full_name: string;
  season_id: number;
  season_year: number | null;
  games: number | null;
  plate_appearances: number | null;
  at_bats: number | null;
  hits: number | null;
  singles: number | null;
  doubles: number | null;
  triples: number | null;
  home_runs: number | null;
  walks: number | null;
  hit_by_pitch: number | null;
  strikeouts: number | null;
  sacrifice_flies: number | null;
  sacrifice_bunts: number | null;
  batting_average: number | null;
  on_base_percentage: number | null;
  slugging_percentage: number | null;
  ops: number | null;
  strikeout_rate: number | null;
  walk_rate: number | null;
}
