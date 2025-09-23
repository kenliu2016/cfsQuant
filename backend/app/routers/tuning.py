from fastapi import APIRouter, Body, HTTPException
from ..services.tuning_service import start_tuning_async, get_tuning_status, get_all_tuning_tasks

# 创建用于 /tuning 前缀的路由器
router = APIRouter(prefix="/tuning", tags=["tuning"])

# 创建用于 /api/tuning 前缀的路由器
available_router = APIRouter(prefix="/api/tuning", tags=["tuning"])

# 定义共享的端点处理函数
async def create_tuning_handler(payload: dict = Body(...)):
    strategy = payload.get("strategy")
    code = payload.get("code")
    start = payload.get("start")
    end = payload.get("end")
    params = payload.get("params", {})
    interval = payload.get("interval", "1m")
    task_id = start_tuning_async(strategy, code, start, end, params, interval)
    return {"task_id": task_id}

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

# 注册端点到两个路由器
router.post("")(create_tuning_handler)
router.get("/{task_id}")(tuning_status_handler)
router.get("")(all_tuning_tasks_handler)

available_router.post("")(create_tuning_handler)
available_router.get("/{task_id}")(tuning_status_handler)
available_router.get("")(all_tuning_tasks_handler)

# 重新导出路由器变量以确保兼容性
tuning_router = router
