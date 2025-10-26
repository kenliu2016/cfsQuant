"""
VE（波动率效率）指标API路由模块
提供VE指标的查询接口
"""

from fastapi import APIRouter, HTTPException, Query, Request, Depends
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from common.logger import LoggerFactory

# 使用项目统一的日志工具
logger = LoggerFactory.get_logger("routers.ve_indicator")

from ..services.ve_indicator_service import (
    get_ve_data,
    get_latest_ve,
    get_ve_summary
)
# from ..main.dependencies import require_user

router = APIRouter(prefix="/api/ve", tags=["ve-indicator"])


@router.get("/data")
def get_ve_data_endpoint(
    symbol: str = Query(..., description="交易对符号，例如BTCUSDT"),
    timeframe: str = Query("1h", description="时间周期，支持1m, 5m, 15m, 1h, 4h, 1d等"),
    limit: int = Query(100, ge=1, le=1000, description="返回数据条数限制"),
    start_time: str = Query(None, description="开始时间，格式：YYYY-MM-DD HH:MM:SS"),
    end_time: str = Query(None, description="结束时间，格式：YYYY-MM-DD HH:MM:SS"),
    request: Request = None
):
    """
    获取VE指标数据
    
    Args:
        symbol: 交易对符号
        timeframe: 时间周期
        limit: 数据条数限制
        start_time: 开始时间
        end_time: 结束时间
        
    Returns:
        VE指标数据列表
    """
    logger.info(f"接收到VE指标数据请求: symbol={symbol}, timeframe={timeframe}, limit={limit}")
    
    try:
        # 调用服务层获取数据
        df = get_ve_data(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            start_time=start_time,
            end_time=end_time
        )
        
        if df.empty:
            logger.info(f"未找到VE指标数据: symbol={symbol}, timeframe={timeframe}")
            return {
                "rows": [],
                "total_count": 0,
                "message": "未找到VE指标数据"
            }
        
        # 转换为字典列表格式
        result = df.to_dict(orient="records")
        
        # 处理datetime字段，确保可JSON序列化
        for item in result:
            if 'datetime' in item and hasattr(item['datetime'], 'isoformat'):
                item['datetime'] = item['datetime'].isoformat()
            if 'created_at' in item and hasattr(item['created_at'], 'isoformat'):
                item['created_at'] = item['created_at'].isoformat()
        
        logger.info(f"成功返回VE指标数据: symbol={symbol}, 数据量={len(result)}")
        
        return {
            "rows": result,
            "total_count": len(result)
        }
        
    except Exception as e:
        logger.error(f"获取VE指标数据失败: symbol={symbol}, timeframe={timeframe}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取VE指标数据失败: {str(e)}")


@router.get("/latest")
def get_latest_ve_endpoint(
    symbol: str = Query(..., description="交易对符号，例如BTCUSDT"),
    timeframe: str = Query("1h", description="时间周期，支持1m, 5m, 15m, 1h, 4h, 1d等"),
    request: Request = None
):
    """
    获取最新的VE指标值
    
    Args:
        symbol: 交易对符号
        timeframe: 时间周期
        
    Returns:
        最新的VE指标数据
    """
    logger.info(f"接收到最新VE指标请求: symbol={symbol}, timeframe={timeframe}")
    
    try:
        # 调用服务层获取最新数据
        result = get_latest_ve(symbol=symbol, timeframe=timeframe)
        
        if not result:
            logger.info(f"未找到最新的VE指标数据: symbol={symbol}, timeframe={timeframe}")
            return {
                "data": {},
                "message": "未找到最新的VE指标数据"
            }
        
        logger.info(f"成功返回最新VE指标: symbol={symbol}, ve={result.get('ve', 0)}")
        
        return {
            "data": result
        }
        
    except Exception as e:
        logger.error(f"获取最新VE指标失败: symbol={symbol}, timeframe={timeframe}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取最新VE指标失败: {str(e)}")


@router.get("/summary")
def get_ve_summary_endpoint(
    timeframe: str = Query("1h", description="时间周期，支持1m, 5m, 15m, 1h, 4h, 1d等"),
    limit: int = Query(50, ge=1, le=200, description="返回交易对数量限制"),
    exchange: str = Query(None, description="交易所过滤，例如binance"),
    request: Request = None
):
    """
    获取VE指标汇总数据（按交易对分组的最新VE值）
    
    Args:
        timeframe: 时间周期
        limit: 交易对数量限制
        exchange: 交易所过滤
        
    Returns:
        VE指标汇总数据
    """
    logger.info(f"接收到VE指标汇总请求: timeframe={timeframe}, limit={limit}, exchange={exchange}")
    
    try:
        # 调用服务层获取汇总数据
        df = get_ve_summary(
            timeframe=timeframe,
            limit=limit,
            exchange=exchange
        )
        
        if df.empty:
            logger.info(f"未找到VE指标汇总数据: timeframe={timeframe}")
            return {
                "rows": [],
                "total_count": 0,
                "message": "未找到VE指标汇总数据"
            }
        
        # 转换为字典列表格式
        result = df.to_dict(orient="records")
        
        # 处理datetime字段，确保可JSON序列化
        for item in result:
            if 'datetime' in item and hasattr(item['datetime'], 'isoformat'):
                item['datetime'] = item['datetime'].isoformat()
            if 'created_at' in item and hasattr(item['created_at'], 'isoformat'):
                item['created_at'] = item['created_at'].isoformat()
        
        logger.info(f"成功返回VE指标汇总数据: timeframe={timeframe}, 交易对数量={len(result)}")
        
        return {
            "rows": result,
            "total_count": len(result)
        }
        
    except Exception as e:
        logger.error(f"获取VE指标汇总数据失败: timeframe={timeframe}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取VE指标汇总数据失败: {str(e)}")


@router.get("/dashboard")
def get_ve_dashboard_data(
    timeframe: str = Query("1h", description="时间周期"),
    limit: int = Query(20, ge=1, le=100, description="返回交易对数量限制"),
    exchange: str = Query("binance", description="交易所"),
    request: Request = None
):
    """
    获取Dashboard专用的VE指标数据格式
    
    Args:
        timeframe: 时间周期
        limit: 交易对数量限制
        exchange: 交易所
        
    Returns:
        Dashboard格式的VE指标数据
    """
    logger.info(f"接收到Dashboard VE指标请求: timeframe={timeframe}, limit={limit}, exchange={exchange}")
    
    try:
        # 获取VE指标汇总数据
        df = get_ve_summary(
            timeframe=timeframe,
            limit=limit,
            exchange=exchange
        )
        
        if df.empty:
            logger.info(f"未找到Dashboard VE指标数据: timeframe={timeframe}")
            return {
                "rows": [],
                "total_count": 0
            }
        
        # 转换为Dashboard需要的格式
        dashboard_data = []
        for _, row in df.iterrows():
            dashboard_item = {
                "symbol": row['symbol'],
                "ve": float(row['ve']) if pd.notna(row['ve']) else 0.0,
                "actualVolatility": float(row['actual_volatility']) if pd.notna(row['actual_volatility']) else 0.0,
                "expectedVolatility": float(row['expected_volatility']) if pd.notna(row['expected_volatility']) else 0.0,
                "volumeEfficiency": float(row['volume_efficiency']) if pd.notna(row['volume_efficiency']) else 0.0,
                "datetime": row['datetime'].isoformat() if hasattr(row['datetime'], 'isoformat') else str(row['datetime'])
            }
            dashboard_data.append(dashboard_item)
        
        logger.info(f"成功返回Dashboard VE指标数据: 交易对数量={len(dashboard_data)}")
        
        return {
            "rows": dashboard_data,
            "total_count": len(dashboard_data)
        }
        
    except Exception as e:
        logger.error(f"获取Dashboard VE指标数据失败: timeframe={timeframe}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取Dashboard VE指标数据失败: {str(e)}")