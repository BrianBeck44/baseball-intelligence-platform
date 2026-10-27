import { useState } from "react";

import { PlayerComparisonPage } from "./components/PlayerComparisonPage";
import { PlayerGameHistoryPage } from "./components/PlayerGameHistoryPage";

type AppView = "history" | "comparison";

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
      </nav>
      {view === "history" ? (
        <PlayerGameHistoryPage />
      ) : (
        <PlayerComparisonPage />
      )}
    </>
  );
}

export default App;
