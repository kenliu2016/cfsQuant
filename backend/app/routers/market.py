from fastapi import APIRouter, Query, HTTPException
from ..services.market_service import get_candles, get_daily_candles, get_intraday, refresh_market_data_cache, get_batch_candles
from datetime import datetime, timedelta
import pandas as pd
import logging

# 配置日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market", tags=["market"])

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
    尝试多种格式解析日期时间字符串
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
    
    if default is not None:
        return default
    
    raise ValueError(f"无法解析日期时间: {dt_str}")

@router.get("/candles")
def candles(code: str = Query(...), start: str = Query(None), end: str = Query(None), interval: str = Query("1m"), 
                 page: int = Query(None, ge=1, description="页码，从1开始"), 
                 page_size: int = Query(None, ge=1, le=1000, description="每页数据量，最大1000条")):
    logger.info(f"接收到candles请求: code={code}, start={start}, end={end}, interval={interval}, page={page}, page_size={page_size}")
    
    # 根据interval参数设置默认的查询时间范围
    now_raw = datetime.now()
    today = datetime(now_raw.year, now_raw.month, now_raw.day)

    if not start and not end:
        logger.info(f"未提供start和end参数，使用默认时间范围")
        if interval == "1m":
            # 1m: 默认查询当天的数据
            start_dt = today
            end_dt = now_raw
        elif interval == "5m":
            # 5m: 默认查询最近5天的数据
            start_dt = today - timedelta(days=4)
            end_dt = now_raw
        elif interval == "15m":
            # 15m: 默认查询最近15天的数据
            start_dt = today - timedelta(days=14)
            end_dt = now_raw
        elif interval == "30m":
            # 30m: 默认查询最近30天的数据
            start_dt = today - timedelta(days=29)
            end_dt = now_raw
        elif interval == "1h" or interval == "60m":
            # 1h或60m: 默认查询最近60天的数据
            start_dt = today - timedelta(days=59)
            end_dt = now_raw
        elif interval == "4h":
            # 4h: 默认查询最近90天的数据
            start_dt = today - timedelta(days=89)
            end_dt = now_raw
        elif interval == "1D":
            # 1D: 默认查询最近2个月的数据
            start_dt = today - timedelta(days=60)
            end_dt = now_raw
        elif interval == "1W":
            # 1W: 默认查询最近8个月的数据
            start_dt = today - timedelta(days=240)
            end_dt = now_raw
        elif interval == "1M":
            # 1M: 默认查询最近3年的数据
            start_dt = today - timedelta(days=1095)
            end_dt = now_raw
        else:
            # 默认查询最近1个月的数据
            start_dt = today - timedelta(days=30)
            end_dt = now_raw
    else:
        # 将字符串类型的日期时间转换为datetime对象
        try:
            start_dt = parse_datetime(start)
            end_dt = parse_datetime(end, datetime.now())
        except ValueError:
            logger.error(f"日期时间格式错误: start={start}, end={end}")
            raise HTTPException(status_code=400, detail="日期时间格式错误，请使用YYYY-MM-DD HH:MM:SS或YYYY-MM-DDTHH:MM:SS格式")

    logger.info(f"查询参数: code={code}, start_dt={start_dt}, end_dt={end_dt}, interval={interval}")
    result = get_candles(code, start_dt, end_dt, interval, page, page_size)

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
        context = f"candles - code={code}, interval={interval}"
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
        context = f"candles - code={code}, interval={interval}"
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

@router.get("/daily")
def daily(code: str = Query(...), start: str = Query(None), end: str = Query(None), interval: str = Query("1D"),
               page: int = Query(None, ge=1, description="页码，从1开始"),
               page_size: int = Query(None, ge=1, le=1000, description="每页数据量，最大1000条")):
    logger.info(f"接收到daily请求: code={code}, start={start}, end={end}, interval={interval}, page={page}, page_size={page_size}")
    
    # 根据interval参数设置默认的查询时间范围
    now = datetime.now()
    today = datetime(now.year, now.month, now.day)
    
    if not start and not end:
        logger.info(f"未提供start和end参数，使用默认时间范围")
        if interval == "1D":
            # 1D: 默认查询最近2个月的数据
            start_dt = today - timedelta(days=60)
            end_dt = now
        elif interval == "1W":
            # 1W: 默认查询最近8个月的数据
            start_dt = today - timedelta(days=240)
            end_dt = now
        elif interval == "1M":
            # 1M: 默认查询最近3年的数据
            start_dt = today - timedelta(days=1095)
            end_dt = now
        else:
            # 默认查询最近1个月的数据
            start_dt = today - timedelta(days=30)
            end_dt = now
    else:
        # 将字符串类型的日期时间转换为datetime对象
        try:
            start_dt = parse_datetime(start)
            end_dt = parse_datetime(end, datetime.now())
        except ValueError:
            logger.error(f"日期时间格式错误: start={start}, end={end}")
            raise HTTPException(status_code=400, detail="日期时间格式错误，请使用YYYY-MM-DD HH:MM:SS或YYYY-MM-DDTHH:MM:SS格式")
        
    logger.info(f"查询参数: code={code}, start_dt={start_dt}, end_dt={end_dt}, interval={interval}")
    result = get_daily_candles(code, start_dt, end_dt, interval, page, page_size)
    
    # 处理分页数据
    if isinstance(result, tuple) and len(result) == 2:
        df, total_count = result
        context = f"daily - code={code}, interval={interval}"
        processed_df = process_market_data(df, context)
        
        response = {
            "rows": processed_df.to_dict(orient="records"),
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "has_more": page * page_size < total_count
        }
        
        logger.info(f"返回daily响应: rows={len(response['rows'])}, total_count={total_count}")
        return response
    else:
        # 处理非分页数据
        df = result
        context = f"daily - code={code}, interval={interval}"
        processed_df = process_market_data(df, context)
        
        response = {"rows": processed_df.to_dict(orient="records")}
        logger.info(f"返回非分页daily响应: rows={len(response['rows'])}")
        return response

@router.get("/intraday")
def intraday(code: str = Query(...), start: str = Query(...), end: str = Query(...),
                  page: int = Query(None, ge=1, description="页码，从1开始"),
                  page_size: int = Query(None, ge=1, le=1000, description="每页数据量，最大1000条")):
    logger.info(f"接收到intraday请求: code={code}, start={start}, end={end}, page={page}, page_size={page_size}")
    
    # 将字符串类型的日期时间转换为datetime对象
    try:
        start_dt = parse_datetime(start)
        end_dt = parse_datetime(end)
    except ValueError:
        logger.error(f"日期时间格式错误: start={start}, end={end}")
        raise HTTPException(status_code=400, detail="日期时间格式错误，请使用YYYY-MM-DD HH:MM:SS或YYYY-MM-DDTHH:MM:SS格式")

    logger.info(f"查询参数: code={code}, start_dt={start_dt}, end_dt={end_dt}")
    result = get_intraday(code, start_dt, end_dt, page, page_size)

    # 处理分页数据
    if isinstance(result, tuple) and len(result) == 2:
        df, total_count = result
        context = f"intraday - code={code}"
        processed_df = process_market_data(df, context)
        
        response = {
            "rows": processed_df.to_dict(orient="records"),
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "has_more": page * page_size < total_count
        }
        
        logger.info(f"返回intraday响应: rows={len(response['rows'])}, total_count={total_count}")
        return response
    else:
        # 处理非分页数据
        df = result
        context = f"intraday - code={code}"
        processed_df = process_market_data(df, context)
        
        response = {"rows": processed_df.to_dict(orient="records")}
        logger.info(f"返回非分页intraday响应: rows={len(response['rows'])}")
        return response

@router.get("/batch-candles")
def batch_candles(codes: str = Query(..., description="股票代码列表，用逗号分隔"),
                  interval: str = Query("1m", description="时间间隔"),
                  limit: int = Query(2, ge=1, description="每个股票返回的bar数量，默认返回最近2个bar的数据"),
                  timestamp: str = Query(None, description="时间戳，用于缓存优化，精确到分钟")):
    """
    批量获取多个股票代码的最新K线数据
    """
    logger.info(f"接收到batch-candles请求: codes={codes}, interval={interval}, limit={limit}, timestamp={timestamp}")
    
    # 将逗号分隔的字符串转换为列表
    code_list = [code.strip() for code in codes.split(",") if code.strip()]
    logger.info(f"解析后的股票代码列表: {code_list}")
    
    # 调用服务层的批量查询函数，传递limit参数和timestamp参数
    df = get_batch_candles(code_list, interval, limit, timestamp)
    
    # 处理结果
    context = f"batch-candles - codes={codes}, interval={interval}"
    processed_df = process_market_data(df, context)
    
    # 将结果转换为字典，键为股票代码，值为数据列表（当有多个bar时）
    result_dict = {}
    if not processed_df.empty and 'code' in processed_df.columns:
        # 按股票代码分组
        for code, group in processed_df.groupby('code'):
            # 转换为字典列表
            result_dict[code] = group.to_dict(orient='records')
    
    logger.info(f"返回batch-candles响应: 包含{len(result_dict)}个股票代码的数据")
    return result_dict

@router.post("/refresh-cache")
def refresh_market_cache(code: str = Query(None, description="可选的股票代码，不提供则刷新所有缓存")):
    """
    刷新市场数据缓存
    
    Args:
        code: 可选的股票代码，如提供则只刷新该代码的缓存
    
    Returns:
        刷新结果信息
    """
    logger.info(f"接收到refresh-cache请求: code={code}")
    
    try:
        refresh_market_data_cache(code)
        logger.info("市场数据缓存刷新成功")
        return {"status": "success", "message": f"市场数据缓存已刷新"}
    except Exception as e:
        logger.error(f"刷新市场数据缓存失败: {str(e)}")
        return {"status": "error", "message": str(e)}
