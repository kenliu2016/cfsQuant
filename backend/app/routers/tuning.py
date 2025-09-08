from fastapi import APIRouter, Body
from ..services.tuning_service import start_tuning_async, get_tuning_status
router = APIRouter(prefix="/api/tuning", tags=["tuning"])

@router.post("")
async def create_tuning(payload: dict = Body(...)):
    strategy = payload.get("strategy")
    code = payload.get("code")
    start = payload.get("start")
    end = payload.get("end")
    params = payload.get("params", {})
    task_id = start_tuning_async(strategy, code, start, end, params)
    return {"task_id": task_id}

@router.get("/{task_id}")
async def tuning_status(task_id: str):
    st = get_tuning_status(task_id)
    if not st:
        return {"error":"not_found"}
    return st
