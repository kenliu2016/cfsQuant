# -*- coding: utf-8 -*-
"""
Binance 数据接入器
支持：
1. REST 历史数据拉取（分钟线 / 日线）
2. WebSocket 实时订阅（分钟线 / 日线，支持 final/realtime 保存模式）
"""

import os
import sys
import yaml
import argparse
import asyncio
import json
import logging
from datetime import datetime
import websockets
from sqlalchemy import Table, Column, MetaData, DateTime, String, Float
from sqlalchemy.dialects.postgresql import insert

# 项目根目录加入 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.adapters.adapter_binance import BinanceAdapter
from app.db import get_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------ WebSocket 管理类 ------------------
metadata = MetaData()
minute_realtime = Table(
    "minute_realtime", metadata,
    Column("datetime", DateTime, primary_key=True),
    Column("code", String, primary_key=True),
    Column("open", Float),
    Column("high", Float),
    Column("low", Float),
    Column("close", Float),
    Column("volume", Float),
)

day_realtime = Table(
    "day_realtime", metadata,
    Column("datetime", DateTime, primary_key=True),
    Column("code", String, primary_key=True),
    Column("open", Float),
    Column("high", Float),
    Column("low", Float),
    Column("close", Float),
    Column("volume", Float),
)


class BinanceWS:
    def __init__(self, symbols, interval="1m", uri="wss://stream.binance.com:9443/ws",
                 save_mode="final", batch_size=20):
        self.symbols = [s.lower() for s in symbols]
        self.interval = interval
        self.uri = uri
        self.save_mode = save_mode
        self.engine = get_engine()
        self.batch_size = batch_size
        self.queue = []

        # 根据 interval 选择表
        if interval.endswith("m"):
            self.table = minute_realtime
        elif interval.endswith("d"):
            self.table = day_realtime
        else:
            raise ValueError(f"Unsupported interval: {interval}")

    async def connect(self):
        """建立 WebSocket 连接并订阅，自动重连"""
        stream_names = [f"{s}@kline_{self.interval}" for s in self.symbols]
        stream_url = f"{self.uri}/{'/'.join(stream_names)}"
        logger.info(f"[Binance WS] 连接: {stream_url}, 保存模式={self.save_mode}")

        while True:
            try:
                async with websockets.connect(stream_url, ping_interval=20, ping_timeout=20) as ws:
                    async for msg in ws:
                        await self.handle_message(msg)
            except Exception as e:
                logger.warning(f"[Binance WS] 连接异常: {e}，5秒后重连")
                await asyncio.sleep(5)

    async def handle_message(self, msg):
        """处理消息并写入数据库，支持批量写入"""
        try:
            data = json.loads(msg)
        except json.JSONDecodeError:
            logger.warning("收到非 JSON 消息")
            return

        if "k" not in data:
            return

        k = data["k"]

        # final 模式下只保存收盘数据
        if self.save_mode == "final" and not k["x"]:
            return

        record = {
            "datetime": datetime.fromtimestamp(k["t"] / 1000),
            "code": k["s"],
            "open": float(k["o"]),
            "high": float(k["h"]),
            "low": float(k["l"]),
            "close": float(k["c"]),
            "volume": float(k["v"]),
        }

        self.queue.append(record)

        # 批量写入
        if len(self.queue) >= self.batch_size:
            self.flush_queue()

    def flush_queue(self):
        """批量写入数据库"""
        if not self.queue:
            return
        try:
            with self.engine.begin() as conn:
                for record in self.queue:
                    stmt = insert(self.table).values(record)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["datetime", "code"],
                        set_=record
                    )
                    conn.execute(stmt)
            logger.info(f"[Binance WS] 批量保存 {len(self.queue)} 条记录 ({self.interval})")
        except Exception as e:
            logger.error(f"[Binance WS] 写入数据库失败: {e}")
        finally:
            self.queue = []


# ------------------ YAML 配置加载 ------------------
def load_config(config_path):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


# ------------------ 主逻辑入口 ------------------
def main():
    parser = argparse.ArgumentParser(description="Binance 数据接入器")
    parser.add_argument("--rest-only", action="store_true", help="只执行 REST 历史数据拉取")
    parser.add_argument("--ws-only", action="store_true", help="只执行 WebSocket 实时订阅")
    parser.add_argument("--interval", default=None, help="K 线周期，例如 1m 或 1d")
    parser.add_argument("--config", default="config/datasource.binance.yaml", help="配置文件路径")
    args = parser.parse_args()

    config = load_config(args.config)
    binance_config = config.get("binance", {})

    adapter = BinanceAdapter(
        api_key=binance_config.get("api_key", ""),
        api_secret=binance_config.get("api_secret", "")
    )

    interval = args.interval if args.interval else "1m"

    # ---------------- REST 历史数据 ----------------
    if args.rest_only or (not args.rest_only and not args.ws_only):
        if binance_config.get("rest", {}).get("enabled", True):
            print(f"执行 REST 历史数据拉取 ({interval})...")
            rest_config = binance_config["rest"]
            symbols = rest_config.get("symbols", ["BTCUSDT", "ETHUSDT"])
            limit = rest_config.get("limit", 1000)

            for symbol in symbols:
                print(f"拉取 {symbol} 的历史数据...")
                klines = adapter.fetch_klines(symbol=symbol, interval=interval, limit=limit)
                print(f"获取到 {len(klines)} 条数据，保存到数据库...")

                # 根据周期选择表
                table_name = "minute_realtime" if interval.endswith("m") else "day_realtime"
                adapter.save_klines_to_db(klines=klines, code=symbol, table_name=table_name)
                print(f"{symbol} 的数据保存完成到 {table_name}")
        else:
            print("REST 数据拉取已禁用")

    # ---------------- WebSocket 实时订阅 ----------------
    if args.ws_only or (not args.rest_only and not args.ws_only):
        if binance_config.get("websocket", {}).get("enabled", True):
            print(f"执行 WebSocket 实时订阅 ({interval})...")
            ws_config = binance_config["websocket"]
            symbols = ws_config.get("symbols", ["btcusdt", "ethusdt"])
            save_mode = ws_config.get("save_mode", "final")

            ws = BinanceWS(symbols=symbols, interval=interval, save_mode=save_mode)
            try:
                asyncio.run(ws.connect())
            except KeyboardInterrupt:
                print("程序已停止")
        else:
            print("WebSocket 订阅已禁用")


if __name__ == "__main__":
    main()
