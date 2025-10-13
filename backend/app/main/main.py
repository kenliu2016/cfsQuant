import os
from fastapi import FastAPI 
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .errors import global_exception_handler, validation_exception_handler
from .middleware import logging_middleware
from .routers import strategies, market, backtest, health, export, runs, tuning, trades
from fastapi.exceptions import RequestValidationError

app = FastAPI(title=settings.APP_TITLE, version=settings.APP_VERSION)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware
app.middleware("http")(logging_middleware)

# Exception handlers
app.exception_handler(Exception)(global_exception_handler)
app.exception_handler(RequestValidationError)(validation_exception_handler)

# Routes
app.include_router(health.router)
app.include_router(market.router)
app.include_router(strategies.router)
app.include_router(backtest.router)
app.include_router(runs.router)
app.include_router(export.router)
app.include_router(tuning.router)
app.include_router(trades.router)
