import { useState } from "react";

import { CaOpsAnalyticsDashboardPage } from "./components/CaOpsAnalyticsDashboardPage";
import { PlayerComparisonPage } from "./components/PlayerComparisonPage";
import { PlayerGameHistoryPage } from "./components/PlayerGameHistoryPage";

type AppView = "history" | "comparison" | "caOpsDashboard";

function App() {
  const [view, setView] = useState<AppView>("history");

  return (
    <>
      <nav className="app-nav" aria-label="Primary">
        <button
          type="button"
          className={view === "history" ? "is-active" : undefined}
          aria-current={view === "history" ? "page" : undefined}
          onClick={() => setView("history")}
        >
          Player Game History
        </button>
        <button
          type="button"
          className={view === "comparison" ? "is-active" : undefined}
          aria-current={view === "comparison" ? "page" : undefined}
          onClick={() => setView("comparison")}
        >
          Player Comparison
        </button>
        <button
          type="button"
          className={view === "caOpsDashboard" ? "is-active" : undefined}
          aria-current={view === "caOpsDashboard" ? "page" : undefined}
          onClick={() => setView("caOpsDashboard")}
        >
          CA-OPS Analytics Dashboard
        </button>
      </nav>
      {view === "history" ? <PlayerGameHistoryPage /> : null}
      {view === "comparison" ? <PlayerComparisonPage /> : null}
      {view === "caOpsDashboard" ? <CaOpsAnalyticsDashboardPage /> : null}
    </>
  );
}

export default App;
