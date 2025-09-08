from fastapi import APIRouter, Body
from ..services.strategies_service import list_strategies, load_strategy_code, save_strategy_code
router = APIRouter(prefix="/api/strategies", tags=["strategies"])
@router.get("")
async def strategies():
    df = list_strategies()
    return {"rows": df.to_dict(orient="records")}
@router.get("/{strategy_name}/code")
async def get_strategy_code(strategy_name: str):
    code = load_strategy_code(strategy_name)
    return {"code": code}
@router.post("/{strategy_name}/code")
async def update_strategy_code(strategy_name: str, payload: dict = Body(...)):
    code = payload.get("code", "")
    return save_strategy_code(strategy_name, code)


from fastapi import Body, HTTPException

@router.post("")
async def create_strategy(payload: dict = Body(...)):
    name = payload.get("name")
    desc = payload.get("description", "")
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    from ..services.strategies_service import create_strategy
    res = create_strategy(name, desc)
    return res

@router.delete("/{strategy_name}")
async def delete_strategy(strategy_name: str):
    from ..services.strategies_service import delete_strategy
    res = delete_strategy(strategy_name)
    if res.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="not found")
    return res
