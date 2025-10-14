import numpy as np
import sys
import os

# 添加项目根目录到Python路径，以便能够导入app模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from common.logger import LoggerFactory

# 使用项目统一的日志工具
logger = LoggerFactory.get_logger("routers.runs")

from ..services.runs_service import recent_runs, run_detail, get_grid_levels, delete_run, batch_delete_runs, get_run_equity, get_run_trades, get_run_klines
from fastapi import HTTPException, APIRouter, Request, Depends
from ..main.config import settings
from ..main.dependencies import require_user, require_super_admin
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["runs"], dependencies=[Depends(require_user)])

# 定义批量删除请求模型
class BatchDeleteRequest(BaseModel):
    ids: list[str]

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
async def runs(limit: int = 20, page: int = 1, code: str = None, strategy: str = None, sortField: str = None, sortOrder: str = None, request: Request = None):
    tenant_id = getattr(request.state, "tenant_id", settings.DEFAULT_TENANT_ID) if request else settings.DEFAULT_TENANT_ID
    current_user = getattr(request.state, "user", {}) or {}
    result = recent_runs(
        limit=limit,
        page=page,
        code=code,
        strategy=strategy,
        sortField=sortField,
        sortOrder=sortOrder,
        tenant_id=tenant_id,
        current_user=current_user,
    )
    rows = result['rows'].to_dict(orient="records")
    # 确保所有数据都是可JSON序列化的Python原生类型
    processed_rows = convert_numpy_types(rows)
    processed_total = convert_numpy_types(result['total'])
    return {
        "rows": processed_rows,
        "total": processed_total
    }

@router.get("/runs/grid_levels")
async def get_grid_levels_endpoint(run_id: str, request: Request):
    logger.debug(f"接收到grid_levels请求，run_id: {run_id}")
    # 获取网格级别数据
    tenant_id = getattr(request.state, "tenant_id", settings.DEFAULT_TENANT_ID)
    current_user = getattr(request.state, "user", {}) or {}
    try:
        grid_levels_data = get_grid_levels(run_id, tenant_id=tenant_id, current_user=current_user)
    except ValueError:
        raise HTTPException(status_code=404, detail="run not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="access denied")
    logger.debug(f"获取网格级别数据完成，数据数量: {len(grid_levels_data)}")
    # 确保所有数据都是可JSON序列化的Python原生类型
    processed_data = convert_numpy_types(grid_levels_data)
    return processed_data

@router.get("/runs/{run_id}")
async def runs_detail(run_id: str, request: Request):
    # 调用服务层获取回测详情数据（只返回基本信息和指标）
    tenant_id = getattr(request.state, "tenant_id", settings.DEFAULT_TENANT_ID)
    current_user = getattr(request.state, "user", {}) or {}
    try:
        detail_data = run_detail(run_id, tenant_id=tenant_id, current_user=current_user)
    except ValueError:
        raise HTTPException(status_code=404, detail="run not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="access denied")
    # 确保所有数据都是可JSON序列化的Python原生类型
    processed_data = convert_numpy_types(detail_data)
    return processed_data

# 获取回测equity曲线数据
@router.get("/runs/{run_id}/equity")
async def get_run_equity_endpoint(run_id: str, limit: int = 1000, request: Request = None):
    # 调用服务层获取equity数据
    tenant_id = getattr(request.state, "tenant_id", settings.DEFAULT_TENANT_ID) if request else settings.DEFAULT_TENANT_ID
    current_user = getattr(request.state, "user", {}) or {}
    try:
        equity_data = get_run_equity(run_id, limit, tenant_id=tenant_id, current_user=current_user)
    except ValueError:
        raise HTTPException(status_code=404, detail="run not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="access denied")
    # 确保所有数据都是可JSON序列化的Python原生类型
    processed_data = convert_numpy_types(equity_data)
    return processed_data

# 获取回测交易记录数据
@router.get("/runs/{run_id}/trades")
async def get_run_trades_endpoint(run_id: str, limit: int = 1000, request: Request = None):
    # 调用服务层获取交易记录数据
    tenant_id = getattr(request.state, "tenant_id", settings.DEFAULT_TENANT_ID) if request else settings.DEFAULT_TENANT_ID
    current_user = getattr(request.state, "user", {}) or {}
    try:
        trades_data = get_run_trades(run_id, limit, tenant_id=tenant_id, current_user=current_user)
    except ValueError:
        raise HTTPException(status_code=404, detail="run not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="access denied")
    # 确保所有数据都是可JSON序列化的Python原生类型
    processed_data = convert_numpy_types(trades_data)
    return processed_data

# 获取回测K线数据
@router.get("/runs/{run_id}/klines")
async def get_run_klines_endpoint(run_id: str, limit: int = 30000, request: Request = None):
    # 调用服务层获取K线数据
    tenant_id = getattr(request.state, "tenant_id", settings.DEFAULT_TENANT_ID) if request else settings.DEFAULT_TENANT_ID
    current_user = getattr(request.state, "user", {}) or {}
    try:
        klines_data = get_run_klines(run_id, limit, tenant_id=tenant_id, current_user=current_user)
    except ValueError:
        raise HTTPException(status_code=404, detail="run not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="access denied")
    # 确保所有数据都是可JSON序列化的Python原生类型
    processed_data = convert_numpy_types(klines_data)
    return processed_data

@router.delete("/runs/{run_id}")
async def delete_run_endpoint(run_id: str, request: Request, current_user=Depends(require_super_admin)):
    """
    删除指定的回测记录及其关联数据
    
    Args:
        run_id: 要删除的回测ID
        
    Returns:
        包含删除结果的字典
    """
    try:
        logger.info(f"接收到删除回测请求，run_id: {run_id}")
        tenant_id = getattr(request.state, "tenant_id", settings.DEFAULT_TENANT_ID)
        success = delete_run(run_id, tenant_id=tenant_id)
        if success:
            logger.info(f"回测记录 {run_id} 删除成功")
            return {"status": "success", "message": f"回测记录 {run_id} 已成功删除"}
        else:
            logger.warning(f"回测记录 {run_id} 删除失败")
            raise HTTPException(status_code=500, detail=f"删除回测记录 {run_id} 失败")
    except Exception as e:
        logger.error(f"删除回测记录时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

@router.post("/runs/batch_delete")
async def batch_delete_runs_endpoint(request: BatchDeleteRequest, http_request: Request, current_user=Depends(require_super_admin)):
    """
    批量删除多个回测记录及其关联数据
    
    Args:
        request: 包含要删除的回测ID列表的请求对象
        
    Returns:
        包含删除结果的字典，记录成功和失败的数量
    """
    try:
        logger.info(f"接收到批量删除回测请求，ids: {request.ids}")
        tenant_id = getattr(http_request.state, "tenant_id", settings.DEFAULT_TENANT_ID)
        result = batch_delete_runs(request.ids, tenant_id=tenant_id)
        
        # 根据删除结果返回不同的状态
        if result['failed'] > 0:
            if result['success'] == 0:
                # 全部删除失败
                logger.warning(f"批量删除全部失败，失败数量: {result['failed']}")
                raise HTTPException(status_code=500, detail=f"批量删除失败: 所有 {result['failed']} 条记录均无法删除")
            else:
                # 部分删除失败
                logger.warning(f"批量删除部分失败，成功: {result['success']} 条，失败: {result['failed']} 条")
                return {
                    "status": "partial_success",
                    "message": f"批量删除完成，但部分记录删除失败，成功: {result['success']} 条，失败: {result['failed']} 条",
                    "result": result
                }
        
        # 全部删除成功
        logger.info(f"批量删除全部成功，成功数量: {result['success']}")
        return {
            "status": "success",
            "message": f"批量删除完成，成功: {result['success']} 条",
            "result": result
        }
    except Exception as e:
        logger.error(f"批量删除回测记录时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量删除失败: {str(e)}")
