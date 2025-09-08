import yaml
import os
from sqlalchemy import create_engine
from sqlalchemy import text
import pandas as pd
import urllib.parse

print("测试SQLAlchemy数据库连接...")

# 获取配置文件路径
cfg_path = os.getenv("DB_CONFIG", os.path.join(os.path.dirname(__file__), "backend", "config", "db_config.yaml"))

# 读取配置文件
if os.path.exists(cfg_path):
    print(f"找到配置文件: {cfg_path}")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    
    pg = cfg.get("postgres", {})
    print(f"数据库配置: {pg}")
    
    # 构建连接字符串 - 对密码进行URL编码以处理特殊字符
    password = urllib.parse.quote_plus(pg.get('password'))
    url = f"postgresql+psycopg2://{pg.get('user')}:{password}@{pg.get('host')}:{pg.get('port')}/{pg.get('dbname')}"
    print(f"构建的连接URL: {url}")
    
    try:
        # 创建引擎
        print("创建SQLAlchemy引擎...")
        engine = create_engine(url, future=True)
        
        # 测试连接
        print("测试连接...")
        with engine.connect() as conn:
            print("连接成功!")
            
            # 执行简单查询
            result = conn.execute(text("SELECT version();"))
            version = result.scalar()
            print(f"PostgreSQL版本: {version}")
            
            # 检查表是否存在
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'minute_realtime'
                )
            """))
            table_exists = result.scalar()
            print(f"minute_realtime表存在: {table_exists}")
            
            # 尝试使用fetch_df函数风格的查询
            print("尝试执行类似fetch_df的查询...")
            sql = text("""
                SELECT 
                    DATE_TRUNC('day', datetime) AS datetime,
                    code,
                    FIRST_VALUE(open) OVER (PARTITION BY DATE_TRUNC('day', datetime) ORDER BY datetime) AS open,
                    MAX(high) AS high,
                    MIN(low) AS low,
                    LAST_VALUE(close) OVER (PARTITION BY DATE_TRUNC('day', datetime) ORDER BY datetime) AS close,
                    SUM(volume) AS volume
                FROM minute_realtime
                WHERE code = :code AND datetime BETWEEN :start AND :end
                GROUP BY DATE_TRUNC('day', datetime), code
                ORDER BY datetime
                LIMIT 5
            """)
            
            params = {
                'code': 'BTCUSDT',
                'start': '2025-09-02 00:00:00',
                'end': '2025-09-08 23:59:00'
            }
            
            result = conn.execute(sql, params)
            columns = result.keys()
            rows = result.fetchall()
            
            print(f"查询结果列: {columns}")
            print(f"查询结果行数: {len(rows)}")
            if rows:
                print(f"第一行数据: {rows[0]}")
            
            # 使用pandas读取SQL
            print("使用pandas读取SQL...")
            df = pd.read_sql(sql, conn, params=params)
            print(f"DataFrame形状: {df.shape}")
            print(df.head())
            
    except Exception as e:
        print(f"连接失败: {e}")
        import traceback
        traceback.print_exc()
else:
    print(f"配置文件不存在: {cfg_path}")