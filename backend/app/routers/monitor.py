from fastapi import APIRouter, Body
from ..services.monitor_service import start_monitor, stop_monitor, get_monitor
router = APIRouter(prefix="/api/monitor", tags=["monitor"])

@router.post("/start")
async def start(payload: dict = Body(...)):
    strategy = payload.get("strategy")
    code = payload.get("code")
    start_time = payload.get("start")
    interval = int(payload.get("interval", 10))
    monitor_id = start_monitor(strategy, code, start_time, interval)
    return {"monitor_id": monitor_id}

@router.post("/stop/{monitor_id}")
async def stop(monitor_id: str):
    ok = stop_monitor(monitor_id)
    return {"stopped": ok}

@router.get("/{monitor_id}")
async def status(monitor_id: str):
    m = get_monitor(monitor_id)
    if not m:
        return {"error":"not_found"}
    return m
