"""
Routers package initialization
导出所有路由模块
"""

from . import strategies
from . import market
from . import backtest
from . import health
from . import export
from . import runs
from . import tuning
from . import trades
from . import tenants
from . import live_trading
from . import auth
from . import users
from . import audit_logs
from . import dashboard_optimized

__all__ = [
    "strategies",
    "market", 
    "backtest",
    "health",
    "export",
    "runs",
    "tuning",
    "trades",
    "tenants",
    "live_trading",
    "auth",
    "users",
    "audit_logs",
    "dashboard_optimized"
]