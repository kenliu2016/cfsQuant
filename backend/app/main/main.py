import os
from fastapi import FastAPI 
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .errors import global_exception_handler, validation_exception_handler
from .middleware import logging_middleware, tenant_middleware, audit_middleware
from ..routers import strategies, market, backtest, health, export, runs, tuning, trades, tenants, live_trading, auth, users, audit_logs, dashboard_optimized
from ..api import strong_weak_coins
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

# Middleware (tenant context needs to run before logging for richer context)
app.middleware("http")(tenant_middleware)
app.middleware("http")(logging_middleware)
app.middleware("http")(audit_middleware)

# Exception handlers
app.exception_handler(Exception)(global_exception_handler)
app.exception_handler(RequestValidationError)(validation_exception_handler)

# Routes
app.include_router(health.router)
app.include_router(market.public_router)  # 公共market接口（先注册，不需要认证）
app.include_router(market.router)  # 需要认证的market接口
app.include_router(strategies.router)
app.include_router(backtest.router)
app.include_router(runs.router)
app.include_router(export.router)
app.include_router(tuning.router)
app.include_router(trades.router)
app.include_router(tenants.router)
app.include_router(live_trading.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(audit_logs.router)
app.include_router(dashboard_optimized.router)  # Dashboard优化API接口
app.include_router(strong_weak_coins.router)  # 强势弱势币种筛选API接口
