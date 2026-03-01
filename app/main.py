from fastapi import FastAPI
from app.routers import auth, matches, fantasy, predictions

app = FastAPI(
    title="T20 DataHub API",
    description="T20 World Cup Analytics API — all tournaments 2014-2026",
    version="1.0.0",
)

app.include_router(auth.router)
app.include_router(matches.router)
app.include_router(fantasy.router)
app.include_router(predictions.router)

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "project": "T20DataHub"}
