"""
统一数据库连接封装模块
- 支持 psycopg2 与 SQLAlchemy
- 从 config/db_config.yaml 读取；支持环境变量覆盖
- 环境变量覆盖：PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
- 支持同步和异步数据库操作
"""

import os
from typing import Dict, Any, Optional, AsyncGenerator
import yaml

# 全局变量，用于缓存数据库引擎
_engine = None
_async_engine = None
# 全局变量，用于缓存会话工厂
_session_factory = None
_async_session_factory = None
# 异步支持标志
HAS_ASYNC = True

try:
    import psycopg2
except ImportError:
    psycopg2 = None

try:
    from sqlalchemy import create_engine
except ImportError:
    create_engine = None

try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
except ImportError:
    HAS_ASYNC = False

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
    """返回 SQLAlchemy Engine - 使用全局单例模式和优化的连接池配置"""
    global _engine
    
    if create_engine is None:
        raise ImportError("未安装 SQLAlchemy，请先执行: pip install sqlalchemy psycopg2-binary")
    
    # 如果引擎已经存在且配置相同，直接返回
    if _engine is not None:
        return _engine
    
    import urllib.parse
    
    pg = load_db_config(config_path)
    # 对用户名和密码进行URL编码，处理特殊字符如@
    user = urllib.parse.quote_plus(pg['user'])
    password = urllib.parse.quote_plus(pg['password'])
    
    url = f"postgresql+psycopg2://{user}:{password}@{pg['host']}:{pg['port']}/{pg['dbname']}"
    
    # 优化的连接池配置
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=20,              # 增加连接池大小到20
        max_overflow=40,           # 增加最大溢出连接数到40
        pool_timeout=30,           # 连接池超时时间
        pool_recycle=1800,         # 连接回收时间(秒)
        pool_use_lifo=True,        # 使用后进先出策略，提高连接复用效率
        echo=False,                # 关闭SQL日志
        connect_args={
            'connect_timeout': 10, # 连接超时时间
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5
        }
    )
    
    _engine = engine
    
    # 添加连接预热机制，减少首次连接开销
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            # 执行一个简单的查询来预热连接
            conn.execute(text("SELECT 1"))
            # 预热几个连接放入池中
            for _ in range(min(5, engine.pool.size())):
                conn = engine.connect()
                conn.execute(text("SELECT 1"))
                conn.close()
    except Exception as e:
        # 预热失败不影响引擎使用
        pass
    
    return engine


async def get_async_engine(config_path: Optional[str] = None):
    """返回 SQLAlchemy 异步 Engine - 使用全局单例模式"""
    global _async_engine
    
    if not HAS_ASYNC:
        raise ImportError("未安装 SQLAlchemy 异步支持，请先执行: pip install sqlalchemy[asyncio] asyncpg")
    
    # 如果异步引擎已经存在，直接返回
    if _async_engine is not None:
        return _async_engine
    
    import urllib.parse
    
    pg = load_db_config(config_path)
    # 对用户名和密码进行URL编码，处理特殊字符如@
    user = urllib.parse.quote_plus(pg['user'])
    password = urllib.parse.quote_plus(pg['password'])
    
    # 异步连接使用 asyncpg 驱动
    url = f"postgresql+asyncpg://{user}:{password}@{pg['host']}:{pg['port']}/{pg['dbname']}"
    
    # 优化的异步连接池配置
    _async_engine = create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=40,
        pool_timeout=30,
        pool_recycle=1800,
        pool_use_lifo=True,
        echo=False,
        connect_args={
            'timeout': 10,
            'command_timeout': 30
        }
    )
    
    # 预热异步连接
    try:
        from sqlalchemy import text
        async with _async_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        # 预热失败不影响引擎使用
        pass
    
    return _async_engine


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """异步上下文管理器，提供数据库会话"""
    global _async_session_factory
    
    if not HAS_ASYNC:
        raise ImportError("未安装 SQLAlchemy 异步支持，请先执行: pip install sqlalchemy[asyncio] asyncpg")
    
    # 如果会话工厂不存在，创建它
    if _async_session_factory is None:
        engine = await get_async_engine()
        _async_session_factory = sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False
        )
    
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


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


async def fetch_df_async(query: str, config_path: Optional[str] = None, **kwargs):
    """异步执行SQL查询并返回pandas DataFrame
    
    Args:
        query: SQL查询语句
        config_path: 数据库配置路径
        **kwargs: 参数化查询的参数
    """
    import logging
    import inspect
    logger = logging.getLogger(__name__)
    # 设置为INFO级别以确保日志可见
    logger.setLevel(logging.INFO)
    
    if not HAS_ASYNC:
        # 如果没有异步支持，降级为同步查询
        return fetch_df(query, config_path, **kwargs)
    
    try:
        import pandas as pd
        from sqlalchemy import text
    except ImportError:
        raise ImportError("未安装必要的包，请先执行: pip install pandas sqlalchemy")
    
    try:
        # 获取异步引擎
        engine = await get_async_engine(config_path)
        
        # 添加基本的类型检查
        if engine is None:
            raise ValueError("未能获取有效的异步引擎 - engine为None")
        if not hasattr(engine, 'connect'):
            raise ValueError(f"引擎对象不具有connect方法，类型: {type(engine)}")
        
        # 使用异步连接执行查询并读取结果
        result = None
        try:
            async with engine.connect() as conn:
                # 执行查询
                if kwargs:
                    result = await conn.execute(text(query), kwargs)
                else:
                    result = await conn.execute(text(query))

                # 获取列名
                columns = result.keys()

                batch_size = 10000
                chunks = []

                # 分批获取数据
                while True:
                    batch = result.fetchmany(batch_size)
                    if not batch:
                        break
                    chunks.append(pd.DataFrame(batch, columns=columns))

                # 如果没有数据，返回空DataFrame
                if not chunks:
                    logger.debug("没有获取到数据，返回空DataFrame")
                    return pd.DataFrame(columns=columns)

                # 优化：合并所有批次的数据，避免过多的内存复制
                if len(chunks) == 1:
                    logger.debug("只有一个批次，直接复制")
                    df = chunks[0].copy()
                else:
                    logger.debug(f"合并 {len(chunks)} 个批次")
                    # 使用ignore_index=True避免索引冲突
                    df = pd.concat(chunks, ignore_index=True)
                    # 释放中间数据占用的内存
                    del chunks

                # 优化：数据类型转换，减少内存使用
                for col in df.columns:
                    # 尝试将数值列转换为更高效的数据类型
                    if pd.api.types.is_integer_dtype(df[col]):
                        # 检查是否存在NA值，如果不存在可以使用更高效的类型
                        if not df[col].isna().any():
                            df[col] = df[col].astype('int32')  # 使用更小的整数类型
                    elif pd.api.types.is_float_dtype(df[col]):
                        # 对于浮点数，可以使用float32来减少内存使用
                        df[col] = df[col].astype('float32')
                    elif pd.api.types.is_object_dtype(df[col]):
                        # 尝试推断并转换对象列
                        try:
                            # 尝试使用通用格式解析日期时间
                            # 先检查是否包含时间信息
                            if df[col].str.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', na=False).any():
                                # 包含时间，使用带时间的格式
                                df[col] = pd.to_datetime(df[col], format='%Y-%m-%d %H:%M:%S', errors='coerce')
                            elif df[col].str.match(r'\d{4}-\d{2}-\d{2}', na=False).any():
                                # 只有日期，使用日期格式
                                df[col] = pd.to_datetime(df[col], format='%Y-%m-%d', errors='coerce')
                            else:
                                # 其他格式，不需要尝试解析，因为注释说明不会修改原数据
                                # 已移除不必要的pd.to_datetime调用，避免警告
                                pass  # 空语句，确保代码块不为空
                        except (ValueError, TypeError, AttributeError):
                            # 不能转换为datetime，检查是否可以转换为分类类型以减少内存使用
                            if len(df[col].unique()) < len(df) * 0.5:
                                df[col] = df[col].astype('category')

                logger.debug(f"成功获取数据: {len(df)} 行，{len(df.columns)} 列")
                return df
        except Exception as e:
            logger.error(f"查询执行失败: {type(e).__name__}: {e}")
            raise
        finally:
            # 确保结果集被关闭 - 直接检查result是否不为None
            if result is not None:
                try:
                    logger.debug(f"关闭结果集，类型: {type(result)}")
                    result.close()
                    logger.debug("结果集关闭成功")
                except Exception as close_e:
                    logger.warning(f"关闭结果集时出错: {type(close_e).__name__}: {close_e}")
    except Exception as e:
        logger.error(f"连接数据库失败: {type(e).__name__}: {e}")
        raise
    except Exception as e:
        logger.error(f"数据库操作总失败: {type(e).__name__}: {e}")
        raise


def to_sql(df, table_name: str, config_path: Optional[str] = None, if_exists: str = "append", index: bool = False):
    """将pandas DataFrame写入数据库表"""
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("未安装 pandas，请先执行: pip install pandas")
    
    engine = get_engine(config_path)
    df.to_sql(table_name, engine, if_exists=if_exists, index=index)


async def to_sql_async(df, table_name: str, config_path: Optional[str] = None, if_exists: str = "append", index: bool = False):
    """异步将pandas DataFrame写入数据库表"""
    if not HAS_ASYNC:
        # 如果没有异步支持，降级为同步操作
        to_sql(df, table_name, config_path, if_exists, index)
        return
    
    try:
        import pandas as pd
        from sqlalchemy import text
    except ImportError:
        raise ImportError("未安装必要的包，请先执行: pip install pandas sqlalchemy")
    
    # 对于异步操作，我们需要先将DataFrame转换为字典列表，然后批量插入
    records = df.to_dict(orient='records')
    if not records:
        return  # 没有数据需要插入
    
    # 获取列名
    columns = list(records[0].keys())
    # 构建INSERT语句
    placeholders = [f":{col}" for col in columns]
    insert_stmt = text(
        f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
    )
    
    # 异步执行批量插入
    engine = await get_async_engine(config_path)
    async with engine.begin() as conn:
        # 如果需要替换表，先删除旧表
        if if_exists == 'replace':
            try:
                await conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
                # 从DataFrame推断表结构并创建表
                # 注意：这是一个简化版，实际项目中可能需要更复杂的表结构定义
                await conn.execute(text(_create_table_sql_from_df(df, table_name)))
            except Exception as e:
                # 如果创建表失败，记录日志并继续
                import logging
                logging.error(f"创建表 {table_name} 失败: {e}")
        elif if_exists == 'fail':
            # 检查表是否存在
            result = await conn.execute(
                text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :table_name)"),
                {"table_name": table_name}
            )
            if result.scalar():
                raise ValueError(f"表 {table_name} 已存在")
        
        # 执行批量插入 - SQLAlchemy异步API直接接受参数列表
        await conn.execute(insert_stmt, records)


def _create_table_sql_from_df(df, table_name):
    """从DataFrame推断表结构并生成CREATE TABLE SQL语句"""
    # 这是一个简化的实现，实际项目中可能需要更复杂的类型映射
    type_mapping = {
        'int64': 'INTEGER',
        'float64': 'DOUBLE PRECISION',
        'object': 'TEXT',
        'datetime64[ns]': 'TIMESTAMP'
    }
    
    columns = []
    for col, dtype in df.dtypes.items():
        sql_type = type_mapping.get(str(dtype), 'TEXT')
        columns.append(f"{col} {sql_type}")
    
    return f"CREATE TABLE {table_name} ({', '.join(columns)})"


def execute(query: str, config_path: Optional[str] = None):
    """执行SQL语句（适合非查询语句，如INSERT、UPDATE、DELETE等）"""
    engine = get_engine(config_path)
    with engine.connect() as conn:
        with conn.begin() as transaction:
            try:
                conn.execute(query)
                transaction.commit()
            except Exception as e:
                transaction.rollback()
                raise e


async def execute_async(query: str, config_path: Optional[str] = None, **kwargs):
    """异步执行SQL语句（适合非查询语句，如INSERT、UPDATE、DELETE等）"""
    if not HAS_ASYNC:
        # 如果没有异步支持，降级为同步操作
        execute(query, config_path)
        return
    
    try:
        from sqlalchemy import text
    except ImportError:
        raise ImportError("未安装必要的包，请先执行: pip install sqlalchemy")
    
    engine = await get_async_engine(config_path)
    async with engine.connect() as conn:
        async with conn.begin() as transaction:
            try:
                if kwargs:
                    await conn.execute(text(query), kwargs)
                else:
                    await conn.execute(text(query))
                await transaction.commit()
            except Exception as e:
                await transaction.rollback()
                raise e


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

def get_session():
    """同步上下文管理器，提供数据库会话"""
    global _session_factory
    
    if create_engine is None:
        raise ImportError("未安装 SQLAlchemy，请先执行: pip install sqlalchemy")
    
    # 如果会话工厂不存在，创建它
    if _session_factory is None:
        engine = get_engine()
        _session_factory = sessionmaker(
            engine,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False
        )
    
    with _session_factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()