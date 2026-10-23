import { FormEvent, useEffect, useState } from "react";

import { fetchPlayers, fetchSeasons, fetchTeams } from "../api/lookups";
import { fetchPlayerGames, PlayerGamesApiError } from "../api/playerGames";
import { ApiError, isAbortError } from "../api/http";
import type {
  PlayerOption,
  SeasonOption,
  TeamOption,
} from "../types/lookups";
import type { PlayerGameHistoryResponse } from "../types/playerGames";
import { PerformanceOverTimeChart } from "./PerformanceOverTimeChart";
import { SearchableSelect } from "./SearchableSelect";
import { ThemeToggle } from "./ThemeToggle";

const ALL_TEAMS = "all";

function formatOps(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return value.toFixed(3);
}

function formatOpsDifference(value: number | null): string {
  if (value === null) {
    return "—";
  }
  const formatted = value.toFixed(3);
  return value > 0 ? `+${formatted}` : formatted;
}

function lookupErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.detail;
  }
  return fallback;
}

export function PlayerGameHistoryPage() {
  const [seasons, setSeasons] = useState<SeasonOption[]>([]);
  const [teams, setTeams] = useState<TeamOption[]>([]);
  const [players, setPlayers] = useState<PlayerOption[]>([]);

  const [seasonId, setSeasonId] = useState("");
  const [teamSelection, setTeamSelection] = useState("");
  const [playerId, setPlayerId] = useState("");
  const [playerQuery, setPlayerQuery] = useState("");

  const [seasonsLoading, setSeasonsLoading] = useState(true);
  const [teamsLoading, setTeamsLoading] = useState(false);
  const [playersLoading, setPlayersLoading] = useState(false);
  const [optionsError, setOptionsError] = useState<string | null>(null);

  const [history, setHistory] = useState<PlayerGameHistoryResponse | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedSeason = seasons.find(
    (season) => String(season.season_id) === seasonId,
  );
  const canRequestHistory =
    seasonId !== "" && teamSelection !== "" && playerId !== "";

  useEffect(() => {
    const controller = new AbortController();
    setSeasonsLoading(true);
    setOptionsError(null);

    fetchSeasons(controller.signal)
      .then((result) => {
        setSeasons(result.seasons);
      })
      .catch((requestError) => {
        if (isAbortError(requestError)) {
          return;
        }
        setSeasons([]);
        setOptionsError(
          lookupErrorMessage(requestError, "Unable to load seasons."),
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setSeasonsLoading(false);
        }
      });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (seasonId === "") {
      setTeams([]);
      setTeamsLoading(false);
      return;
    }

    const controller = new AbortController();
    setTeamsLoading(true);
    setOptionsError(null);

    fetchTeams(Number(seasonId), controller.signal)
      .then((result) => {
        setTeams(result.teams);
      })
      .catch((requestError) => {
        if (isAbortError(requestError)) {
          return;
        }
        setTeams([]);
        setOptionsError(
          lookupErrorMessage(requestError, "Unable to load teams."),
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setTeamsLoading(false);
        }
      });

    return () => controller.abort();
  }, [seasonId]);

  useEffect(() => {
    if (seasonId === "" || teamSelection === "") {
      setPlayers([]);
      setPlayersLoading(false);
      return;
    }

    const controller = new AbortController();
    const teamId =
      teamSelection === ALL_TEAMS ? undefined : Number(teamSelection);
    setPlayersLoading(true);
    setOptionsError(null);

    fetchPlayers(Number(seasonId), teamId, controller.signal)
      .then((result) => {
        setPlayers(result.players);
      })
      .catch((requestError) => {
        if (isAbortError(requestError)) {
          return;
        }
        setPlayers([]);
        setOptionsError(
          lookupErrorMessage(requestError, "Unable to load players."),
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setPlayersLoading(false);
        }
      });

    return () => controller.abort();
  }, [seasonId, teamSelection]);

  function handleSeasonChange(nextSeasonId: string) {
    setSeasonId(nextSeasonId);
    setTeamSelection("");
    setPlayerId("");
    setPlayerQuery("");
    setTeams([]);
    setPlayers([]);
    setTeamsLoading(nextSeasonId !== "");
    setPlayersLoading(false);
    setHistory(null);
    setError(null);
  }

  function handleTeamChange(nextTeamSelection: string) {
    setTeamSelection(nextTeamSelection);
    setPlayerId("");
    setPlayerQuery("");
    setPlayers([]);
    setPlayersLoading(nextTeamSelection !== "");
    setHistory(null);
    setError(null);
  }

  function handlePlayerChange(nextPlayerId: string) {
    setPlayerId(nextPlayerId);
    setHistory(null);
    setError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!canRequestHistory) {
      setHistory(null);
      setError("Select a season, team, and player.");
      return;
    }

    setIsLoading(true);
    try {
      const result = await fetchPlayerGames(
        Number(playerId),
        Number(seasonId),
        200,
      );
      setHistory(result);
    } catch (requestError) {
      setHistory(null);
      if (requestError instanceof PlayerGamesApiError) {
        setError(requestError.detail);
      } else {
        setError("Unable to load player game history.");
      }
    } finally {
      setIsLoading(false);
    }
  }

  const seasonYearLabel = selectedSeason
    ? String(selectedSeason.season_year)
    : history
      ? String(history.season_id)
      : "";

  return (
    <main className="page">
      <header className="page-header">
        <div className="page-header-copy">
          <h1>Player Game History</h1>
          <p>
            Choose a season, team, and player to load game-by-game batting
            history from the Baseball Intelligence API.
          </p>
        </div>
        <ThemeToggle />
      </header>

      <form className="history-form" onSubmit={handleSubmit}>
        <label htmlFor="seasonId">
          Season
          <select
            id="seasonId"
            name="seasonId"
            value={seasonId}
            onChange={(event) => handleSeasonChange(event.target.value)}
            disabled={seasonsLoading || seasons.length === 0}
            required
          >
            <option value="">
              {seasonsLoading ? "Loading seasons…" : "Select a season"}
            </option>
            {seasons.map((season) => (
              <option key={season.season_id} value={season.season_id}>
                {season.season_year}
              </option>
            ))}
          </select>
        </label>

        <label htmlFor="teamSelection">
          Team
          <select
            id="teamSelection"
            name="teamSelection"
            value={teamSelection}
            onChange={(event) => handleTeamChange(event.target.value)}
            disabled={seasonId === "" || teamsLoading}
            required
          >
            <option value="">
              {teamsLoading ? "Loading teams…" : "Select a team"}
            </option>
            <option value={ALL_TEAMS}>Search All Teams</option>
            {teams.map((team) => (
              <option key={team.team_id} value={team.team_id}>
                {team.name}
              </option>
            ))}
          </select>
        </label>

        <SearchableSelect
          id="playerId"
          label="Player"
          value={playerId}
          options={players.map((player) => ({
            value: String(player.player_id),
            label: player.full_name,
          }))}
          disabled={teamSelection === "" || playersLoading}
          required
          searchValue={playerQuery}
          onSearchChange={setPlayerQuery}
          onChange={handlePlayerChange}
          placeholder={
            playersLoading ? "Loading players…" : "Select a player"
          }
          searchPlaceholder="Search players by name"
          emptyMessage="No players match that search."
        />

        <button
          type="submit"
          disabled={isLoading || !canRequestHistory}
        >
          {isLoading ? "Loading…" : "Load history"}
        </button>
      </form>

      {seasonsLoading ? <p className="status">Loading seasons…</p> : null}
      {!seasonsLoading && seasons.length === 0 && !optionsError ? (
        <p className="status">No seasons with batting history are available.</p>
      ) : null}
      {seasonId !== "" && !teamsLoading && teams.length === 0 && !optionsError ? (
        <p className="status">No teams have batting history in that season.</p>
      ) : null}
      {teamSelection !== "" &&
      !playersLoading &&
      players.length === 0 &&
      !optionsError ? (
        <p className="status">
          No players have batting history for that selection.
        </p>
      ) : null}
      {optionsError ? <p className="status error">{optionsError}</p> : null}
      {isLoading ? <p className="status">Loading player history…</p> : null}
      {error ? <p className="status error">{error}</p> : null}

      {history && history.games.length === 0 ? (
        <p className="status">
          No game history for {history.player_name} in {seasonYearLabel}.
        </p>
      ) : null}

      {history && history.games.length > 0 ? (
        <section className="results">
          <h2>
            {history.player_name}{" "}
            <span className="meta">Season {seasonYearLabel}</span>
          </h2>
          <PerformanceOverTimeChart games={history.games} />
          <table>
            <thead>
              <tr>
                <th>Game date</th>
                <th>Season game</th>
                <th>Team ID</th>
                <th>PA</th>
                <th>Rolling 14 OPS</th>
                <th>Season OPS</th>
                <th>OPS diff</th>
              </tr>
            </thead>
            <tbody>
              {history.games.map((game) => (
                <tr key={`${game.game_id}-${game.team_id}`}>
                  <td>{game.game_date}</td>
                  <td>{game.season_game_number}</td>
                  <td>{game.team_id}</td>
                  <td>{game.plate_appearances}</td>
                  <td>{formatOps(game.rolling_14_ops)}</td>
                  <td>{formatOps(game.season_ops)}</td>
                  <td>{formatOpsDifference(game.ops_difference)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
    </main>
  );
}
