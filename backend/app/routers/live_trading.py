from fastapi import APIRouter, Body, HTTPException, Query, Request, Depends
from typing import Any, Dict, Optional

from ..services.live_trading_service import LiveTradingService
from ..main.config import settings
from ..main.dependencies import require_user

router = APIRouter(prefix="/api/live-trading", tags=["live-trading"], dependencies=[Depends(require_user)])


def _service_from_request(request: Request) -> LiveTradingService:
    tenant_id = getattr(request.state, "tenant_id", settings.DEFAULT_TENANT_ID)
    return LiveTradingService(tenant_id=tenant_id)


@router.get("/exchanges")
async def list_supported_exchanges():
    return {
        "exchanges": sorted(LiveTradingService.SUPPORTED_EXCHANGES),
    }


@router.get("/accounts")
async def list_accounts(request: Request):
    service = _service_from_request(request)
    accounts = service.list_accounts()
    return {"rows": accounts, "total": len(accounts)}


@router.post("/accounts")
async def create_account(request: Request, payload: Dict[str, Any] = Body(...)):
    required = ["exchange", "api_key", "api_secret"]
    for field in required:
        if field not in payload:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    service = _service_from_request(request)
    try:
        account = service.create_account(
            exchange=payload["exchange"],
            api_key=payload["api_key"],
            api_secret=payload["api_secret"],
            label=payload.get("label"),
            api_passphrase=payload.get("api_passphrase"),
            extra=payload.get("extra"),
            is_active=payload.get("is_active", True),
        )
        return account
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/accounts/{account_id}")
async def update_account(account_id: str, request: Request, payload: Dict[str, Any] = Body(...)):
    service = _service_from_request(request)
    try:
        account = service.update_account(
            account_id=account_id,
            exchange=payload.get("exchange"),
            api_key=payload.get("api_key"),
            api_secret=payload.get("api_secret"),
            label=payload.get("label"),
            api_passphrase=payload.get("api_passphrase"),
            extra=payload.get("extra"),
            is_active=payload.get("is_active"),
        )
        return account
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: str, request: Request):
    service = _service_from_request(request)
    try:
        service.delete_account(account_id)
        return {"status": "deleted"}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/accounts/{account_id}/test")
async def test_account(account_id: str, request: Request):
    service = _service_from_request(request)
    try:
        result = service.test_connection(account_id)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/balance")
async def fetch_balance(account_id: str = Query(...), request: Request = None):
    service = _service_from_request(request)
    try:
        balances = service.fetch_balances(account_id)
        return balances
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/orders/open")
async def fetch_open_orders(
    account_id: str = Query(...),
    symbol: Optional[str] = Query(None),
    request: Request = None,
):
    service = _service_from_request(request)
    try:
        orders = service.fetch_open_orders(account_id, symbol)
        return {"rows": orders, "total": len(orders)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/orders")
async def place_order(request: Request, payload: Dict[str, Any] = Body(...)):
    required = ["account_id", "symbol", "side", "order_type", "amount"]
    for field in required:
        if field not in payload:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    service = _service_from_request(request)
    try:
        order = service.place_order(
            account_id=payload["account_id"],
            symbol=payload["symbol"],
            side=payload["side"],
            order_type=payload["order_type"],
            amount=float(payload["amount"]),
            price=payload.get("price"),
            params=payload.get("params"),
        )
        return order
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.delete("/orders/{account_id}/{order_id}")
async def cancel_order(
    account_id: str,
    order_id: str,
    request: Request,
    symbol: Optional[str] = Query(None),
):
    service = _service_from_request(request)
    try:
        result = service.cancel_order(account_id, order_id, symbol)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
