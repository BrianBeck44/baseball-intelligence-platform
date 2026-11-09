import { useEffect, useState } from "react";

import { fetchSeasons } from "../api/lookups";
import { ApiError, isAbortError } from "../api/http";
import {
  fetchSeasonCaOpsAnalytics,
  SeasonCaOpsAnalyticsApiError,
} from "../api/playerSeasonCaOpsAnalytics";
import type { SeasonOption } from "../types/lookups";
import type { SeasonCaOpsAnalytics } from "../types/playerSeasonCaOpsAnalytics";
import { CaOpsAnalyticsCharts } from "./CaOpsAnalyticsCharts";
import { MINIMUM_PLATE_APPEARANCES } from "./caOpsAnalyticsRankings";
import { ThemeToggle } from "./ThemeToggle";

function lookupErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.detail;
  }
  return fallback;
}

export function CaOpsAnalyticsDashboardPage() {
  const [seasons, setSeasons] = useState<SeasonOption[]>([]);
  const [seasonId, setSeasonId] = useState("");
  const [seasonsLoading, setSeasonsLoading] = useState(true);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [analytics, setAnalytics] = useState<SeasonCaOpsAnalytics | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedSeason = seasons.find(
    (season) => String(season.season_id) === seasonId,
  );
  const seasonYearLabel = selectedSeason
    ? String(selectedSeason.season_year)
    : analytics?.season_year != null
      ? String(analytics.season_year)
      : "";

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
      setAnalytics(null);
      setError(null);
      setIsLoading(false);
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setAnalytics(null);
    setError(null);

    fetchSeasonCaOpsAnalytics(Number(seasonId), controller.signal)
      .then((result) => {
        setAnalytics(result);
      })
      .catch((requestError) => {
        if (isAbortError(requestError)) {
          return;
        }
        setAnalytics(null);
        if (requestError instanceof SeasonCaOpsAnalyticsApiError) {
          setError(requestError.detail);
        } else {
          setError("Unable to load CA-OPS analytics.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });

    return () => controller.abort();
  }, [seasonId]);

  return (
    <main className="page ca-ops-dashboard">
      <header className="page-header">
        <div className="page-header-copy">
          <h1>CA-OPS Analytics Dashboard</h1>
          <p>Competition-Adjusted OPS (CA-OPS)</p>
        </div>
        <ThemeToggle />
      </header>

      <section className="ca-ops-explainer">
        <p>
          <strong>
            CA-OPS is a custom retrospective metric that adjusts a hitter's
            Observed OPS based on the quality of the opposing pitchers they
            faced. It measures how a hitter performed relative to the expected
            difficulty of their competition. It is not an official MLB
            statistic.
          </strong>
        </p>
        <p className="ca-ops-formula">
          CA-OPS = League OPS + (Observed OPS − Expected Opponent OPS)
        </p>
        <ul>
          <li>
            <strong>Observed OPS</strong> is the hitter's actual OPS.
          </li>
          <li>
            <strong>Expected Opponent OPS</strong> is the PA-weighted expected
            OPS based on the quality of pitchers faced.
          </li>
          <li>
            <strong>League OPS</strong> is the leave-one-batter-out league
            baseline used to recenter the metric.
          </li>
          <li>
            Facing tougher-than-average pitching can increase CA-OPS above
            Observed OPS.
          </li>
          <li>
            Facing weaker-than-average pitching can decrease CA-OPS below
            Observed OPS.
          </li>
          <li>
            Rankings include only players with at least{" "}
            {MINIMUM_PLATE_APPEARANCES} plate appearances.
          </li>
        </ul>
      </section>

      <form className="history-form" onSubmit={(event) => event.preventDefault()}>
        <label htmlFor="caOpsDashboardSeasonId">
          Season
          <select
            id="caOpsDashboardSeasonId"
            name="seasonId"
            value={seasonId}
            onChange={(event) => setSeasonId(event.target.value)}
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
      </form>

      {seasonsLoading ? <p className="status">Loading seasons…</p> : null}
      {!seasonsLoading && seasons.length === 0 && !optionsError ? (
        <p className="status">No seasons with batting history are available.</p>
      ) : null}
      {optionsError ? <p className="status error">{optionsError}</p> : null}
      {isLoading ? <p className="status">Loading CA-OPS analytics…</p> : null}
      {error ? <p className="status error">{error}</p> : null}

      {analytics && !isLoading ? (
        <section className="results">
          <h2>
            Season rankings
            <span className="meta">
              {seasonYearLabel ? `Season ${seasonYearLabel}` : "Season"}
            </span>
          </h2>
          {analytics.players.length === 0 ? (
            <p className="status">
              No CA-OPS rows are available
              {seasonYearLabel ? ` for ${seasonYearLabel}` : " for that season"}.
            </p>
          ) : (
            <CaOpsAnalyticsCharts players={analytics.players} />
          )}
        </section>
      ) : null}
    </main>
  );
}
