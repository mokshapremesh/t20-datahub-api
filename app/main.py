from fastapi import FastAPI

app = FastAPI(
    title="T20DataHub API",
    description="T20 World Cup Analytics API",
    version="0.1.0",
)

@app.get("/health")
async def health():
    return {"status": "ok", "project": "T20DataHub"}
