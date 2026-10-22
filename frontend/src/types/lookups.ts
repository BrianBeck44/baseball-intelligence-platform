export interface SeasonOption {
  season_id: number;
  season_year: number;
}

export interface SeasonListResponse {
  seasons: SeasonOption[];
}

export interface TeamOption {
  team_id: number;
  name: string;
}

export interface TeamListResponse {
  teams: TeamOption[];
}

export interface PlayerOption {
  player_id: number;
  full_name: string;
}

export interface PlayerListResponse {
  players: PlayerOption[];
}
