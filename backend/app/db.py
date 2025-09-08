"""
统一数据库连接封装模块
- 支持 psycopg2 与 SQLAlchemy
- 从 config/db_config.yaml 读取；支持环境变量覆盖
- 环境变量覆盖：PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
"""

import os
from typing import Dict, Any, Optional
import yaml

# 全局engine变量，懒加载
_engine = None

try:
    import psycopg2
except ImportError:
    psycopg2 = None

try:
    from sqlalchemy import create_engine
except ImportError:
    create_engine = None

DEFAULT_CONFIG_PATH = os.environ.get("DB_CONFIG", "config/db_config.yaml")


def load_db_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    加载数据库配置。
    优先级：参数 > 环境变量 DB_CONFIG > 默认路径。
    环境变量覆盖：PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
    """
    path = config_path or DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    pg = dict(raw.get("postgres", {}))
    # 兼容 dbname / database 两种命名
    dbname = pg.get("dbname") or pg.get("database")
    pg["dbname"] = dbname

    # 环境变量覆盖
    if os.environ.get("PGHOST"):
        pg["host"] = os.environ["PGHOST"]
    if os.environ.get("PGPORT"):
        try:
            pg["port"] = int(os.environ["PGPORT"])
        except ValueError:
            pg["port"] = os.environ["PGPORT"]
    if os.environ.get("PGDATABASE"):
        pg["dbname"] = os.environ["PGDATABASE"]
    if os.environ.get("PGUSER"):
        pg["user"] = os.environ["PGUSER"]
    if os.environ.get("PGPASSWORD"):
        pg["password"] = os.environ["PGPASSWORD"]

    # 默认端口
    pg.setdefault("port", 5432)
    return pg


def get_connection(config_path: Optional[str] = None):
    """返回 psycopg2 连接"""
    if psycopg2 is None:
        raise ImportError("未安装 psycopg2，请先执行: pip install psycopg2-binary")

    pg = load_db_config(config_path)
    conn = psycopg2.connect(
        host=pg["host"],
        port=pg["port"],
        dbname=pg["dbname"],
        user=pg["user"],
        password=pg["password"],
    )
    return conn


def get_engine(config_path: Optional[str] = None):
    """返回 SQLAlchemy Engine"""
    if create_engine is None:
        raise ImportError("未安装 SQLAlchemy，请先执行: pip install sqlalchemy psycopg2-binary")

    import urllib.parse
    
    pg = load_db_config(config_path)
    # 对用户名和密码进行URL编码，处理特殊字符如@
    user = urllib.parse.quote_plus(pg['user'])
    password = urllib.parse.quote_plus(pg['password'])
    
    url = f"postgresql+psycopg2://{user}:{password}@{pg['host']}:{pg['port']}/{pg['dbname']}"

    # ✅ 这里用 sqlalchemy.create_engine，而不是递归调用自己
    engine = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)
    return engine


def fetch_df(query: str, config_path: Optional[str] = None, **kwargs):
    """执行SQL查询并返回pandas DataFrame
    
    Args:
        query: SQL查询语句
        config_path: 数据库配置路径
        **kwargs: 参数化查询的参数
    """
    try:
        import pandas as pd
        from sqlalchemy import text
    except ImportError:
        raise ImportError("未安装必要的包，请先执行: pip install pandas sqlalchemy")
    
    engine = get_engine(config_path)
    with engine.connect() as conn:
        if kwargs:
            # 使用SQLAlchemy的text对象来支持命名参数
            df = pd.read_sql(text(query), conn, params=kwargs)
        else:
            df = pd.read_sql(query, conn)
    return df


def to_sql(df, table_name: str, config_path: Optional[str] = None, if_exists: str = "append", index: bool = False):
    """将pandas DataFrame写入数据库表"""
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("未安装 pandas，请先执行: pip install pandas")
    
    engine = get_engine(config_path)
    df.to_sql(table_name, engine, if_exists=if_exists, index=index)


def execute(query: str, config_path: Optional[str] = None):
    """执行SQL语句（适合非查询语句，如INSERT、UPDATE、DELETE等）"""
    engine = get_engine(config_path)
    with engine.connect() as conn:
        conn.execute(query)
        conn.commit()


# 提供全局engine变量，懒加载
def get_engine_global():
    """获取全局SQLAlchemy Engine实例"""
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine

# 全局engine变量
def _get_engine():
    """内部函数，用于获取engine"""
    return get_engine_global()

# 设置engine属性，使其可以被导入
globals()['engine'] = _get_engine()