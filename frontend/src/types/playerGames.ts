export interface PlayerGameRecord {
  game_id: number;
  team_id: number;
  game_date: string;
  season_game_number: number;
  plate_appearances: number;
  rolling_14_ops: number | null;
  season_ops: number | null;
  ops_difference: number | null;
}

export interface PlayerGameHistoryResponse {
  player_id: number;
  player_name: string;
  season_id: number;
  games: PlayerGameRecord[];
}
