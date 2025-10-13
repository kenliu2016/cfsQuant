from fastapi import APIRouter
from ..common import LoggerFactory, fetch_df, execute

router = APIRouter()

# 示例路由
@router.get("/strategies")
async def get_strategies():
    # 使用fetch_df从数据库获取策略数据
    query = "SELECT * FROM strategies"
    df = await fetch_df(query)
    return df.to_dict(orient="records")

@router.post("/strategies")
async def create_strategy(strategy: dict):
    # 使用execute执行插入策略的SQL语句
    query = "INSERT INTO strategies (name, parameters) VALUES (:name, :parameters)"
    await execute(query, **strategy)
    return {"message": "策略已创建"}