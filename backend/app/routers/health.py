from fastapi import APIRouter
from common.schemas import HealthResp
router = APIRouter(prefix="/api", tags=["health"])
@router.get("/health", response_model=HealthResp)
async def health():
    return {"status":"ok"}
