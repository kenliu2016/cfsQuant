import requests
import psycopg2
from psycopg2.extras import execute_batch
from datetime import datetime
import time
import argparse
import json

# 数据库连接
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            dbname="quant",
            user="cfs",
            password="Aa520@cfs"
        )
        conn.autocommit = True
        return conn
    except psycopg2.Error as e:
        print(f"数据库连接错误: {e}")
        raise

# Binance.US K线接口
BINANCE_US_URL = "https://api.binance.us/api/v3/klines"
# OKX K线接口
OKX_URL = "https://www.okx.com/api/v5/market/candles"

# 从数据库获取 symbols
def get_symbols():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT exchange, code FROM market_codes WHERE active = true")
        return cur.fetchall()  # [(exchange, code), ...]
    finally:
        cur.close()
        conn.close()

# 存入数据库，修复数据类型问题
def save_klines(table, rows):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        sql = f"""
            INSERT INTO {table} (exchange, code, datetime, open, high, low, close, volume, raw)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (exchange, code, datetime) DO UPDATE
              SET open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                  close=EXCLUDED.close, volume=EXCLUDED.volume, raw=EXCLUDED.raw
        """
        
        # 对rows进行处理，确保数据类型正确
        processed_rows = []
        for row in rows:
            exchange, symbol, dt, open_p, high_p, low_p, close_p, volume, raw = row
            # 将raw数据转换为JSON字符串，避免类型问题
            processed_raw = json.dumps(raw)
            processed_rows.append((
                exchange, symbol, dt, open_p, high_p, low_p, close_p, volume, processed_raw
            ))
            
        # 使用参数化查询执行批量插入
        execute_batch(cur, sql, processed_rows, page_size=200)
        print(f"成功插入/更新 {len(processed_rows)} 条记录到表 {table}")
    except psycopg2.Error as e:
        print(f"数据库操作错误: {e}")
        # 打印详细信息，帮助调试
        if rows and len(rows) > 0:
            print(f"问题行示例: {rows[0]}")
        raise
    finally:
        cur.close()
        conn.close()

# 拉取 Binance.US 历史数据，修复数据处理逻辑
def fetch_binance(symbol, interval, table):
    print(f"[Binance.US] {symbol} {interval}")
    start = int(datetime(2017, 1, 1).timestamp() * 1000)
    
    # 处理不支持的interval
    valid_intervals = ["1m", "1h", "1d"]
    if interval not in valid_intervals:
        print(f"不支持的时间间隔: {interval}，使用默认值 '1m'")
        interval = "1m"
        table = "minute_realtime_1"
        
    while True:
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": 1000,
            "startTime": start
        }
        
        try:
            r = requests.get(BINANCE_US_URL, params=params, timeout=10)
            r.raise_for_status()
            
            data = r.json()
            if not data:
                break

            rows = []
            for d in data:
                try:
                    # 确保时间戳是整数
                    timestamp = int(d[0]) if isinstance(d[0], (int, float)) else int(float(d[0]))
                    open_time = datetime.utcfromtimestamp(timestamp / 1000)
                    
                    if interval == "1d":
                        dt = open_time.date()
                    else:
                        dt = open_time
                    
                    # 安全地转换为浮点数
                    open_p = float(d[1]) if d[1] is not None else 0.0
                    high_p = float(d[2]) if d[2] is not None else 0.0
                    low_p = float(d[3]) if d[3] is not None else 0.0
                    close_p = float(d[4]) if d[4] is not None else 0.0
                    volume = float(d[5]) if d[5] is not None else 0.0
                    
                    # 复制d数组，确保数据安全
                    safe_d = d.copy() if isinstance(d, list) else list(d)
                    
                    rows.append((
                        "binance", symbol, dt,
                        open_p, high_p, low_p, close_p,
                        volume, safe_d
                    ))
                except (ValueError, TypeError) as e:
                    print(f"处理数据时出错: {e}, 数据: {d}")
                    continue

            if rows:
                save_klines(table, rows)
            
            # 正确获取下一次startTime
            if data and len(data) > 0:
                try:
                    start = int(data[-1][6]) + 1  # 用 closeTime+1ms 作为下一次 startTime
                except (IndexError, ValueError):
                    print(f"无法获取下一次startTime，数据: {data[-1]}")
                    break
            
            time.sleep(0.2)  # 防限速
        except requests.RequestException as e:
            print(f"请求错误: {e}")
            time.sleep(2)  # 出错时等待更长时间
        except Exception as e:
            print(f"未知错误: {e}")
            time.sleep(2)

# 拉取 OKX 历史数据，修复数据处理逻辑
def fetch_okx(symbol, interval, table):
    print(f"[OKX] {symbol} {interval}")
    # OKX symbol 格式：BTC-USDT
    instId = symbol.replace("USDT", "-USDT")
    before = None
    
    # 处理不支持的interval
    valid_intervals = ["1m", "1H", "1D"]
    if interval not in valid_intervals:
        print(f"不支持的时间间隔: {interval}，使用默认值 '1m'")
        interval = "1m"
        table = "minute_realtime_1"

    while True:
        params = {
            "instId": instId,
            "bar": interval,
            "limit": 100
        }
        if before:
            params["before"] = before

        try:
            r = requests.get(OKX_URL, params=params, timeout=10)
            r.raise_for_status()
            
            data = r.json().get("data", [])
            if not data:
                break

            rows = []
            for d in data:
                try:
                    # 确保时间戳是整数
                    timestamp = int(d[0]) if isinstance(d[0], (int, float)) else int(float(d[0]))
                    open_time = datetime.utcfromtimestamp(timestamp / 1000)
                    
                    if interval == "1D":
                        dt = open_time.date()
                    else:
                        dt = open_time
                    
                    # 安全地转换为浮点数
                    open_p = float(d[1]) if d[1] is not None else 0.0
                    high_p = float(d[2]) if d[2] is not None else 0.0
                    low_p = float(d[3]) if d[3] is not None else 0.0
                    close_p = float(d[4]) if d[4] is not None else 0.0
                    volume = float(d[5]) if d[5] is not None else 0.0
                    
                    # 复制d数组，确保数据安全
                    safe_d = d.copy() if isinstance(d, list) else list(d)
                    
                    rows.append((
                        "okx", symbol, dt,
                        open_p, high_p, low_p, close_p,
                        volume, safe_d
                    ))
                except (ValueError, TypeError) as e:
                    print(f"处理数据时出错: {e}, 数据: {d}")
                    continue

            if rows:
                save_klines(table, rows)
            
            # 正确设置下一次before参数
            if data and len(data) > 0:
                before = data[-1][0]  # 翻页用 before
            
            time.sleep(0.5)  # 防限速
        except requests.RequestException as e:
            print(f"请求错误: {e}")
            time.sleep(2)  # 出错时等待更长时间
        except Exception as e:
            print(f"未知错误: {e}")
            time.sleep(2)

# 主流程，添加命令行参数解析
def main():
    # 设置命令行参数
    parser = argparse.ArgumentParser(description='获取K线历史数据')
    parser.add_argument('--interval', type=str, default='1m', help='时间间隔: 1m, 1h, 1d')
    parser.add_argument('--test', action='store_true', help='测试模式，只处理少量数据')
    args = parser.parse_args()
    
    # 验证interval参数
    valid_intervals = {"1m", "1h", "1d"}
    if args.interval not in valid_intervals:
        print(f"警告: 不支持的时间间隔 '{args.interval}'，使用默认值 '1m'")
        interval_arg = "1m"
    else:
        interval_arg = args.interval
    
    # 获取所有symbol
    symbols = get_symbols()
    
    # 测试模式只处理前3个symbol
    if args.test and symbols:
        symbols = symbols[:3]
        print(f"测试模式: 只处理 {len(symbols)} 个symbol")
    
    for exchange, code in symbols:
        print(f"处理 {exchange} {code}")
        
        # 根据interval参数选择对应的表
        interval_table_map = {
            "1m": "minute_realtime_1",
            "1h": "hour_realtime_1",
            "1d": "day_realtime_1"
        }
        
        if interval_arg in interval_table_map:
            interval = interval_arg
            table = interval_table_map[interval_arg]
        else:
            interval = "1m"
            table = "minute_realtime_1"
        
        try:
            if exchange == "binance":
                fetch_binance(code, interval, table)
            elif exchange == "okx":
                # OKX的interval格式不同
                okx_interval = {"1m": "1m", "1h": "1H", "1d": "1D"}[interval]
                fetch_okx(code, okx_interval, table)
        except Exception as e:
            print(f"处理 {exchange} {code} 时出错: {e}")
            # 继续处理下一个symbol
            continue
        
        # 测试模式下只处理一个symbol
        if args.test:
            break

if __name__ == "__main__":
    main()