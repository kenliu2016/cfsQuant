import requests
import psycopg2
from datetime import datetime
from psycopg2.extras import execute_values

# === API 配置 ===
API_KEY = "aa933896-7789-4070-adf4-7a4231aa9e83"
API_URL = "https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest"

# === 数据库配置 ===
DB_CONFIG = {
    "dbname": "quant",
    "user": "cfs",
    "password": "Cc563479,.",
    "host": "127.0.0.1",
    "port": 5432
}


def fetch_global_metrics():
    """从 CMC 获取全球市场指标"""
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": API_KEY
    }

    resp = requests.get(API_URL, headers=headers)
    resp.raise_for_status()

    data = resp.json()
    status = data.get("status", {})
    error_code = int(status.get("error_code", 0))
    if error_code != 0:
        raise Exception(f"API error: {status}")

    record = data["data"]

    # 提取主要指标
    quote_usd = record["quote"]["USD"]
    result = {
        "timestamp": datetime.fromisoformat(quote_usd["last_updated"].replace("Z", "+00:00")),
        "btc_dominance": record.get("btc_dominance"),
        "eth_dominance": record.get("eth_dominance"),
        "total_market_cap": quote_usd.get("total_market_cap"),
        "total_volume_24h": quote_usd.get("total_volume_24h"),
        "defi_market_cap": quote_usd.get("defi_market_cap"),
        "stablecoin_market_cap": quote_usd.get("stablecoin_market_cap"),
        "derivatives_volume_24h": quote_usd.get("derivatives_volume_24h"),
        "total_market_cap_yesterday": quote_usd.get("total_market_cap_yesterday"),
        "total_market_cap_yesterday_percentage_change": quote_usd.get("total_market_cap_yesterday_percentage_change"),
        "total_volume_24h_yesterday": quote_usd.get("total_volume_24h_yesterday"),
        "total_volume_24h_yesterday_percentage_change": quote_usd.get("total_volume_24h_yesterday_percentage_change")
    }

    return result


def save_to_postgres(record):
    """保存数据到 PostgreSQL"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    sql = """
    INSERT INTO global_metrics (
        timestamp, btc_dominance, eth_dominance, total_market_cap,
        total_volume_24h, defi_market_cap, stablecoin_market_cap,
        derivatives_volume_24h, total_market_cap_yesterday,
        total_market_cap_yesterday_percentage_change,
        total_volume_24h_yesterday,
        total_volume_24h_yesterday_percentage_change
    )
    VALUES %s
    ON CONFLICT (timestamp)
    DO UPDATE SET
        btc_dominance = EXCLUDED.btc_dominance,
        eth_dominance = EXCLUDED.eth_dominance,
        total_market_cap = EXCLUDED.total_market_cap,
        total_volume_24h = EXCLUDED.total_volume_24h,
        defi_market_cap = EXCLUDED.defi_market_cap,
        stablecoin_market_cap = EXCLUDED.stablecoin_market_cap,
        derivatives_volume_24h = EXCLUDED.derivatives_volume_24h,
        total_market_cap_yesterday = EXCLUDED.total_market_cap_yesterday,
        total_market_cap_yesterday_percentage_change = EXCLUDED.total_market_cap_yesterday_percentage_change,
        total_volume_24h_yesterday = EXCLUDED.total_volume_24h_yesterday,
        total_volume_24h_yesterday_percentage_change = EXCLUDED.total_volume_24h_yesterday_percentage_change,
        created_at = now();
    """

    values = [tuple(record.values())]
    execute_values(cur, sql, values)
    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ 成功保存全局指标记录，时间：{record['timestamp']}")


if __name__ == "__main__":
    try:
        print("🌍 正在获取 CoinMarketCap 全球指标...")
        data = fetch_global_metrics()
        save_to_postgres(data)
        print("✅ 全部任务完成。")
    except Exception as e:
        print("❌ 出错：", e)