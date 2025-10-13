import sys
import os

# 添加项目根目录到Python路径，以便能够导入app模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from app.common.logger import LoggerFactory

# 使用项目统一的日志工具
logger = LoggerFactory.get_logger("routers.tuning")

from fastapi import APIRouter, Body, HTTPException
from ..services.tuning_service import start_tuning_async, get_tuning_status, get_all_tuning_tasks, delete_tuning_task, run_parameter_tuning

# 创建用于 /api/tuning 前缀的路由器（与前端保持一致）
router = APIRouter(prefix="/api/tuning", tags=["tuning"])
# 定义共享的端点处理函数
async def create_tuning_handler(payload: dict = Body(...)):
    strategy = payload.get("strategy")
    # 同时支持code和excode字段，优先使用excode
    code = payload.get("excode") or payload.get("code")
    # 同时支持新旧参数名，优先使用start_time和end_time（前端实际使用的参数名）
    start = payload.get("start_time") or payload.get("start")
    end = payload.get("end_time") or payload.get("end")
    params = payload.get("params", {})
    interval = payload.get("interval", "1m")
    
    # 验证必需参数
    if not strategy:
        raise HTTPException(status_code=400, detail="策略名称（strategy）不能为空")
    if not code:
        raise HTTPException(status_code=400, detail="交易对代码（code）不能为空")
    if not start:
        raise HTTPException(status_code=400, detail="开始时间（start/start_time）不能为空")
    if not end:
        raise HTTPException(status_code=400, detail="结束时间（end/end_time）不能为空")
    
    task_id = start_tuning_async(strategy, code, params, interval, start, end)
    return {"task_id": task_id}

# 添加任务转发端点，用于primary实例将任务转发到secondary实例
@router.post("/forward")
async def forward_tuning_task(payload: dict = Body(...)):
    """
    接收来自primary实例的任务转发请求
    此端点只应由secondary实例处理
    """
    # 提取任务参数
    task_id = payload.get("task_id")
    strategy = payload.get("strategy")
    code = payload.get("code")
    start_time = payload.get("start_time")
    end_time = payload.get("end_time")
    params_grid = payload.get("params_grid", {})
    interval = payload.get("interval", "1m")
    total = payload.get("total", 1)
    
    # 验证必需参数
    if not all([task_id, strategy, code, start_time, end_time]):
        raise HTTPException(status_code=400, detail="缺少必需的任务参数")
    
    # 直接提交任务到Celery队列
    try:
        run_parameter_tuning.delay(task_id, strategy, code, start_time, end_time, params_grid, interval, total)
        logger.info(f"成功接收并提交转发的调优任务: {task_id}")
        return {"success": True, "task_id": task_id}
    except Exception as e:
        logger.error(f"提交转发的调优任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"提交任务失败: {str(e)}")

async def tuning_status_handler(task_id: str):
    st = get_tuning_status(task_id)
    if not st:
        # 返回JSON格式的错误信息，而不是抛出异常
        # 这样前端可以正确解析错误信息而不会触发404页面
        return {"error": "not_found", "detail": "任务不存在或已被删除"}
    return st

async def all_tuning_tasks_handler():
    tasks = get_all_tuning_tasks()
    return {"tasks": tasks}

async def delete_tuning_task_handler(task_id: str):
    result = delete_tuning_task(task_id)
    if not result:
        return {"error": "not_found", "detail": "任务不存在或已被删除"}
    return {"success": True, "message": "任务已成功删除"}

# 注册端点到路由器
router.post("")(create_tuning_handler)
router.get("/{task_id}")(tuning_status_handler)
router.get("")(all_tuning_tasks_handler)
router.delete("/{task_id}")(delete_tuning_task_handler)

# 重新导出路由器变量以确保兼容性
tuning_router = router
