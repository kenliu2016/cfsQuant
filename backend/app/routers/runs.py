from fastapi import APIRouter
import numpy as np
import logging
from ..services.runs_service import recent_runs, run_detail, get_grid_levels

router = APIRouter(prefix="/api", tags=["runs"])

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
    # 现在run_detail函数直接返回包含四部分数据的字典
    detail_data = run_detail(run_id)
    # 确保所有数据都是可JSON序列化的Python原生类型
    processed_data = convert_numpy_types(detail_data)
    return processed_data
