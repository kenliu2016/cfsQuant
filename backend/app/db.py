from sqlalchemy import text, create_engine
from sqlalchemy.engine import Engine
import pandas as pd
import os
import yaml

cfg_path = os.getenv("DB_CONFIG", os.path.join(os.path.dirname(__file__), "..", "config", "db_config.yaml"))
if os.path.exists(cfg_path):
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    pg = cfg.get("postgres", {})
    url = f"postgresql+psycopg2://{pg.get('user')}:{pg.get('password')}@{pg.get('host')}:{pg.get('port')}/{pg.get('dbname')}"
else:
    url = os.getenv("DB_URL", "sqlite:///./local.db")
engine = create_engine(url, future=True)

def fetch_df(sql: str, **params):
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn, params=params)
    return df


def execute(sql: str, **params):
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text(sql), params)


def to_sql(df, table: str, if_exists: str = 'append'):
    df.to_sql(table, con=engine, if_exists=if_exists, index=False)
