from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import FastAPI
from app.routers import auth, search, matches, fantasy, profile
from app.routers.matches import admin_router as matches_admin_router
from app.routers.profile import options_router
from app.routers.fantasy_v2 import teams_router, lb_router, squad_router

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="T20 DataHub API",
    description="T20 World Cup Season Challenge — 2014-2026",
    version="2.0.0",
    openapi_tags=[
        {"name": "Auth"},
        {"name": "Matches"},
        {"name": "Admin - Matches"},
        {"name": "Fan Profile & Dashboard"},
        {"name": "Match Squads"},
        {"name": "Fantasy Teams"},
        {"name": "Fantasy Leaderboards"},
    ]
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

app.include_router(auth.router)
app.include_router(search.router)
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
