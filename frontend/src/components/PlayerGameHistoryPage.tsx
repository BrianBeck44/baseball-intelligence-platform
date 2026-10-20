import { FormEvent, useState } from "react";

import { fetchPlayerGames, PlayerGamesApiError } from "../api/playerGames";
import type { PlayerGameHistoryResponse } from "../types/playerGames";

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

function parsePositiveInteger(value: string, label: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1) {
    throw new Error(`${label} must be a positive integer.`);
  }
  return parsed;
}

export function PlayerGameHistoryPage() {
  const [playerId, setPlayerId] = useState("");
  const [seasonId, setSeasonId] = useState("");
  const [history, setHistory] = useState<PlayerGameHistoryResponse | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    let parsedPlayerId: number;
    let parsedSeasonId: number;
    try {
      parsedPlayerId = parsePositiveInteger(playerId, "Player ID");
      parsedSeasonId = parsePositiveInteger(seasonId, "Season ID");
    } catch (validationError) {
      setHistory(null);
      setError(
        validationError instanceof Error
          ? validationError.message
          : "Enter a valid player ID and season ID.",
      );
      return;
    }

    setIsLoading(true);
    try {
      const result = await fetchPlayerGames(parsedPlayerId, parsedSeasonId);
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

  return (
    <main className="page">
      <header className="page-header">
        <h1>Player Game History</h1>
        <p>
          Load a player's game-by-game batting history for one season from the
          Baseball Intelligence API.
        </p>
      </header>

      <form className="history-form" onSubmit={handleSubmit}>
        <label>
          Player ID
          <input
            type="number"
            min={1}
            step={1}
            name="playerId"
            value={playerId}
            onChange={(event) => setPlayerId(event.target.value)}
            required
          />
        </label>
        <label>
          Season ID
          <input
            type="number"
            min={1}
            step={1}
            name="seasonId"
            value={seasonId}
            onChange={(event) => setSeasonId(event.target.value)}
            required
          />
        </label>
        <button type="submit" disabled={isLoading}>
          {isLoading ? "Loading…" : "Load history"}
        </button>
      </form>

      {isLoading ? <p className="status">Loading player history…</p> : null}
      {error ? <p className="status error">{error}</p> : null}

      {history && history.games.length === 0 ? (
        <p className="status">
          No game history for {history.player_name} in season{" "}
          {history.season_id}.
        </p>
      ) : null}

      {history && history.games.length > 0 ? (
        <section className="results">
          <h2>
            {history.player_name}{" "}
            <span className="meta">
              Player {history.player_id} · Season {history.season_id}
            </span>
          </h2>
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
