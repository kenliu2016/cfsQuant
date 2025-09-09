import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import strategies, market, backtest, health, export, runs, predictions, tuning, monitor, trades

app = FastAPI(title="Trading API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGIN", "*")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(market.router)
app.include_router(predictions.router)
app.include_router(strategies.router)
app.include_router(backtest.router)
app.include_router(runs.router)
app.include_router(export.router)

app.include_router(tuning.router)
app.include_router(monitor.router)
app.include_router(trades.router)
