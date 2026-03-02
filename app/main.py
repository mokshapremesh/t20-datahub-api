from fastapi import FastAPI
from app.routers import auth, matches, fantasy, profile
from app.routers.profile import options_router

app = FastAPI(
    title="T20 DataHub API",
    description="T20 World Cup Season Challenge — 2014-2026",
    version="2.0.0",
)

app.include_router(auth.router)
app.include_router(matches.router)
app.include_router(fantasy.router)
app.include_router(profile.router)
app.include_router(options_router)

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "project": "T20DataHub"}
