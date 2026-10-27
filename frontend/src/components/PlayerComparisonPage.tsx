import { FormEvent, useEffect, useState } from "react";

import { fetchPlayers, fetchSeasons } from "../api/lookups";
import { ApiError, isAbortError } from "../api/http";
import {
  fetchPlayerSeasonBatting,
  PlayerSeasonBattingApiError,
} from "../api/playerSeasonBatting";
import type { PlayerOption, SeasonOption } from "../types/lookups";
import type { PlayerSeasonBatting } from "../types/playerSeasonBatting";
import { PlayerComparisonCharts } from "./PlayerComparisonCharts";
import { SearchableSelect } from "./SearchableSelect";
import { ThemeToggle } from "./ThemeToggle";

type StatFormat = "count" | "average" | "percent";

const COMPARISON_STATS: {
  key: keyof PlayerSeasonBatting;
  label: string;
  format: StatFormat;
}[] = [
  { key: "games", label: "G", format: "count" },
  { key: "plate_appearances", label: "PA", format: "count" },
  { key: "at_bats", label: "AB", format: "count" },
  { key: "hits", label: "H", format: "count" },
  { key: "doubles", label: "2B", format: "count" },
  { key: "triples", label: "3B", format: "count" },
  { key: "home_runs", label: "HR", format: "count" },
  { key: "walks", label: "BB", format: "count" },
  { key: "hit_by_pitch", label: "HBP", format: "count" },
  { key: "strikeouts", label: "SO", format: "count" },
  { key: "batting_average", label: "AVG", format: "average" },
  { key: "on_base_percentage", label: "OBP", format: "average" },
  { key: "slugging_percentage", label: "SLG", format: "average" },
  { key: "ops", label: "OPS", format: "average" },
  { key: "strikeout_rate", label: "K%", format: "percent" },
  { key: "walk_rate", label: "BB%", format: "percent" },
];

function lookupErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.detail;
  }
  return fallback;
}

function formatCount(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return String(value);
}

function formatAverage(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return value.toFixed(3);
}

function formatPercent(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function formatStat(value: number | string | null, format: StatFormat): string {
  if (typeof value !== "number" && value !== null) {
    return "—";
  }
  if (format === "average") {
    return formatAverage(value);
  }
  if (format === "percent") {
    return formatPercent(value);
  }
  return formatCount(value);
}

function hasSeasonBattingLine(line: PlayerSeasonBatting): boolean {
  return line.games !== null;
}

export function PlayerComparisonPage() {
  const [seasons, setSeasons] = useState<SeasonOption[]>([]);
  const [players, setPlayers] = useState<PlayerOption[]>([]);
  const [seasonId, setSeasonId] = useState("");
  const [firstPlayerId, setFirstPlayerId] = useState("");
  const [secondPlayerId, setSecondPlayerId] = useState("");
  const [firstPlayerQuery, setFirstPlayerQuery] = useState("");
  const [secondPlayerQuery, setSecondPlayerQuery] = useState("");

  const [seasonsLoading, setSeasonsLoading] = useState(true);
  const [playersLoading, setPlayersLoading] = useState(false);
  const [optionsError, setOptionsError] = useState<string | null>(null);

  const [comparison, setComparison] = useState<
    [PlayerSeasonBatting, PlayerSeasonBatting] | null
  >(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedSeason = seasons.find(
    (season) => String(season.season_id) === seasonId,
  );
  const samePlayerSelected =
    firstPlayerId !== "" && firstPlayerId === secondPlayerId;
  const canCompare =
    seasonId !== "" &&
    firstPlayerId !== "" &&
    secondPlayerId !== "" &&
    !samePlayerSelected;

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
      setPlayers([]);
      setPlayersLoading(false);
      return;
    }

    const controller = new AbortController();
    setPlayersLoading(true);
    setOptionsError(null);

    fetchPlayers(Number(seasonId), undefined, controller.signal)
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
  }, [seasonId]);

  function handleSeasonChange(nextSeasonId: string) {
    setSeasonId(nextSeasonId);
    setFirstPlayerId("");
    setSecondPlayerId("");
    setFirstPlayerQuery("");
    setSecondPlayerQuery("");
    setPlayers([]);
    setPlayersLoading(nextSeasonId !== "");
    setComparison(null);
    setError(null);
  }

  function handleFirstPlayerChange(nextPlayerId: string) {
    setFirstPlayerId(nextPlayerId);
    setComparison(null);
    setError(null);
  }

  function handleSecondPlayerChange(nextPlayerId: string) {
    setSecondPlayerId(nextPlayerId);
    setComparison(null);
    setError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (samePlayerSelected) {
      setComparison(null);
      setError("Select two different players.");
      return;
    }

    if (!canCompare) {
      setComparison(null);
      setError("Select a season and two players.");
      return;
    }

    setIsLoading(true);
    setComparison(null);
    try {
      const [first, second] = await Promise.all([
        fetchPlayerSeasonBatting(Number(firstPlayerId), Number(seasonId)),
        fetchPlayerSeasonBatting(Number(secondPlayerId), Number(seasonId)),
      ]);
      setComparison([first, second]);
    } catch (requestError) {
      setComparison(null);
      if (requestError instanceof PlayerSeasonBattingApiError) {
        setError(requestError.detail);
      } else {
        setError("Unable to load player season batting.");
      }
    } finally {
      setIsLoading(false);
    }
  }

  const playerOptions = players.map((player) => ({
    value: String(player.player_id),
    label: player.full_name,
  }));
  const seasonYearLabel = selectedSeason
    ? String(selectedSeason.season_year)
    : comparison?.[0].season_year != null
      ? String(comparison[0].season_year)
      : "";
  const missingBattingNames = comparison
    ? comparison
        .filter((line) => !hasSeasonBattingLine(line))
        .map((line) => line.full_name)
    : [];

  return (
    <main className="page">
      <header className="page-header">
        <div className="page-header-copy">
          <h1>Player Comparison</h1>
          <p>
            Choose a season and two players to compare season batting lines
            from the Baseball Intelligence API.
          </p>
        </div>
        <ThemeToggle />
      </header>

      <form className="history-form" onSubmit={handleSubmit}>
        <label htmlFor="comparisonSeasonId">
          Season
          <select
            id="comparisonSeasonId"
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

        <SearchableSelect
          id="firstPlayerId"
          label="Player 1"
          value={firstPlayerId}
          options={playerOptions}
          disabled={seasonId === "" || playersLoading}
          required
          searchValue={firstPlayerQuery}
          onSearchChange={setFirstPlayerQuery}
          onChange={handleFirstPlayerChange}
          placeholder={
            playersLoading ? "Loading players…" : "Select a player"
          }
          searchPlaceholder="Search players by name"
          emptyMessage="No players match that search."
        />

        <SearchableSelect
          id="secondPlayerId"
          label="Player 2"
          value={secondPlayerId}
          options={playerOptions}
          disabled={seasonId === "" || playersLoading}
          required
          searchValue={secondPlayerQuery}
          onSearchChange={setSecondPlayerQuery}
          onChange={handleSecondPlayerChange}
          placeholder={
            playersLoading ? "Loading players…" : "Select a player"
          }
          searchPlaceholder="Search players by name"
          emptyMessage="No players match that search."
        />

        <button type="submit" disabled={isLoading || !canCompare}>
          {isLoading ? "Loading…" : "Compare"}
        </button>
      </form>

      {seasonsLoading ? <p className="status">Loading seasons…</p> : null}
      {!seasonsLoading && seasons.length === 0 && !optionsError ? (
        <p className="status">No seasons with batting history are available.</p>
      ) : null}
      {seasonId !== "" &&
      !playersLoading &&
      players.length === 0 &&
      !optionsError ? (
        <p className="status">No players have batting history in that season.</p>
      ) : null}
      {samePlayerSelected ? (
        <p className="status error">Select two different players.</p>
      ) : null}
      {optionsError ? <p className="status error">{optionsError}</p> : null}
      {isLoading ? <p className="status">Loading player comparison…</p> : null}
      {error ? <p className="status error">{error}</p> : null}

      {comparison && !isLoading ? (
        <section className="results">
          <h2>
            {comparison[0].full_name} vs {comparison[1].full_name}{" "}
            <span className="meta">
              {seasonYearLabel ? `Season ${seasonYearLabel}` : "Season"}
            </span>
          </h2>
          {missingBattingNames.length > 0 ? (
            <p className="status">
              No season batting line for {missingBattingNames.join(" and ")}
              {seasonYearLabel ? ` in ${seasonYearLabel}` : ""}.
            </p>
          ) : null}
          <PlayerComparisonCharts
            first={comparison[0]}
            second={comparison[1]}
          />
          <div className="comparison-table-wrap">
            <table className="comparison-table">
              <thead>
                <tr>
                  <th>Stat</th>
                  <th>{comparison[0].full_name}</th>
                  <th>{comparison[1].full_name}</th>
                </tr>
              </thead>
              <tbody>
                {COMPARISON_STATS.map((stat) => (
                  <tr key={stat.key}>
                    <th scope="row">{stat.label}</th>
                    <td>
                      {formatStat(comparison[0][stat.key], stat.format)}
                    </td>
                    <td>
                      {formatStat(comparison[1][stat.key], stat.format)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </main>
  );
}
