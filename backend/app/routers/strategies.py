from fastapi import APIRouter, Body, HTTPException, Request, Depends

from ..services.strategies_service import (
    alist_strategies,
    load_strategy_code,
    save_strategy_code,
    clear_strategies_cache,
    create_strategy as create_strategy_service,
    delete_strategy as delete_strategy_service,
)
from ..main.dependencies import require_user

router = APIRouter(prefix="/api/strategies", tags=["strategies"], dependencies=[Depends(require_user)])

@router.get("")
async def strategies(request: Request):
    tenant_id = getattr(request.state, "tenant_id", None)
    df = await alist_strategies(tenant_id=tenant_id)
    return {"rows": df.to_dict(orient="records")}


@router.get("/{strategy_name}/code")
async def get_strategy_code(strategy_name: str):
    code = load_strategy_code(strategy_name)
    return {"code": code}


@router.post("/{strategy_name}/code")
async def update_strategy_code(strategy_name: str, payload: dict = Body(...), request: Request = None):
    code = payload.get("code", "")
    tenant_id = getattr(request.state, "tenant_id", None) if request else None
    result = save_strategy_code(strategy_name, code, tenant_id=tenant_id)
    # 清除缓存以刷新策略列表
    clear_strategies_cache(tenant_id)
    return result


@router.post("")
async def create_strategy(payload: dict = Body(...), request: Request = None):
    name = payload.get("name")
    desc = payload.get("description", "")
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    tenant_id = getattr(request.state, "tenant_id", None) if request else None
    res = create_strategy_service(name, desc, tenant_id=tenant_id)
    # 清除缓存以刷新策略列表
    clear_strategies_cache(tenant_id)
    return res


@router.delete("/{strategy_name}")
async def delete_strategy(strategy_name: str, request: Request = None):
    tenant_id = getattr(request.state, "tenant_id", None) if request else None
    res = delete_strategy_service(strategy_name, tenant_id=tenant_id)
    if res.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="not found")
    # 清除缓存以刷新策略列表
    clear_strategies_cache(tenant_id)
    return res
