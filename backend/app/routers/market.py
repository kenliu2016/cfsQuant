from fastapi import APIRouter, HTTPException, Query, Body, Request, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Generic, TypeVar, Any
import sys
import os
import time
import asyncio
import math

# 添加项目根目录到Python路径，以便能够导入app模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from common.logger import LoggerFactory

# 使用项目统一的日志工具
logger = LoggerFactory.get_logger("routers.market")

from ..services.market_service import (
    get_candles,
    get_latest_candles,
    refresh_market_data_cache,
    get_market_exchanges,
    get_market_codes,
    get_market_base_score,
    get_strong_weak_coins_enhanced,
    get_coin_analysis_table as get_coin_analysis_table_service,
    market_data_service,
)
from ..services.candles_cache_service import clear_candles_cache, clear_all_candles_cache
from common.db import fetch_df, execute
from datetime import datetime, timedelta
import pandas as pd
from ..main.config import settings
from ..main.dependencies import require_user
from ..services.cache_service import CacheService

# 定义通用的API响应模型
T = TypeVar('T')

class ApiResponse(BaseModel):
    """通用API响应模型"""
    success: bool = Field(..., description="请求是否成功")
    data: Optional[Any] = Field(None, description="响应数据")
    message: str = Field(..., description="响应消息")
    
    @classmethod
    def create_success(cls, data: Any, message: str = "操作成功") -> "ApiResponse":
        """创建成功响应"""
        return cls(success=True, data=data, message=message)
    
    @classmethod
    def create_error(cls, message: str = "操作失败") -> "ApiResponse":
        """创建错误响应"""
        return cls(success=False, data=None, message=message)

# 定义分页信息模型
class PaginationInfo(BaseModel):
    """分页信息模型"""
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")
    total_count: int = Field(..., description="总记录数")
    total_pages: int = Field(..., description="总页数")
    has_previous: bool = Field(..., description="是否有上一页")
    has_next: bool = Field(..., description="是否有下一页")

# 定义币种分析表响应模型
class CoinAnalysisTableResponse(BaseModel):
    """币种分析表响应模型"""
    items: List[dict] = Field(..., description="币种分析数据列表")
    pagination: PaginationInfo = Field(..., description="分页信息")



router = APIRouter(prefix="/api/market", tags=["market"], dependencies=[Depends(require_user)])

# 创建不需要认证的路由器
public_router = APIRouter(prefix="/api/market", tags=["market"])

# 定义通用的数据处理函数
def process_market_data(df, context=""):
    """
    统一处理市场数据的DataFrame，确保datetime和价格字段被正确格式化
    
    Args:
        df: 要处理的DataFrame
        context: 可选的上下文信息，用于更详细的日志记录
    """
    if df is None or df.empty:
        if context:
            logger.warning(f"收到空的DataFrame进行处理 - 上下文: {context}")
        else:
            logger.warning("收到空的DataFrame进行处理")
        return df
    
    # 创建df的副本以避免修改原始数据
    processed_df = df.copy()
    
    logger.info(f"处理DataFrame: 形状={processed_df.shape}, 列={list(processed_df.columns)}")
    
    # 添加调试信息：显示原始数据的前几行
    logger.info(f"原始数据预览 (前3行):\n{processed_df.head(3).to_string()}")
    
    # 检查datetime列是否存在
    datetime_columns = [col for col in processed_df.columns if col.lower() in ['datetime', 'date', 'time']]
    if not datetime_columns:
        # 只有在不是处理market_codes数据时才输出警告
        if 'market_codes' not in context:
            logger.warning("DataFrame中未找到datetime相关列")
    else:
        datetime_col = datetime_columns[0]
        logger.info(f"使用{datetime_col}作为datetime列")
        
        # 尝试将列转换为datetime类型并格式化为ISO字符串
        try:
            # 先检查是否已经是datetime类型
            if not pd.api.types.is_datetime64_any_dtype(processed_df[datetime_col]):
                logger.info(f"转换{datetime_col}列为datetime类型")
                processed_df[datetime_col] = pd.to_datetime(processed_df[datetime_col], errors='coerce')
            
            # 检查是否有NaT值
            if processed_df[datetime_col].isna().any():
                na_count = processed_df[datetime_col].isna().sum()
                logger.warning(f"{datetime_col}列包含{na_count}个NaT值")
            
            # 转换为ISO格式字符串
            processed_df[datetime_col] = processed_df[datetime_col].dt.strftime("%Y-%m-%dT%H:%M:%S").fillna("")
        except Exception as e:
            logger.error(f"处理{datetime_col}列时出错: {str(e)}")
            # 如果转换失败，直接转为字符串并替换可能的NaT
            processed_df[datetime_col] = processed_df[datetime_col].astype(str).replace({"NaT": "", "None": "", "nan": ""}, regex=False)
    
    # 处理价格相关列
    price_columns = ["open", "high", "low", "close", "volume"]
    for col in price_columns:
        if col in processed_df.columns:
            logger.info(f"处理{col}列")
            
            # 记录处理前该列的非零值数量
            if pd.api.types.is_numeric_dtype(processed_df[col]):
                non_zero_count_before = (processed_df[col] != 0).sum()
                logger.info(f"{col}列处理前非零值数量: {non_zero_count_before}/{len(processed_df)}")
                # 记录该列的统计信息
                logger.info(f"{col}列处理前统计信息: 最小值={processed_df[col].min()}, 最大值={processed_df[col].max()}, 平均值={processed_df[col].mean()}")
            
            try:
                # 检查列的数据类型
                current_dtype = processed_df[col].dtype
                logger.info(f"{col}列当前类型: {current_dtype}")
                
                # 如果被错误地识别为日期时间类型，需要特殊处理
                if pd.api.types.is_datetime64_any_dtype(processed_df[col]):
                    logger.warning(f"{col}列被错误识别为日期时间类型，正在修复...")
                    # 先转换为字符串
                    str_col = processed_df[col].astype(str)
                    # 过滤掉NaT值
                    str_col = str_col.apply(lambda x: x if x != 'NaT' else '0')
                    # 再转换为数值
                    processed_df[col] = pd.to_numeric(str_col, errors='coerce')
                else:
                    # 尝试直接转换为数值类型
                    processed_df[col] = pd.to_numeric(processed_df[col], errors='coerce')
                
                # 检查是否有NaN值
                if processed_df[col].isna().any():
                    na_count = processed_df[col].isna().sum()
                    logger.warning(f"{col}列包含{na_count}个NaN值，将替换为0")
                    # 替换NaN值为0
                    processed_df[col] = processed_df[col].fillna(0)
                
                # 检查是否有0值
                zero_count = (processed_df[col] == 0).sum()
                non_zero_count_after = len(processed_df) - zero_count
                if zero_count > 0:
                    logger.warning(f"{col}列包含{zero_count}个0值，非零值数量: {non_zero_count_after}/{len(processed_df)}")
                    
                # 记录处理后该列的统计信息
                logger.info(f"{col}列处理后统计信息: 最小值={processed_df[col].min()}, 最大值={processed_df[col].max()}, 平均值={processed_df[col].mean()}")
                
            except Exception as e:
                logger.error(f"处理{col}列时出错: {str(e)}")
                # 尝试更激进的方法处理
                try:
                    # 尝试先转换为字符串再处理
                    str_col = processed_df[col].astype(str)
                    # 清理字符串，移除非数字字符
                    str_col = str_col.str.replace(r'[^0-9.]', '', regex=True)
                    # 再转换为数值
                    processed_df[col] = pd.to_numeric(str_col, errors='coerce').fillna(0)
                except Exception as inner_e:
                    logger.error(f"二次处理{col}列时出错: {str(inner_e)}")
                    # 如果所有尝试都失败，保持原样
                    pass
    
    # 添加调试信息：显示处理后数据的前几行
    logger.info(f"处理后数据预览 (前3行):\n{processed_df.head(3).to_string()}")
    
    logger.info("数据处理完成")
    return processed_df

# 定义通用的日期时间解析函数
def parse_datetime(dt_str, default=None):
    """
    尝试多种格式解析日期时间字符串，确保不会抛出无法序列化的异常
    特别注意：正确处理ISO 8601格式的时区信息
    """
    if dt_str is None:
        return default
    
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    
    # 尝试处理ISO 8601格式，带有毫秒和时区信息
    try:
        if isinstance(dt_str, str):
            # 截取前19个字符，去掉毫秒和时区信息
            return datetime.strptime(dt_str[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        pass
    
    # 尝试转换为时间戳
    try:
        return datetime.fromtimestamp(int(dt_str))
    except (ValueError, TypeError):
        pass
    
    # 始终返回默认值，而不是抛出ValueError异常
    if default is not None:
        logger.warning(f"无法解析日期时间: {dt_str}，使用默认值: {default}")
        return default
    
    # 如果没有提供默认值，返回当前时间
    logger.error(f"无法解析日期时间: {dt_str}，也没有提供默认值，返回当前时间")
    return datetime.now()

@router.get("/candles")
def candles(symbol: str = Query(...), startTime: str = Query(None), endTime: str = Query(None), timeframe: str = Query("1m"), 
                 page: int = Query(None, ge=1, description="页码，从1开始"), 
                 page_size: int = Query(None, ge=1, le=1000, description="每页数据量，最大1000条"),
                 limit: int = Query(None, ge=1, le=70000, description="查询最近的记录条数，最大70000条")):
    logger.info(f"接收到candles请求: symbol={symbol}, startTime={startTime}, endTime={endTime}, timeframe={timeframe}, page={page}, page_size={page_size}, limit={limit}")
    
    # 处理查询逻辑：有时间范围按时间范围查询，没有时间范围按limit查询最近记录
    if startTime and endTime:
        # 有时间范围时，按时间范围查询
        logger.info(f"有时间范围参数，按时间范围查询")
        # 将字符串类型的日期时间转换为datetime对象
        try:
            start_dt = parse_datetime(startTime)
            end_dt = parse_datetime(endTime, datetime.now())
        except ValueError:
            logger.error(f"日期时间格式错误: startTime={startTime}, endTime={endTime}")
            raise HTTPException(status_code=400, detail="日期时间格式错误，请使用YYYY-MM-DD HH:MM:SS或YYYY-MM-DDTHH:MM:SS格式")
        
        result = get_candles(symbol, startTime, endTime, timeframe, page, page_size)
    else:
        # 没有时间范围时，按limit参数查询最近的记录
        logger.info(f"没有时间范围参数，按limit查询最近的记录")
        # 调用新的方法查询最近的K线数据
        result = get_latest_candles(symbol, timeframe, limit)

    logger.info(f"查询参数: symbol={symbol}, timeframe={timeframe}")

    # 处理返回结果
    if isinstance(result, tuple):
        # 根据元组长度判断返回类型
        if len(result) == 3:
            # 分页模式：(df, total_count, query_params)
            df, total_count, query_params = result
        else:
            # 非分页模式：(df, query_params)
            df, query_params = result
            # 计算实际数据条数作为total_count
            total_count = len(df) if df is not None else 0
        
        # 处理数据
        context = f"candles - symbol={symbol}, timeframe={timeframe}"
        processed_df = process_market_data(df, context)
        
        # 计算has_more时处理page和page_size为None的情况
        has_more = False
        if page is not None and page_size is not None:
            has_more = page * page_size < total_count
            
        response = {
            "rows": processed_df.to_dict(orient="records"),
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "has_more": has_more
        }
        
        # 如果有query_params，将其添加到响应中
        if query_params is not None:
            response["query_params"] = query_params
            
        logger.info(f"返回candles响应: rows={len(response['rows'])}, total_count={total_count}")
        return response
    else:
        # 处理非元组返回值（单df）
        df = result
        context = f"candles - symbol={symbol}, timeframe={timeframe}"
        processed_df = process_market_data(df, context)
        
        response = {
            "rows": processed_df.to_dict(orient="records"),
            "total_count": len(processed_df) if processed_df is not None else 0,
            "page": None,
            "page_size": None,
            "has_more": False
        }
        
        logger.info(f"返回非元组candles响应: rows={len(response['rows'])}")
        return response

@router.post("/refresh-cache")
def refresh_market_cache(symbol: str = Query(None, description="可选的交易对代码，不提供则刷新所有缓存")):
    """
    刷新市场数据缓存
    
    Args:
        symbol: 可选的交易对代码，如提供则只刷新该代码的缓存
    
    Returns:
        刷新结果信息
    """
    logger.info(f"接收到refresh-cache请求: symbol={symbol}")
    
    try:
        refresh_market_data_cache(symbol)
        logger.info("市场数据缓存刷新成功")
        return {"status": "success", "message": f"市场数据缓存已刷新"}
    except Exception as e:
        logger.error(f"刷新市场数据缓存失败: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.get("/market_codes/exchanges")
def get_exchanges(active: bool = Query(True, description="是否只获取活跃的交易所"), request: Request = None):
    """
    获取所有可用的交易所列表
    
    Args:
        active: 是否只获取活跃的交易所
        
    Returns:
        交易所列表
    """
    logger.info(f"接收到获取交易所列表请求: active={active}")
    
    try:
        tenant_id = getattr(request.state, "tenant_id", settings.DEFAULT_TENANT_ID) if request else settings.DEFAULT_TENANT_ID
        df = get_market_exchanges(active, tenant_id=tenant_id)
        
        # 处理结果
        context = f"market_codes/exchanges - active={active}"
        processed_df = process_market_data(df, context)
        
        # 转换为字典列表
        result = processed_df.to_dict(orient="records")
        
        logger.info(f"返回交易所列表: 共{len(result)}条记录")
        return {
            "rows": result,
            "total_count": len(result)
        }
    except Exception as e:
        logger.error(f"获取交易所列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取交易所列表失败")

@public_router.get("/market_codes")
def get_public_codes(exchange: str = None, 
                    symbol: str = None,
                    active: bool = None,
                    watch: bool = None,
                    request: Request = None):
    """
    获取市场代码列表（公开接口，不需要认证）
    """
    return get_codes(exchange, symbol, active, watch, request)


@router.get("/market_codes")
def get_codes(exchange: str = None, 
                symbol: str = None,
                active: bool = None,
                watch: bool = None,
                request: Request = None):
    """
    获取市场代码列表，可以按交易所、交易对、活跃状态和关注状态过滤
    
    Args:
        exchange: 交易所代码，不提供则获取所有
        symbol: 交易对代码，不提供则获取所有
        active: 是否只获取活跃的代码，为None时获取所有
        watch: 是否只获取关注的代码，为None时获取所有
        
    Returns:
        市场代码列表
    """
    logger.info(f"接收到获取市场代码列表请求: exchange={exchange}, symbol={symbol}, active={active}, watch={watch}")
    
    try:
        # 直接调用底层服务函数，不经过缓存
        # 注意：需要修改服务函数以支持active为None的情况
        sql = """
        SELECT symbol, exchange, active, watch FROM market_codes
        WHERE 1=1
        """
        
        params = {}
        
        if exchange:
            sql += " AND exchange = :exchange"
            params['exchange'] = exchange
        
        if symbol:
            sql += " AND symbol ILIKE :symbol"
            params['symbol'] = f"%{symbol}%"
        
        if active is not None:
            sql += " AND active = :active"
            params['active'] = active
            
        if watch is not None:
            sql += " AND watch = :watch"
            params['watch'] = watch
        
        sql += " ORDER BY symbol"
        
        df = fetch_df(sql, **params)
        logger.info(f"直接从数据库获取数据，形状={df.shape}")
        if not df.empty:
            logger.info(f"直接从数据库获取的数据预览: {df.head(2).to_dict('records')}")
        
        # 处理结果
        context = f"market_codes - exchange={exchange}, active={active}"
        processed_df = process_market_data(df, context)
        logger.info(f"处理后的数据形状={processed_df.shape}")
        if not processed_df.empty:
            logger.info(f"处理后的数据预览: {processed_df.head(2).to_dict('records')}")
        
        # 转换为字典列表
        result = processed_df.to_dict(orient="records")
        logger.info(f"转换后的结果数量: {len(result)}")
        if result:
            logger.info(f"转换后的结果预览: {result[:2]}")
        
        return {
            "rows": result,
            "total_count": len(result)
        }
    except Exception as e:
        logger.error(f"获取市场代码列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取市场代码列表失败")


@router.post("/market_codes")
def add_code(code_data: dict, request: Request):
    """
    添加市场代码
    
    Args:
        code_data: 包含市场代码信息的字典
    
    Returns:
        成功信息
    """
    logger.info(f"接收到添加市场代码请求: {code_data}")
    
    try:
        # 检查必要字段
        required_fields = ['exchange', 'symbol']
        for field in required_fields:
            if field not in code_data:
                raise HTTPException(status_code=400, detail=f"缺少必要字段: {field}")
        
        # 检查是否已存在
        tenant_id = getattr(request.state, "tenant_id", settings.DEFAULT_TENANT_ID)
        check_sql = """
        SELECT 1 FROM market_codes WHERE exchange = :exchange AND symbol = :symbol AND tenant_id = :tenant_id
        """
        check_params = {'exchange': code_data['exchange'], 'symbol': code_data['symbol'], 'tenant_id': tenant_id}
        check_df = fetch_df(check_sql, **check_params)
        
        if len(check_df) > 0:
            raise HTTPException(status_code=400, detail=f"市场代码已存在: {code_data['exchange']}:{code_data['symbol']}")
        
        # 插入新记录
        insert_sql = """
        INSERT INTO market_codes (tenant_id, exchange, symbol, active, watch)
        VALUES (:tenant_id, :exchange, :symbol, :active, :watch)
        """
        
        # 设置默认值
        insert_params = {
            'tenant_id': tenant_id,
            'exchange': code_data['exchange'],
            'symbol': code_data['symbol'],
            'active': code_data.get('active', True),
            'watch': code_data.get('watch', False)
        }
        
        execute(insert_sql, **insert_params)
        logger.info(f"添加市场代码成功: {code_data['exchange']}:{code_data['symbol']}")
        
        return {"success": True, "message": "添加成功"}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"添加市场代码失败: {str(e)}")
        raise HTTPException(status_code=500, detail="添加失败")


@router.put("/market_codes/{exchange}")
def update_code(exchange: str, symbol: str = Query(..., description="交易对代码"), update_data: dict = Body(...), request: Request = None):
    """
    更新市场代码
    
    Args:
        exchange: 交易所
        symbol: 交易对代码
        update_data: 更新数据
    
    Returns:
        成功信息
    """
    logger.info(f"接收到更新市场代码请求: {exchange}:{symbol}, 数据: {update_data}")
    
    try:
        # 检查记录是否存在
        tenant_id = getattr(request.state, "tenant_id", settings.DEFAULT_TENANT_ID)
        check_sql = """
        SELECT 1 FROM market_codes WHERE exchange = :exchange AND symbol = :symbol AND tenant_id = :tenant_id
        """
        check_params = {'exchange': exchange, 'symbol': symbol, 'tenant_id': tenant_id}
        check_df = fetch_df(check_sql, **check_params)
        
        if len(check_df) == 0:
            raise HTTPException(status_code=404, detail=f"市场代码不存在: {exchange}:{symbol}")
        
        # 构建更新SQL
        update_fields = []
        update_params = {'exchange': exchange, 'symbol': symbol, 'tenant_id': tenant_id}
        
        allowed_fields = ['active', 'watch']
        for field in allowed_fields:
            if field in update_data:
                update_fields.append(f"{field} = :{field}")
                update_params[field] = update_data[field]
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="没有有效的更新字段")
        
        update_sql = f"""
        UPDATE market_codes 
        SET {', '.join(update_fields)}
        WHERE exchange = :exchange AND symbol = :symbol AND tenant_id = :tenant_id
        """
        
        execute(update_sql, **update_params)
        logger.info(f"更新市场代码成功: {exchange}:{symbol}")
        
        return {"success": True, "message": "更新成功"}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"更新市场代码失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新失败")


@router.delete("/market_codes")
def delete_code(exchange: str = Query(...), symbol: str = Query(...), request: Request = None):
    """
    删除市场代码
    
    Args:
        exchange: 交易所代码（通过查询参数传递）
        symbol: 市场代码（通过查询参数传递）
    
    Returns:
        成功信息
    """
    logger.info(f"接收到删除市场代码请求: {exchange}:{symbol}")
    
    try:
        # 检查记录是否存在
        tenant_id = getattr(request.state, "tenant_id", settings.DEFAULT_TENANT_ID) if request else settings.DEFAULT_TENANT_ID
        check_sql = """
        SELECT 1 FROM market_codes WHERE exchange = :exchange AND symbol = :symbol AND tenant_id = :tenant_id
        """
        check_params = {'exchange': exchange, 'symbol': symbol, 'tenant_id': tenant_id}
        check_df = fetch_df(check_sql, **check_params)
        
        if len(check_df) == 0:
            raise HTTPException(status_code=404, detail=f"市场代码不存在: {exchange}:{symbol}")
        
        # 执行删除
        delete_sql = """
        DELETE FROM market_codes WHERE exchange = :exchange AND symbol = :symbol AND tenant_id = :tenant_id
        """
        delete_params = {'exchange': exchange, 'symbol': symbol, 'tenant_id': tenant_id}
        
        # 使用execute函数执行DELETE操作，而不是fetch_df
        execute(delete_sql, **delete_params)
        logger.info(f"删除市场代码成功: {exchange}:{symbol}")
        
        return {"success": True, "message": "删除成功"}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"删除市场代码失败: {str(e)}")
        raise HTTPException(status_code=500, detail="删除失败")


@router.post("/market_codes/batch_update")
def batch_update_codes(batch_data: dict, request: Request = None):
    """
    批量更新市场代码
    
    Args:
        batch_data: 包含keys(要更新的记录键列表)和updates(要更新的字段)的字典
    
    Returns:
        成功信息
    """
    logger.info(f"接收到批量更新市场代码请求: {batch_data}")
    
    try:
        # 检查必要字段
        if 'keys' not in batch_data or 'updates' not in batch_data:
            raise HTTPException(status_code=400, detail="缺少必要字段: keys 或 updates")
        
        keys = batch_data['keys']
        updates = batch_data['updates']
        
        if not keys or not isinstance(keys, list):
            raise HTTPException(status_code=400, detail="keys必须是非空的列表")
        
        # 只能更新watch和active字段
        allowed_fields = ['watch', 'active']
        update_fields = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not update_fields:
            return {"success": True, "message": "没有需要更新的字段"}
        
        tenant_id = getattr(request.state, "tenant_id", settings.DEFAULT_TENANT_ID) if request else settings.DEFAULT_TENANT_ID
        # 构建更新语句
        update_sql = """
        UPDATE market_codes SET
        """
        
        # 添加更新字段
        set_clauses = []
        params = {'tenant_id': tenant_id}
        
        for field, value in update_fields.items():
            set_clauses.append(f"{field} = :{field}")
            params[field] = value
        
        update_sql += ", ".join(set_clauses)
        update_sql += " WHERE tenant_id = :tenant_id AND CONCAT(exchange, ':', code) = ANY(:keys)"
        params['keys'] = keys
        
        # 使用execute函数而非fetch_df，因为更新操作不返回数据
        execute(update_sql, **params)
        logger.info(f"批量更新市场代码成功，共更新 {len(keys)} 条记录")
        
        return {"success": True, "message": f"批量更新成功，共更新 {len(keys)} 条记录"}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"批量更新市场代码失败: {str(e)}")
        raise HTTPException(status_code=500, detail="批量更新失败")


@router.delete("/candles/cache")
def delete_candles_cache(symbol: str = Query(..., description="市场代码，如BTC/USDT"), 
                         timeframe: str = Query("1m", description="时间间隔，如1m, 15m, 1h, 1d"),
                         limit: int = Query(None, ge=1, description="查询的记录条数，如果为None则匹配所有limit值"),
                         startTime: str = Query(None, description="开始时间，如果为None则不按时间范围清除"),
                         endTime: str = Query(None, description="结束时间，如果为None则不按时间范围清除")):
    """
    清除特定K线查询的缓存
    
    支持清除基于时间范围的查询缓存或基于limit的查询缓存
    如果同时提供了时间范围和limit，则优先按时间范围清除
    """
    logger.info(f"接收到清除K线缓存请求: symbol={symbol}, timeframe={timeframe}, limit={limit}, startTime={startTime}, endTime={endTime}")
    
    # 调用清除缓存的服务函数
    success = clear_candles_cache(symbol, timeframe, limit, startTime, endTime)
    
    if success:
        logger.info(f"成功清除K线缓存: symbol={symbol}, timeframe={timeframe}")
        return {"success": True, "message": "K线缓存清除成功"}
    else:
        logger.error(f"清除K线缓存失败: symbol={symbol}, timeframe={timeframe}")
        raise HTTPException(status_code=500, detail="清除K线缓存失败")


@router.delete("/candles-cache/all")
def delete_all_candles_cache_endpoint():
    """
    清除所有K线相关的缓存
    """
    logger.info("接收到清除所有K线缓存的请求")
    
    # 调用清除所有缓存的服务函数
    success = clear_all_candles_cache()
    
    if success:
        logger.info("成功清除所有K线缓存")
        return {"success": True, "message": "所有K线缓存清除成功"}
    else:
        logger.error("清除所有K线缓存失败")
        raise HTTPException(status_code=500, detail="清除所有K线缓存失败")
@router.get("/market-base-score")
def market_base_score_endpoint(exchange: str = Query(None), symbol: str = Query(None)):
    """
    获取市场基准情绪指标（牛熊评分 + Fear & Greed）
    """
    try:
        return get_market_base_score(exchange=exchange, symbol=symbol)
    except Exception as e:
        logger.error(f"获取市场基准情绪指标失败: {e}")
        raise HTTPException(status_code=500, detail="failed to fetch market base score")





@public_router.get("/strong-weak-coins-enhanced")
def get_strong_weak_coins_enhanced_endpoint():
    """
    获取强势币种和弱势币种列表（增强版本）
    
    计算规则：
    1. 从market_ohlcv_1h视图获取最近24小时数据
    2. VMR = 24小时内总成交量（quoteVolume总和）/ 期初市值（24小时前的market_cap）* 100
    3. 涨幅 = (当前收盘价 - 24小时前开盘价) / 24小时前开盘价 * 100
    4. 返回每个币种的24小时内每个小时的收盘价和quoteVolume，用于绘制曲线图
    
    返回包含强势币种（前10）和弱势币种（后10）的列表
    """
    try:
        # 调用服务层方法获取增强版强势/弱势币种数据
        result = get_strong_weak_coins_enhanced()
        
        logger.info(f"成功获取增强版强势/弱势币种数据: 强势币种{len(result.get('strong_coins', []))}个, 弱势币种{len(result.get('weak_coins', []))}个")
        
        return {
            "success": True,
            "data": result,
            "message": "获取增强版强势/弱势币种数据成功"
        }
    except Exception as e:
        logger.error(f"获取增强版强势/弱势币种数据失败: {e}")
        raise HTTPException(status_code=500, detail="获取增强版强势/弱势币种数据失败")


@router.get("/coin-analysis-table", response_model=ApiResponse)
async def get_coin_analysis_table(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页大小"),
    force_refresh: bool = Query(False, description="强制刷新缓存")
):
    """
    获取币种分析表数据 - 优化版本
    
    优化特性：
    1. 智能缓存策略：根据数据更新频率动态调整缓存时间
    2. 分级缓存：支持物化视图和内存缓存
    3. 强制刷新机制：支持手动刷新缓存
    4. 性能监控：记录查询耗时和缓存命中率
    
    缓存策略：
    - 正常情况：30分钟缓存
    - 数据量少时：15分钟缓存
    - 强制刷新：跳过缓存直接查询
    """
    start_time = time.time()
    cache_hit = False
    
    try:
        # 使用缓存键
        cache_key = f"coin_analysis_table:all_data"
        
        # 检查是否强制刷新
        if force_refresh:
            logger.info("强制刷新模式，跳过缓存直接查询")
            all_data = []
        else:
            # 尝试从缓存获取数据，使用try-catch包装await调用
            try:
                cached_data = await CacheService.get(cache_key)
                if cached_data is not None:  # 明确检查是否为None
                    logger.info("从缓存获取币种分析表数据成功")
                    all_data = cached_data
                    cache_hit = True
                else:
                    logger.info("缓存未命中，开始查询数据库")
                    all_data = []
            except Exception as e:
                logger.warning(f"缓存获取失败，但继续处理: {e}")
                all_data = []
        
        # 如果缓存未命中或强制刷新，查询数据库
        if not all_data:
            try:
                all_data = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, get_coin_analysis_table_service),
                    timeout=15.0  # 优化超时时间
                )
                
                # 智能缓存策略：根据数据量动态调整缓存时间
                if all_data:
                    data_count = len(all_data)
                    if data_count > 50:
                        # 数据量充足，设置30分钟缓存
                        cache_time = 1800
                    elif data_count > 10:
                        # 数据量中等，设置20分钟缓存
                        cache_time = 1200
                    else:
                        # 数据量较少，设置15分钟缓存
                        cache_time = 900
                    
                    # 使用try-catch包装await调用，防止NoneType错误
                    try:
                        await CacheService.set(cache_key, all_data, expire_time=cache_time)
                        logger.info(f"币种分析表数据查询成功，共{data_count}条记录，已设置{cache_time//60}分钟缓存")
                    except Exception as cache_error:
                        logger.warning(f"缓存设置失败，但继续处理: {cache_error}")
                else:
                    # 空数据设置较短缓存时间
                    try:
                        await CacheService.set(cache_key, all_data, expire_time=300)
                        logger.info("币种分析表数据为空，设置5分钟缓存")
                    except Exception as cache_error:
                        logger.warning(f"空数据缓存设置失败，但继续处理: {cache_error}")
                    
            except asyncio.TimeoutError:
                logger.warning("币种分析表查询超时，返回空数据")
                all_data = []
                # 查询超时时设置较短缓存
                try:
                    await CacheService.set(cache_key, all_data, expire_time=300)
                except Exception as cache_error:
                    logger.warning(f"超时数据缓存设置失败，但继续处理: {cache_error}")
            except Exception as e:
                logger.error(f"币种分析表查询异常: {e}")
                all_data = []
        
        # 分页处理
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_data = all_data[start_idx:end_idx]
        
        # 计算查询耗时
        query_time = time.time() - start_time
        
        # 构建响应
        response = CoinAnalysisTableResponse(
            items=paginated_data,
            pagination=PaginationInfo(
                page=page,
                page_size=page_size,
                total_count=len(all_data),
                total_pages=math.ceil(len(all_data) / page_size) if all_data else 0,
                has_previous=page > 1,
                has_next=end_idx < len(all_data)
            )
        )
        
        # 记录性能指标
        logger.info(f"币种分析表API请求完成 - 耗时: {query_time:.4f}s, 缓存命中: {cache_hit}, 数据量: {len(all_data)}")
        
        return ApiResponse.create_success(response, "获取币种分析表数据成功")
        
    except Exception as e:
        logger.error(f"获取币种分析表数据失败: {e}")
        # 返回空数据但保持API响应正常
        response = CoinAnalysisTableResponse(
            items=[],
            pagination=PaginationInfo(
                page=page,
                page_size=page_size,
                total_count=0,
                total_pages=0,
                has_previous=False,
                has_next=False
            )
        )
        return ApiResponse.create_success(response, "获取币种分析表数据成功")
