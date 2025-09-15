import os
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from .routers import strategies, market, backtest, health, export, runs, predictions, tuning, monitor, trades
import os
import asyncio
import logging
import time
from contextlib import asynccontextmanager

# 配置日志 - 只显示WARNING及以上级别的信息，减少调试输出
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 创建应用生命周期管理器
@asynccontextmanager
async def app_lifespan(app: FastAPI):
    # 应用启动时
    # 启动缓存预热任务（作为后台任务，不阻塞应用启动）
    import threading
    threading.Thread(target=prewarm_market_cache, daemon=True).start()
    
    yield  # 应用运行中
    
    # 应用关闭时
    # 可以在这里添加关闭时的清理代码
    pass

app = FastAPI(title="Trading API", version="0.1.0", lifespan=app_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGIN", "*")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加请求-响应日志记录中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # 记录请求信息
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    logger.debug(f"请求开始: {request.method} {request.url} (客户端: {client_ip})")
    
    # 处理请求
    try:
        response = await call_next(request)
        
        # 计算处理时间
        process_time = time.time() - start_time
        
        # 记录响应信息
        logger.debug(f"请求完成: {request.method} {request.url} 状态码: {response.status_code} 耗时: {process_time:.4f}秒")
        
        return response
    except Exception as e:
        # 记录异常信息
        process_time = time.time() - start_time
        logger.error(f"请求异常: {request.method} {request.url} 异常: {str(e)} 耗时: {process_time:.4f}秒")
        raise

# 添加全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """处理所有未捕获的异常"""
    logger.error(f"全局异常: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "服务器内部错误，请稍后重试",
            "error_type": type(exc).__name__
        }
    )

# 添加请求验证异常处理器
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证异常"""
    logger.warning(f"请求验证失败: {str(exc)}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "请求参数验证失败",
            "errors": exc.errors()
        }
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

def prewarm_market_cache():
    """预热市场数据缓存"""
    # 导入需要的模块
    from datetime import datetime, timedelta
    from .services.market_service import get_intraday
    
    hot_codes = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']  # 热门交易对
    
    try:
        # 计算日期范围（过去7天）
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        
        logger.debug(f"开始预热市场数据缓存，代码: {', '.join(hot_codes)}")
        
        # 直接同步调用，不再使用异步任务
        success_count = 0
        for code in hot_codes:
            try:
                get_intraday(code, start_str, end_str)
                success_count += 1
                logger.debug(f"成功预热 {code} 的市场数据缓存")
            except Exception as e:
                logger.error(f"预热 {code} 的市场数据缓存失败: {e}")
        
        logger.debug(f"市场数据缓存预热完成，成功: {success_count}/{len(hot_codes)}")
    except Exception as e:
        logger.error(f"执行缓存预热过程中发生错误: {e}")
