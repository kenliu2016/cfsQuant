from fastapi import APIRouter, HTTPException
import numpy as np
import logging
from ..services.runs_service import recent_runs, run_detail, get_grid_levels, delete_run, batch_delete_runs, get_run_equity, get_run_trades, get_run_klines
from fastapi import HTTPException, APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["runs"])

# 定义批量删除请求模型
class BatchDeleteRequest(BaseModel):
    ids: list[str]

# 配置日志
logger = logging.getLogger(__name__)

# 辅助函数：递归将NumPy类型转换为Python原生类型
def convert_numpy_types(data):
    if isinstance(data, (np.integer, np.int64, np.int32)):
        return int(data)
    elif isinstance(data, (np.floating, np.float64, np.float32)):
        return float(data)
    elif isinstance(data, np.ndarray):
        return data.tolist()
    elif isinstance(data, dict):
        return {k: convert_numpy_types(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_numpy_types(item) for item in data]
    return data

@router.get("/runs")
async def runs(limit: int = 20, page: int = 1, code: str = None, strategy: str = None, sortField: str = None, sortOrder: str = None):
    result = recent_runs(limit=limit, page=page, code=code, strategy=strategy, sortField=sortField, sortOrder=sortOrder)
    rows = result['rows'].to_dict(orient="records")
    # 确保所有数据都是可JSON序列化的Python原生类型
    processed_rows = convert_numpy_types(rows)
    processed_total = convert_numpy_types(result['total'])
    return {
        "rows": processed_rows,
        "total": processed_total
    }

@router.get("/runs/grid_levels")
async def get_grid_levels_endpoint(run_id: str):
    logger.debug(f"接收到grid_levels请求，run_id: {run_id}")
    # 获取网格级别数据
    grid_levels_data = get_grid_levels(run_id)
    logger.debug(f"获取网格级别数据完成，数据数量: {len(grid_levels_data)}")
    # 确保所有数据都是可JSON序列化的Python原生类型
    processed_data = convert_numpy_types(grid_levels_data)
    return processed_data

@router.get("/runs/{run_id}")
async def runs_detail(run_id: str):
    # 调用服务层获取回测详情数据（只返回基本信息和指标）
    detail_data = run_detail(run_id)
    # 确保所有数据都是可JSON序列化的Python原生类型
    processed_data = convert_numpy_types(detail_data)
    return processed_data

# 获取回测equity曲线数据
@router.get("/runs/{run_id}/equity")
async def get_run_equity_endpoint(run_id: str, limit: int = 1000):
    # 调用服务层获取equity数据
    equity_data = get_run_equity(run_id, limit)
    # 确保所有数据都是可JSON序列化的Python原生类型
    processed_data = convert_numpy_types(equity_data)
    return processed_data

# 获取回测交易记录数据
@router.get("/runs/{run_id}/trades")
async def get_run_trades_endpoint(run_id: str, limit: int = 1000):
    # 调用服务层获取交易记录数据
    trades_data = get_run_trades(run_id, limit)
    # 确保所有数据都是可JSON序列化的Python原生类型
    processed_data = convert_numpy_types(trades_data)
    return processed_data

# 获取回测K线数据
@router.get("/runs/{run_id}/klines")
async def get_run_klines_endpoint(run_id: str, limit: int = 2000):
    # 调用服务层获取K线数据
    klines_data = get_run_klines(run_id, limit)
    # 确保所有数据都是可JSON序列化的Python原生类型
    processed_data = convert_numpy_types(klines_data)
    return processed_data

@router.delete("/runs/{run_id}")
async def delete_run_endpoint(run_id: str):
    """
    删除指定的回测记录及其关联数据
    
    Args:
        run_id: 要删除的回测ID
        
    Returns:
        包含删除结果的字典
    """
    try:
        logger.info(f"接收到删除回测请求，run_id: {run_id}")
        success = delete_run(run_id)
        if success:
            return {"status": "success", "message": f"回测记录 {run_id} 已成功删除"}
        else:
            raise HTTPException(status_code=500, detail=f"删除回测记录 {run_id} 失败")
    except Exception as e:
        logger.error(f"删除回测记录时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

@router.post("/runs/batch_delete")
async def batch_delete_runs_endpoint(request: BatchDeleteRequest):
    """
    批量删除多个回测记录及其关联数据
    
    Args:
        request: 包含要删除的回测ID列表的请求对象
        
    Returns:
        包含删除结果的字典，记录成功和失败的数量
    """
    try:
        logger.info(f"接收到批量删除回测请求，ids: {request.ids}")
        result = batch_delete_runs(request.ids)
        return {
            "status": "success",
            "message": f"批量删除完成，成功: {result['success']} 条，失败: {result['failed']} 条",
            "result": result
        }
    except Exception as e:
        logger.error(f"批量删除回测记录时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量删除失败: {str(e)}")
