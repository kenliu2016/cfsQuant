from fastapi import APIRouter, Body
from ..services.strategies_service import alist_strategies, load_strategy_code, save_strategy_code, clear_strategies_cache
from fastapi import APIRouter, Body, HTTPException

router = APIRouter(prefix="/api/strategies", tags=["strategies"])

@router.get("")
async def strategies():
    df = await alist_strategies()
    return {"rows": df.to_dict(orient="records")}
@router.get("/{strategy_name}/code")
async def get_strategy_code(strategy_name: str):
    code = load_strategy_code(strategy_name)
    return {"code": code}
@router.post("/{strategy_name}/code")
async def update_strategy_code(strategy_name: str, payload: dict = Body(...)):
    code = payload.get("code", "")
    result = save_strategy_code(strategy_name, code)
    # 清除缓存以刷新策略列表
    clear_strategies_cache()
    return result


from fastapi import Body, HTTPException

@router.post("")
async def create_strategy(payload: dict = Body(...)):
    name = payload.get("name")
    desc = payload.get("description", "")
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    from ..services.strategies_service import create_strategy
    res = create_strategy(name, desc)
    # 清除缓存以刷新策略列表
    clear_strategies_cache()
    return res

@router.delete("/{strategy_name}")
async def delete_strategy(strategy_name: str):
    from ..services.strategies_service import delete_strategy
    res = delete_strategy(strategy_name)
    if res.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="not found")
    # 清除缓存以刷新策略列表
    clear_strategies_cache()
    return res
