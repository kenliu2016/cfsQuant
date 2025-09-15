from fastapi import APIRouter, Query
from ..services.market_service import get_candles, get_daily_candles, get_intraday, refresh_market_data_cache
from datetime import datetime, timedelta
router = APIRouter(prefix="/api/market", tags=["market"])
@router.get("/candles")
def candles(code: str = Query(...), start: str = Query(None), end: str = Query(None), interval: str = Query("1m"), 
                 page: int = Query(None, ge=1, description="页码，从1开始"), 
                 page_size: int = Query(None, ge=1, le=1000, description="每页数据量，最大1000条")):
    # 根据interval参数设置默认的查询时间范围
    now = datetime.now()
    today = datetime(now.year, now.month, now.day)
    
    if not start and not end:
        if interval in ["1m", "5m", "15m"]:
            # 1m, 5m, 15m: 默认查询当天的数据
            start_dt = today
            end_dt = now
        elif interval == "30m":
            # 30m: 默认查询最近2天的数据
            start_dt = today - timedelta(days=1)
            end_dt = now
        elif interval == "1h":
            # 1h: 默认查询最近5天的数据
            start_dt = today - timedelta(days=4)
            end_dt = now
        elif interval == "4h":
            # 4h: 默认查询最近30天的数据
            start_dt = today - timedelta(days=29)
            end_dt = now
        else:
            # 其他情况默认查询当天数据
            start_dt = today
            end_dt = now
    else:
        # 将字符串类型的日期时间转换为datetime对象
        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # 尝试其他常见格式
            try:
                start_dt = datetime.strptime(start, "%Y-%m-%d")
                end_dt = datetime.strptime(end, "%Y-%m-%d")
            except ValueError:
                start_dt = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S")
                end_dt = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S")
            
    result = get_candles(code, start_dt, end_dt, interval, page, page_size)
    
    # 处理分页数据
    if isinstance(result, tuple) and len(result) == 2:
        df, total_count = result
        if "datetime" in df.columns:
            df["datetime"] = df["datetime"].astype(str)
        return {
            "rows": df.to_dict(orient="records"),
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "has_more": page * page_size < total_count
        }
    else:
        # 处理非分页数据
        df = result
        if "datetime" in df.columns:
            df["datetime"] = df["datetime"].astype(str)
        return {"rows": df.to_dict(orient="records")}


@router.get("/daily")
def daily(code: str = Query(...), start: str = Query(None), end: str = Query(None), interval: str = Query("1D"),
               page: int = Query(None, ge=1, description="页码，从1开始"),
               page_size: int = Query(None, ge=1, le=1000, description="每页数据量，最大1000条")):
    # 根据interval参数设置默认的查询时间范围
    now = datetime.now()
    today = datetime(now.year, now.month, now.day)
    
    if not start and not end:
        if interval == "1D":
            # 1D: 默认查询最近1个月的数据
            start_dt = today - timedelta(days=30)
            end_dt = now
        elif interval == "1W":
            # 1W: 默认查询最近6个月的数据
            start_dt = today - timedelta(days=180)
            end_dt = now
        elif interval == "1M":
            # 1M: 默认查询最近2年的数据
            start_dt = today - timedelta(days=730)
            end_dt = now
        else:
            # 默认查询最近1个月的数据
            start_dt = today - timedelta(days=30)
            end_dt = now
    else:
        # 将字符串类型的日期时间转换为datetime对象
        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # 尝试其他常见格式
            try:
                start_dt = datetime.strptime(start, "%Y-%m-%d")
                end_dt = datetime.strptime(end, "%Y-%m-%d")
            except ValueError:
                start_dt = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S")
                end_dt = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S")
            
    result = get_daily_candles(code, start_dt, end_dt, interval, page, page_size)
    
    # 处理分页数据
    if isinstance(result, tuple) and len(result) == 2:
        df, total_count = result
        if "datetime" in df.columns:
            df["datetime"] = df["datetime"].astype(str)
        return {
            "rows": df.to_dict(orient="records"),
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "has_more": page * page_size < total_count
        }
    else:
        # 处理非分页数据
        df = result
        if "datetime" in df.columns:
            df["datetime"] = df["datetime"].astype(str)
        return {"rows": df.to_dict(orient="records")}

@router.get("/intraday")
def intraday(code: str = Query(...), start: str = Query(...), end: str = Query(...),
                  page: int = Query(None, ge=1, description="页码，从1开始"),
                  page_size: int = Query(None, ge=1, le=1000, description="每页数据量，最大1000条")):
    # 将字符串类型的日期时间转换为datetime对象
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        # 尝试其他常见格式
        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d")
            end_dt = datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            start_dt = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S")
            end_dt = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S")
            
    result = get_intraday(code, start_dt, end_dt, page, page_size)
    
    # 处理分页数据
    if isinstance(result, tuple) and len(result) == 2:
        df, total_count = result
        if "datetime" in df.columns:
            df["datetime"] = df["datetime"].astype(str)
        return {
            "rows": df.to_dict(orient="records"),
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "has_more": page * page_size < total_count
        }
    else:
        # 处理非分页数据
        df = result
        if "datetime" in df.columns:
            df["datetime"] = df["datetime"].astype(str)
        return {"rows": df.to_dict(orient="records")}

# 添加刷新缓存的API端点
@router.post("/refresh-cache")
def refresh_market_cache(code: str = Query(None, description="可选的股票代码，不提供则刷新所有缓存")):
    """
    刷新市场数据缓存
    
    Args:
        code: 可选的股票代码，如提供则只刷新该代码的缓存
    
    Returns:
        刷新结果信息
    """
    from ..services.market_service import refresh_market_data_cache
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        refresh_market_data_cache(code)
        # 成功刷新市场数据缓存的信息已省略，以减少日志输出
        return {"status": "success", "message": f"市场数据缓存已刷新"}
    except Exception as e:
        logger.error(f"刷新市场数据缓存失败: {e}")
        return {"status": "error", "message": str(e)}
