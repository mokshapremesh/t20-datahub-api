from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from fastapi import FastAPI
from app.routers import auth, matches, profile
from fastapi.middleware.cors import CORSMiddleware
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

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(SlowAPIMiddleware)

app.include_router(auth.router)
app.include_router(matches.router)
app.include_router(matches_admin_router)
app.include_router(teams_router)
app.include_router(lb_router)
app.include_router(squad_router)
app.include_router(profile.router)
app.include_router(options_router)

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "project": "T20DataHub"}

# ── SPA static serving ──────────────────────────────────────────────────────
try:
    app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")
except Exception:
    pass  # assets folder may not exist in dev

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    api_prefixes = ("auth/", "matches", "fantasy/", "me/", 
                    "options/", "health", "docs", "redoc", "openapi.json")
    if full_path.startswith(api_prefixes):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not Found")
    index_path = "frontend/dist/index.html"
    if os.path.exists(index_path):
        return FileResponse(index_path)
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Frontend not built")
