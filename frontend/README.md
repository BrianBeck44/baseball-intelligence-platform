# Baseball Intelligence Frontend

React + TypeScript UI for the Baseball Intelligence Platform. The first
screen loads a player's game-by-game batting history. Select a season
year, a team (or Search All Teams), then a player name. The page uses:

```text
GET /seasons
GET /teams?season_id={season_id}
GET /players?season_id={season_id}&team_id={team_id}
GET /players/{player_id}/games?season_id={season_id}&limit={limit}
```

The table shows game date, season game number, team ID, plate
appearances, rolling 14-game OPS, season OPS, and OPS difference. Null
OPS values render as an em dash. Use the header control to switch
between light and dark themes; the choice is stored in localStorage.

## Requirements

- Node.js 16 or later (the scaffold uses Vite 4 so it runs on the
  repository's current Node 16)
- A running FastAPI backend

## Install

From the repository root:

```text
cd frontend
npm install
```

## Configure the API URL

Copy the example environment file and edit it if the backend is not on
the default local address:

```text
cp .env.example .env
```

`VITE_API_BASE_URL` defaults to `http://127.0.0.1:8000` when unset.
Restart `npm run dev` after changing it.

## Run the frontend

In one terminal, start the API from `backend/`:

```text
uvicorn app.main:app --reload --app-dir .
```

If you run that command from `backend/`, omit `--app-dir` and use:

```text
uvicorn app.main:app --reload
```

In another terminal:

```text
cd frontend
npm run dev
```

The Vite dev server listens on `http://localhost:5173`. The backend
allows that origin (and `http://127.0.0.1:5173`) for local browser
requests.

Select a season year, team, and player name, then load history. The
page submits the internal `player_id` and `season_id` values to the
game-history API.

## Checks

```text
cd frontend
npm run lint
npm run build
```
