# -*- coding: utf-8 -*-
"""
Binance 数据适配器
- REST 拉取历史 K 线
- WebSocket 实时订阅 K 线
- 数据落地到 Postgres: minute_realtime(datetime, code, open, high, low, close, volume)
依赖：python-binance, websocket-client
"""
import os, json, time, threading
from datetime import datetime
from typing import List, Optional

import websocket  # websocket-client
from binance.client import Client  # python-binance

from app.db import get_connection  # 统一数据库封装
from app.db import get_engine
from sqlalchemy import Table, Column, MetaData, DateTime, String, Float
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime

class BinanceAdapter:
    def __init__(self, api_key: Optional[str]=None, api_secret: Optional[str]=None):
        self.api_key = api_key or os.getenv("BINANCE_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET", "")
        self.client = Client(self.api_key, self.api_secret)

    def fetch_klines(self, symbol: str, interval: str="1m", limit: int=500, start_time=None, end_time=None):
        params = dict(symbol=symbol, interval=interval, limit=limit)
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        return self.client.get_klines(**params)

    def save_klines_to_db(self, klines, code, table_name="minute_realtime"):
        metadata = MetaData()
        table = Table(
            table_name, metadata,
            Column("datetime", DateTime, primary_key=True),
            Column("code", String, primary_key=True),
            Column("open", Float),
            Column("high", Float),
            Column("low", Float),
            Column("close", Float),
            Column("volume", Float),
        )

        engine = get_engine()
        with engine.begin() as conn:
            for k in klines:
                record = {
                    "datetime": datetime.fromtimestamp(k[0] / 1000),  # open_time 转 datetime
                    "code": code,
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                }
                stmt = insert(table).values(record)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["datetime", "code"],
                    set_=record
                )
                conn.execute(stmt)



    def _on_message(self, ws, message: str, code: str):
        data = json.loads(message)
        if "k" not in data:
            return
        k = data["k"]
        dt = datetime.fromtimestamp(k["t"] / 1000.0)
        conn = get_connection()
        cur = conn.cursor()
        sql = """
        INSERT INTO minute_realtime(datetime, code, open, high, low, close, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (datetime, code) DO UPDATE SET
          open = EXCLUDED.open,
          high = EXCLUDED.high,
          low = EXCLUDED.low,
          close = EXCLUDED.close,
          volume = EXCLUDED.volume
        """
        cur.execute(sql, (
            dt, code, float(k["o"]), float(k["h"]), float(k["l"]), float(k["c"]), float(k["v"])
        ))
        conn.commit()
        cur.close()
        conn.close()

    def _on_error(self, ws, error):
        print("[Binance WS] 错误:", error)

    def _on_close(self, ws, status_code, msg):
        print("[Binance WS] 连接关闭:", status_code, msg)

    def _on_open(self, ws, symbol: str, interval: str):
        payload = {"method": "SUBSCRIBE", "params": [f"{symbol}@kline_{interval}"], "id": 1}
        ws.send(json.dumps(payload))

    def start_ws(self, symbol: str="btcusdt", interval: str="1m"):
        url = "wss://stream.binance.com:9443/ws"
        ws = websocket.WebSocketApp(
            url,
            on_message=lambda ws, msg: self._on_message(ws, msg, code=symbol.upper()),
            on_error=self._on_error,
            on_close=self._on_close,
        )
        ws.on_open = lambda ws: self._on_open(ws, symbol, interval)
        th = threading.Thread(target=ws.run_forever, daemon=True)
        th.start()
        print(f"[Binance WS] 订阅启动: {symbol.upper()} @ {interval}")
