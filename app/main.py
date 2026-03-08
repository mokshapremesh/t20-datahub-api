from fastapi import FastAPI
from app.routers import auth, matches, fantasy, profile
from app.routers.matches import admin_router as matches_admin_router
from app.routers.profile import options_router
from app.routers.fantasy_v2 import teams_router, lb_router, squad_router

app = FastAPI(
    title="T20 DataHub API",
    description="T20 World Cup Season Challenge — 2014-2026",
    version="2.0.0",
    openapi_tags=[
        {"name": "Auth"},
        {"name": "Matches"},
        {"name": "Admin - Matches"},
        {"name": "Fan Profile & Dashboard"},
        {"name": "Fantasy Teams"},
        {"name": "Fantasy Leaderboards"},
        {"name": "Match Squads"},
    ]
)

app.include_router(auth.router)
app.include_router(matches.router)
app.include_router(matches_admin_router)
app.include_router(fantasy.router)
app.include_router(teams_router)
app.include_router(lb_router)
app.include_router(squad_router)
app.include_router(profile.router)
app.include_router(options_router)

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "project": "T20DataHub"}
