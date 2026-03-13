# 🏏 T20 DataHub API

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.131-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-336791?style=flat&logo=postgresql&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-52%20passing-22c55e?style=flat)
![Deployed on Render](https://img.shields.io/badge/Deployed-Render.com-46E3B7?style=flat)

A full-stack cricket data platform for T20 World Cup matches (2014–2026). Built with **FastAPI** + **PostgreSQL** on the backend and **React 18** on the frontend, with ball-by-ball match data, a fantasy cricket system, personalised fan dashboards, and a Claude Desktop MCP integration.

🌐 **Live App:** https://t20-datahub-api.onrender.com
📖 **API Docs:** https://t20-datahub-api.onrender.com/docs

> Free tier on Render spins down after inactivity — first request may take 30–60 seconds.

---

## Table of Contents

1. [Features](#features)
2. [Tech Stack](#tech-stack)
3. [Project Structure](#project-structure)
4. [Local Setup](#local-setup)
5. [API Reference](#api-reference)
6. [Authentication](#authentication)
7. [Frontend](#frontend)
8. [Testing](#testing)
9. [Deployment](#deployment)
10. [MCP Integration](#mcp-integration)
11. [Data Source](#data-source)

---

## Features

### Data & Matches
- 🏟️ **216 T20 World Cup matches** across 2014, 2016, 2021, 2022, 2024, 2026
- 📊 **Ball-by-ball scorecards** — batting, bowling, fall of wickets per innings
- 🏴 **Country flags** displayed alongside every team name in the UI
- 🔍 **Filterable match list** by year, stage, team, and venue

### User Features
- 👤 **Fan profiles** — set favourite team, player, and tournament year
- 📈 **Personalised dashboard** — team win/loss charts, player career history
- 🔐 **JWT authentication** with bcrypt password hashing
- 🛡️ **Role-based access control** — user and admin roles

### Fantasy Cricket
- ✨ **Build an XI** from real match squads
- 🏆 **Captain (2×) and Vice-Captain (1.5×)** multipliers
- 📬 **Submit teams** for fantasy scoring
- 🥇 **Per-match and global leaderboards**
- 👥 **Inline player browser** with search on every match page

### Admin & Operations
- 🔧 **Admin panel** — create, update, and delete matches
- 🔑 **Self-service admin promotion** via secret key
- ⏱️ **Rate limiting** on the login endpoint (10 req/min)
- 🔒 **Password policy** — 10+ characters, letters + numbers required
- 🗄️ **Alembic migrations** — 13 version-controlled migration files
- ✅ **52 automated tests** — auth, matches, profile, fantasy, admin, options

---

## Tech Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Backend | FastAPI | 0.131 |
| Database | PostgreSQL + asyncpg | 14+ |
| ORM | SQLAlchemy (async) | 2.0 |
| Migrations | Alembic | 1.18 |
| Auth | python-jose (JWT) + passlib (bcrypt) | — |
| Rate Limiting | SlowAPI | 0.1.9 |
| AI Integration | Anthropic SDK | 0.84 |
| Testing | pytest + pytest-asyncio | — |
| Frontend | React 18 + Vite | — |
| State / Data | TanStack Query v5 | — |
| Charts | Recharts | — |
| Styling | Tailwind CSS | — |
| Deployment | Render.com | — |

---

## Project Structure

```
t20-datahub-api/
├── app/
│   ├── main.py                  # App factory, middleware, router registration, SPA serving
│   ├── models/
│   │   ├── match.py             # Match + innings scores
│   │   ├── delivery.py          # Ball-by-ball delivery records
│   │   ├── user.py              # User accounts and roles
│   │   ├── profile.py           # Fan profile
│   │   └── fantasy.py           # Fantasy teams, players, entries
│   ├── routers/
│   │   ├── auth.py              # Register, login, /me, admin promotion
│   │   ├── matches.py           # Match list, scorecard, admin CRUD
│   │   ├── profile.py           # Fan profile + dashboard + options
│   │   └── fantasy_v2.py        # Squads, teams, captain/VC, leaderboards
│   ├── schemas/                 # Pydantic request/response models
│   ├── services/                # Auth logic, JWT creation/validation
│   ├── db/                      # Async session factory
│   └── utils/                   # Password policy validation
│
├── alembic/
│   └── versions/                # 13 migration files
│
├── tests/
│   ├── conftest.py              # Shared fixtures (test DB, auth headers)
│   ├── test_auth.py
│   ├── test_matches.py
│   ├── test_profile.py
│   ├── test_fantasy.py
│   ├── test_admin.py
│   └── test_options.py
│
├── scripts/
│   ├── import_matches.py        # Seed 216 matches from Cricsheet JSON
│   └── create_admin.py          # Create admin user via terminal
│
├── frontend/
│   └── src/
│       ├── App.jsx              # Router, auth context, navbar
│       ├── api/client.js        # Axios instance with JWT interceptor
│       ├── utils/flags.js       # Team name → country flag emoji
│       ├── components/          # Layout, Spinner, ErrorCard, EmptyState
│       └── pages/
│           ├── Matches.jsx           # Filterable match list with flags
│           ├── MatchDetail.jsx       # Match hero + inline player browser
│           ├── Scorecard.jsx         # Batting/bowling tables, FoW, tabs
│           ├── Squads.jsx            # Match squad viewer
│           ├── Profile.jsx           # Fan profile form + admin promotion
│           ├── Dashboard.jsx         # Stats + bar charts
│           ├── FantasyBuild.jsx      # Squad → XI → C/VC → submit
│           ├── FantasyTeams.jsx      # User's teams list
│           ├── FantasyTeamDetail.jsx # Single team view
│           ├── GlobalLeaderboard.jsx
│           ├── MatchLeaderboard.jsx
│           ├── AdminMatches.jsx      # Admin match management
│           ├── Login.jsx / Register.jsx
│           └── NotFound.jsx
│
├── mcp_server.py                # MCP server for Claude Desktop
├── requirements.txt
├── Procfile                     # Render: uvicorn startup command
├── .python-version              # 3.11.9
└── README.md
```

---

## Local Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Node.js 18+ *(frontend only)*

### 1. Clone

```bash
git clone https://github.com/mokshapremesh/t20-datahub-api.git
cd t20-datahub-api
```

### 2. Python environment

```bash
python3 -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate           # Windows
pip install -r requirements.txt
```

### 3. Environment variables

Create `.env` in the project root:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/t20datahub
DATABASE_URL_SYNC=postgresql://user:password@localhost:5432/t20datahub
SECRET_KEY=your-secret-key-at-least-32-characters-long
ADMIN_SECRET=your-admin-promotion-secret
```

### 4. Database setup

```bash
createdb t20datahub
PYTHONPATH=. alembic upgrade head
PYTHONPATH=. python3 scripts/import_matches.py
# → Imports: 216 matches | Skipped: 0 | Errors: 0
```

### 5. Run the API

```bash
PYTHONPATH=. uvicorn app.main:app --reload
```

| URL | Description |
|-----|-------------|
| http://localhost:8000 | API root |
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/redoc | ReDoc |

### 6. Run the frontend *(optional)*

```bash
cd frontend
npm install
npm run dev          # → http://localhost:5173
```

The Vite dev server proxies `/api/*` to `http://localhost:8000`, so the backend must be running.

---

## API Reference

### Auth

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/auth/register` | Register a new user | — |
| `POST` | `/auth/login` | Login, returns JWT token | — |
| `GET` | `/auth/me` | Current user info | ✅ |
| `POST` | `/auth/make-admin?secret=` | Promote yourself to admin | ✅ |

### Matches

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/matches` | List matches — filters: `year`, `team`, `stage`, `venue` | — |
| `GET` | `/matches/{id}` | Single match detail | — |
| `GET` | `/matches/{id}/scorecard` | Full batting/bowling scorecard + FoW | — |
| `GET` | `/matches/{id}/squads` | Player squads for team selection | — |

### Admin — Matches

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/admin/matches` | Create a match | 🔑 Admin |
| `PATCH` | `/admin/matches/{id}` | Update a match | 🔑 Admin |
| `DELETE` | `/admin/matches/{id}` | Delete a match | 🔑 Admin |

### Fan Profile & Dashboard

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `PUT` | `/me/profile` | Create or update fan profile | ✅ |
| `GET` | `/me/profile` | Get fan profile | ✅ |
| `DELETE` | `/me/profile` | Delete fan profile | ✅ |
| `GET` | `/me/dashboard` | Personalised stats dashboard | ✅ |

### Fantasy Cricket

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/matches/{id}/fantasy/teams` | My fantasy teams for a match | ✅ |
| `POST` | `/matches/{id}/fantasy/teams` | Create a new fantasy team | ✅ |
| `GET` | `/fantasy/teams/{id}` | Get a specific team | ✅ |
| `PUT` | `/fantasy/teams/{id}/captain` | Set captain (2× points) | ✅ |
| `PUT` | `/fantasy/teams/{id}/vice-captain` | Set vice-captain (1.5× points) | ✅ |
| `POST` | `/fantasy/teams/{id}/submit` | Submit team for scoring | ✅ |
| `DELETE` | `/fantasy/teams/{id}` | Delete a draft team | ✅ |
| `GET` | `/matches/{id}/fantasy/leaderboard` | Per-match leaderboard | — |
| `GET` | `/fantasy/leaderboard` | Global leaderboard | — |

### Reference Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/options/years` | Tournament years with match data |
| `GET` | `/options/teams` | All teams with win/loss stats |
| `GET` | `/options/players` | All players |
| `GET` | `/health` | API health check |

---

## Authentication

The API uses **JWT Bearer tokens**.

```bash
# 1. Register
curl -X POST /auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "fan1", "email": "fan@example.com", "password": "cricket123"}'

# 2. Login
curl -X POST /auth/login \
  -F "username=fan1" -F "password=cricket123"
# → {"access_token": "eyJ...", "token_type": "bearer"}

# 3. Use token
curl /me/profile -H "Authorization: Bearer eyJ..."
```

**Token lifetime:** 24 hours

**Password policy:**
- Minimum 10 characters
- Must include at least one letter and one number
- Common weak passwords rejected

**Admin access:**
Call `POST /auth/make-admin?secret=<ADMIN_SECRET>` while authenticated. The secret is configured via the `ADMIN_SECRET` environment variable.

---

## Frontend

A React 18 SPA served directly by FastAPI in production (from `frontend/dist/`).

| Page | Route | Description |
|------|-------|-------------|
| Matches | `/matches` | Filterable match list with country flags |
| Match Detail | `/matches/:id` | Scores, toss, inline player browser with search |
| Scorecard | `/matches/:id/scorecard` | Innings tabs, batting/bowling tables, fall of wickets |
| Squads | `/matches/:id/squads` | Full player squads grouped by team |
| Fantasy Build | `/matches/:id/fantasy/teams` | Pick XI, set C/VC, submit |
| Fantasy Teams | `/fantasy/teams` | Manage your teams |
| Leaderboard | `/matches/:id/fantasy/leaderboard` | Match fantasy rankings |
| Profile | `/me/profile` | Favourite team, player, year + admin promotion |
| Dashboard | `/me/dashboard` | Personalised charts and stats |
| Admin | `/admin/matches` | Match management (admin only) |

**Build for production:**

```bash
cd frontend
npm run build
# Built files in frontend/dist/ — served automatically by FastAPI
```

---

## Testing

```bash
source venv/bin/activate
python3 -m pytest tests/ -v
```

**52 tests** across 6 files:

| File | Coverage |
|------|----------|
| `test_auth.py` | Register, login, JWT validation, password policy |
| `test_matches.py` | Match list, filters, scorecard |
| `test_profile.py` | Fan profile CRUD, dashboard |
| `test_fantasy.py` | Team creation, captain/VC, submit, leaderboard |
| `test_admin.py` | Admin-only route protection, CRUD |
| `test_options.py` | Years, teams, players endpoints |

---

## Deployment

Deployed on **Render.com** with a managed PostgreSQL database.

**Procfile:**
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Required environment variables on Render:**

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL async connection string (`postgresql+asyncpg://...`) |
| `SECRET_KEY` | JWT signing secret (32+ characters) |
| `ADMIN_SECRET` | Secret for admin self-promotion |

**URLs:**
- App + API: https://t20-datahub-api.onrender.com
- Swagger: https://t20-datahub-api.onrender.com/docs

---

## MCP Integration

An MCP (Model Context Protocol) server lets **Claude Desktop** query match data using natural language.

### Setup

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "t20-datahub": {
      "command": "/absolute/path/to/venv/bin/python3",
      "args": ["/absolute/path/to/t20-datahub-api/mcp_server.py"]
    }
  }
}
```

Restart Claude Desktop. You can then ask things like:
*"Who won the 2022 T20 World Cup final?"* or *"Show me India's scorecard against Pakistan."*

### Available Tools

| Tool | Description |
|------|-------------|
| `t20_login` | Authenticate with the API |
| `t20_list_matches` | List and filter matches |
| `t20_get_scorecard` | Get full match scorecard |
| `t20_get_teams` | Get team statistics |
| `t20_get_players` | List all players |
| `t20_get_global_leaderboard` | Global fantasy leaderboard |

---

## Data Source

Ball-by-ball match data sourced from [**Cricsheet**](https://cricsheet.org) — a free, open cricket data resource.

**Coverage:** T20 World Cup 2014 · 2016 · 2021 · 2022 · 2024 · 2026

---

## Author

**Moksha Premesh Kancharla**
University of Leeds — University Coursework
March 2026
