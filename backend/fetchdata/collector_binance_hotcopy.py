#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Binance OHLCV 采集器（最终稳定版）
- 数据源：market_codes (exchange='binance' AND quotecurrency='USDT' AND active=true)
- WS：/ws 动态 SUB/UNSUB，分批+ACK，限速≤5条控制消息/秒；兼容 /ws 与 /stream 事件格式
- COPY：TEMP 表 + COPY + UPSERT，适配高吞吐
- 自动分片：>1024 流自动多连接
- 先启动 reader 再订阅；backfill 并发，不阻塞 WS 消费，避免 1008
- 订阅前用 exchangeInfo 白名单过滤；白名单失败时降级为“探测订阅模式”（小批 SUB+ACK）
- 优雅关闭：吞掉 1000 正常关闭异常；修正 asyncio.wait 弃用告警
"""

import os
import re
import json
import time
import math
import asyncio
import logging
import signal
import contextlib
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Set, Any

import asyncpg
import aiohttp
import websockets
from websockets.exceptions import ConnectionClosed, ConnectionClosedOK

# ===================== 配置 =====================
EXCHANGE = "binance"

BINANCE_WS   = os.getenv("BINANCE_WS",   "wss://stream.binance.com:9443/ws")  # 支持 SUB/UNSUB
BINANCE_REST = os.getenv("BINANCE_REST", "https://api.binance.com")

INTERVAL = os.getenv("INTERVAL", "1m")  # 只收 1m，其它周期靠 Timescale 连续聚合
PG_DSN  = os.getenv("PG_DSN", "postgres://cfs:Cc563479,.@127.0.0.1:5432/quant")

# 写入缓冲/COPY
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "400"))
FLUSH_SEC  = float(os.getenv("FLUSH_SEC", "1.0"))

# REST 补数
BACKFILL_LIMIT = int(os.getenv("BACKFILL_LIMIT", "1000"))
BACKFILL_LOOKBACK_MINUTES = int(os.getenv("BACKFILL_LOOKBACK_MINUTES", "300"))

# 热更新轮询
SYMBOL_POLL_SEC = int(os.getenv("SYMBOL_POLL_SEC", "15"))
SUB_BATCH_SIZE  = int(os.getenv("SUB_BATCH_SIZE", "200"))  # 单条控制消息最多 streams 数
INBOUND_RATE_PER_SEC = 5  # Binance 控制消息限速

# 自动分片
SHARD_MAX_STREAMS = int(os.getenv("SHARD_MAX_STREAMS", "1000"))  # 单连接流数阈值（建议<1024）
FORCE_SHARDS = int(os.getenv("FORCE_SHARDS", "0"))               # >0 强制分片数

# 断线重连退避
MAX_RETRY_SEC = int(os.getenv("MAX_RETRY_SEC", "60"))

# exchangeInfo 白名单缓存
VALID_SYMBOLS_CACHE_TTL = 600  # 秒
_VALID_CACHE = {"syms": set(), "ts": 0.0}

# 日志
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("collector")

# ===================== SQL =====================
LOAD_SYMBOLS_FULL_SQL = """
SELECT code
FROM public.market_codes
WHERE exchange = $1
  AND quotecurrency = 'USDT'
  AND active = true
ORDER BY code ASC
"""

LOAD_SYMBOLS_SINCE_SQL = """
SELECT code
FROM public.market_codes
WHERE exchange = $1
  AND quotecurrency = 'USDT'
  AND active = true
  AND updated_at >= $2
ORDER BY code ASC
"""

GET_LAST_CLOSE_TS_SQL = """
SELECT symbol, MAX(close_ts) AS last_close
FROM market_ohlcv_1m
WHERE exchange = $1 AND symbol = ANY($2::text[])
GROUP BY symbol
"""

# ===================== 工具函数 =====================
def ms_to_ts(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)

def now_ms() -> int:
    return int(time.time() * 1000)

def chunked(lst: List[Any], n: int) -> List[List[Any]]:
    return [lst[i:i+n] for i in range(0, len(lst), n)]

def compute_shard_count(total_streams: int) -> int:
    if FORCE_SHARDS > 0:
        return FORCE_SHARDS
    return max(1, math.ceil(total_streams / max(1, SHARD_MAX_STREAMS)))

def shard_index(symbol: str, shard_count: int) -> int:
    return (hash(symbol.lower()) & 0x7FFFFFFF) % shard_count

# ---------- 符号/流构造与校验 ----------
_NON_ALNUM = re.compile(r'[^A-Za-z0-9]+')

def sanitize_symbols(symbols: List[str]) -> List[str]:
    """
    把 market_codes.code 规范化为 binance 符号：
    - 删除 / - _ : . 等非字母数字字符
    - 转小写
    - 去重
    """
    out, seen = [], set()
    for s in symbols:
        if not s:
            continue
        s = s.strip().lower()
        s = _NON_ALNUM.sub('', s)  # 'BTC/USDT' -> 'btcusdt', 'binance:ETHUSDT' -> 'ethusdt'
        if not s:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out

def build_streams(symbols: List[str], interval: str) -> List[str]:
    """把符号转成订阅流名，如 'btcusdt@kline_1m'，并去重"""
    return sorted({f"{s.lower()}@kline_{interval}" for s in sanitize_symbols(symbols)})

def filter_streams_with_whitelist(streams: List[str], whitelist_syms: Set[str], interval: str = INTERVAL) -> List[str]:
    """
    过滤掉不合法/不在白名单的流；正则基于 interval 动态生成
    """
    pat = re.compile(rf'^[a-z0-9]+@kline_{re.escape(interval)}$')
    good, bad = [], []
    for st in streams:
        if not pat.match(st):
            bad.append(st); continue
        sym = st.split("@", 1)[0]
        if sym not in whitelist_syms:
            bad.append(st); continue
        good.append(st)
    if bad:
        log.warning("Filtered %d invalid streams (e.g. %s)", len(bad), bad[:3])
    return good

# ---------- exchangeInfo 白名单（带降级） ----------
async def _fetch_valid_usdt_symbols() -> Set[str]:
    url = f"{BINANCE_REST}/api/v3/exchangeInfo"
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as s:
        async with s.get(url) as r:
            j = await r.json()
    valid = set()
    for sym in j.get("symbols", []):
        if sym.get("quoteAsset") == "USDT" and sym.get("status") == "TRADING":
            valid.add(sym["symbol"].lower())
    return valid

async def get_valid_usdt_symbols() -> Set[str]:
    """优先用缓存；失败则不抛异常，返回缓存（可能为空），由调用方决定降级策略。"""
    now = time.time()
    if _VALID_CACHE["syms"] and now - _VALID_CACHE["ts"] <= VALID_SYMBOLS_CACHE_TTL:
        return _VALID_CACHE["syms"]
    try:
        syms = await _fetch_valid_usdt_symbols()
        _VALID_CACHE["syms"] = syms
        _VALID_CACHE["ts"] = now
        log.info("Refreshed whitelist: %d USDT symbols", len(syms))
        return syms
    except Exception as e:
        log.warning("fetch exchangeInfo failed: %s; using cached whitelist size=%d",
                    repr(e), len(_VALID_CACHE["syms"]))
        return _VALID_CACHE["syms"]

# ===================== COPY 批量写 =====================
COPY_COLS = [
    "exchange","symbol","open_ts","close_ts",
    "open","high","low","close",
    "volume","quote_volume","taker_buy_volume","taker_buy_qv",
    "number_of_trades","is_final"
]

CREATE_STAGE_SQL = f"""
CREATE TEMP TABLE stage_ohlcv (
  {COPY_COLS[0]} text NOT NULL,
  {COPY_COLS[1]} text NOT NULL,
  {COPY_COLS[2]} timestamptz NOT NULL,
  {COPY_COLS[3]} timestamptz NOT NULL,
  {COPY_COLS[4]} numeric NOT NULL,
  {COPY_COLS[5]} numeric NOT NULL,
  {COPY_COLS[6]} numeric NOT NULL,
  {COPY_COLS[7]} numeric NOT NULL,
  {COPY_COLS[8]} numeric NOT NULL,
  {COPY_COLS[9]} numeric,
  {COPY_COLS[10]} numeric,
  {COPY_COLS[11]} numeric,
  {COPY_COLS[12]} bigint,
  {COPY_COLS[13]} boolean NOT NULL
) ON COMMIT DROP;
"""

INSERT_FROM_STAGE_SQL = f"""
INSERT INTO market_ohlcv_1m ({", ".join(COPY_COLS)})
SELECT {", ".join(COPY_COLS)} FROM stage_ohlcv
ON CONFLICT (exchange, symbol, open_ts) DO UPDATE SET
  close_ts = EXCLUDED.close_ts,
  open = EXCLUDED.open,
  high = GREATEST(market_ohlcv_1m.high, EXCLUDED.high),
  low  = LEAST(market_ohlcv_1m.low, EXCLUDED.low),
  close = EXCLUDED.close,
  volume = EXCLUDED.volume,
  quote_volume = EXCLUDED.quote_volume,
  taker_buy_volume = EXCLUDED.taker_buy_volume,
  taker_buy_qv = EXCLUDED.taker_buy_qv,
  number_of_trades = EXCLUDED.number_of_trades,
  is_final = EXCLUDED.is_final
"""

class CopyBuffer:
    """缓冲 → TEMP 表 COPY → 合并 UPSERT"""
    def __init__(self, pool: asyncpg.Pool, batch_size=BATCH_SIZE, flush_sec=FLUSH_SEC):
        self.pool = pool
        self.batch_size = batch_size
        self.flush_sec = flush_sec
        self._rows: List[Tuple] = []
        self._last = time.time()
        self._lock = asyncio.Lock()
        self._counter = 0
        self._last_log = time.time()

    async def add(self, row: Tuple):
        async with self._lock:
            self._rows.append(row)
            self._counter += 1
            now = time.time()
            if now - self._last_log >= 60:
                log.info("WS ingest rate ~ %d msgs/min", self._counter)
                self._counter = 0
                self._last_log = now
            if len(self._rows) >= self.batch_size or (now - self._last) >= self.flush_sec:
                await self.flush()

    async def flush(self):
        if not self._rows:
            return
        rows = self._rows
        self._rows = []
        self._last = time.time()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(CREATE_STAGE_SQL)
                await conn.copy_records_to_table('stage_ohlcv', records=rows, columns=COPY_COLS)
                await conn.execute(INSERT_FROM_STAGE_SQL)

# ===================== DB 装载 =====================
async def load_full_symbols(pool: asyncpg.Pool) -> List[str]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(LOAD_SYMBOLS_FULL_SQL, EXCHANGE)
    if not rows:
        log.warning("No active USDT symbols found in market_codes for exchange=%s", EXCHANGE)
    # 将symbol转换为大写并用/分隔的形式
    formatted_symbols = []
    for r in rows:
        symbol_upper = r["code"].upper()
        # 假设symbol格式为BASEQUOTE（如BTCUSDT），在倒数4个字符前插入/
        if len(symbol_upper) >= 4:
            symbol_formatted = symbol_upper[:-4] + "/" + symbol_upper[-4:]
        else:
            symbol_formatted = symbol_upper  # 如果长度不足，保持原样
        formatted_symbols.append(symbol_formatted)
    return formatted_symbols

async def load_symbols_since(pool: asyncpg.Pool, since_ts: datetime) -> List[str]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(LOAD_SYMBOLS_SINCE_SQL, EXCHANGE, since_ts)
    # 将symbol转换为大写并用/分隔的形式
    formatted_symbols = []
    for r in rows:
        symbol_upper = r["code"].upper()
        # 假设symbol格式为BASEQUOTE（如BTCUSDT），在倒数4个字符前插入/
        if len(symbol_upper) >= 4:
            symbol_formatted = symbol_upper[:-4] + "/" + symbol_upper[-4:]
        else:
            symbol_formatted = symbol_upper  # 如果长度不足，保持原样
        formatted_symbols.append(symbol_formatted)
    return formatted_symbols

# ===================== REST Backfill =====================
async def backfill_symbol(session: aiohttp.ClientSession, pool: asyncpg.Pool, symbol_lc: str, start_ms: int) -> int:
    # 将小写无分隔符格式转换为大写无分隔符格式用于API调用
    # 例如：bsvusdt -> BSVUSDT
    symbol_uc = symbol_lc.upper()
    url = f"{BINANCE_REST}/api/v3/klines"
    params = {"symbol": symbol_uc, "interval": "1m", "limit": BACKFILL_LIMIT, "startTime": start_ms}
    total_rows = 0
    buf = CopyBuffer(pool, batch_size=max(2000, BATCH_SIZE), flush_sec=1.0)
    max_retries = 3  # 最大重试次数
    retry_count = 0

    while True:
        async with session.get(url, params=params, timeout=25) as resp:
            if resp.status != 200:
                txt = await resp.text()
                log.warning("Backfill %s HTTP %s: %s", symbol_uc, resp.status, txt)
                
                # 如果是"Invalid symbol"错误，直接跳过该符号
                if "Invalid symbol" in txt:
                    log.warning("Skipping invalid symbol: %s", symbol_uc)
                    return 0
                
                # 其他错误重试，但限制重试次数
                retry_count += 1
                if retry_count >= max_retries:
                    log.error("Backfill %s failed after %d retries", symbol_uc, max_retries)
                    return 0
                
                await asyncio.sleep(1.5)
                continue
            
            # 重置重试计数
            retry_count = 0
            data = await resp.json()

        if not data:
            break

        for k in data:
            open_ms, o, h, l, c, v, close_ms, qv, trades, tbv, tbq, *_ = k
            # 将symbol转换为大写并用/分隔的形式存入数据库
            # 例如：bsvusdt -> BSV/USDT
            symbol_upper = symbol_lc.upper()
            # 假设symbol格式为BASEQUOTE（如BTCUSDT），在倒数4个字符前插入/
            if len(symbol_upper) >= 4:
                symbol_formatted = symbol_upper[:-4] + "/" + symbol_upper[-4:]
            else:
                symbol_formatted = symbol_upper  # 如果长度不足，保持原样
            
            await buf.add((
                EXCHANGE, symbol_formatted,
                ms_to_ts(open_ms),
                ms_to_ts(close_ms),
                o, h, l, c,
                v, qv, tbv, tbq,
                trades, True
            ))
        await buf.flush()
        total_rows += len(data)

        last_close_ms = data[-1][6]
        if last_close_ms >= now_ms() - 60_000:
            break
        params["startTime"] = last_close_ms + 1
        await asyncio.sleep(0.2)

    return total_rows

async def backfill_range(pool: asyncpg.Pool, symbols_formatted: List[str]):
    # 将格式化后的symbol转换为小写无分隔符格式用于数据库查询
    symbols_lc = []
    for symbol in symbols_formatted:
        symbol_lc = symbol.replace("/", "").lower()
        symbols_lc.append(symbol_lc)
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(GET_LAST_CLOSE_TS_SQL, EXCHANGE, symbols_lc)
    last_map = {r["symbol"]: r["last_close"] for r in rows}
    start_defaults_ms = now_ms() - BACKFILL_LOOKBACK_MINUTES * 60_000

    async with aiohttp.ClientSession() as session:
        sem = asyncio.Semaphore(20)
        async def run_one(sym: str):
            last_close = last_map.get(sym)
            start_ms = int(last_close.timestamp()*1000)+1 if last_close else start_defaults_ms
            return await backfill_symbol(session, pool, sym, start_ms)
        tasks = [run_one(s) for s in symbols_lc]
        results = await asyncio.gather(*[sem_wrapped(sem, t) for t in tasks], return_exceptions=True)
        added = sum(int(r) for r in results if isinstance(r, int))
        log.info("Backfill done (symbols=%d). Inserted %d rows.", len(symbols_formatted), added)

async def sem_wrapped(sem: asyncio.Semaphore, coro):
    async with sem:
        return await coro

# ===================== WS 管理（ACK + 限速） =====================
class WSManager:
    def __init__(self, ws):
        self.ws = ws
        self._last_send_ts = 0.0
        self._id = 1
        self._pending: Dict[int, asyncio.Future] = {}

    async def _throttle(self):
        now = time.time()
        min_interval = 1.0 / INBOUND_RATE_PER_SEC
        if now - self._last_send_ts < min_interval:
            await asyncio.sleep(min_interval - (now - self._last_send_ts))
        self._last_send_ts = time.time()

    async def _send_and_wait_ack(self, method: str, params: List[str]):
        self._id += 1
        mid = self._id
        fut = asyncio.get_running_loop().create_future()
        self._pending[mid] = fut
        await self._throttle()
        await self.ws.send(json.dumps({"method": method, "params": params, "id": mid}))
        try:
            return await asyncio.wait_for(fut, timeout=5.0)
        finally:
            self._pending.pop(mid, None)

    async def subscribe(self, streams: List[str]):
        for batch in chunked(streams, SUB_BATCH_SIZE):
            ack = await self._send_and_wait_ack("SUBSCRIBE", batch)
            if isinstance(ack, dict) and "error" in ack:
                log.warning("SUB ACK error: %s", ack)
            else:
                log.info("SUB %d streams ack ok", len(batch))

    async def unsubscribe(self, streams: List[str]):
        for batch in chunked(streams, SUB_BATCH_SIZE):
            ack = await self._send_and_wait_ack("UNSUBSCRIBE", batch)
            if isinstance(ack, dict) and "error" in ack:
                log.warning("UNSUB ACK error: %s", ack)
            else:
                log.info("UNSUB %d streams ack ok", len(batch))

    async def handle_control_ack(self, msg: dict):
        # {"result": null, "id": X} 或 {"id":X,"code":-1121,"msg":"Invalid symbol."}
        mid = msg.get("id")
        if mid is None:
            return
        fut = self._pending.get(mid)
        if not fut or fut.done():
            return
        if "code" in msg:
            fut.set_result({"error": msg.get("code"), "msg": msg.get("msg")})
        else:
            fut.set_result(msg.get("result"))

# ===================== 分片 =====================
class Shard:
    def __init__(self, shard_id: int, shard_count: int, pool: asyncpg.Pool):
        self.shard_id = shard_id
        self.shard_count = shard_count
        self.pool = pool
        self.buf = CopyBuffer(pool, batch_size=BATCH_SIZE, flush_sec=FLUSH_SEC)
        self.current_symbols: Set[str] = set()
        self.current_streams: Set[str] = set()
        self.last_poll_ts: datetime = datetime.now(timezone.utc) - timedelta(days=1)
        self.wsm: WSManager | None = None

    def owns(self, symbol: str) -> bool:
        # 将大写并用/分隔的symbol转换回小写无分隔符格式用于分片计算
        # 例如：BTC/USDT -> btcusdt
        symbol_lc = symbol.replace("/", "").lower()
        return shard_index(symbol_lc, self.shard_count) == self.shard_id

    async def run(self, shutdown_event: asyncio.Event):
        backoff = 1
        while not shutdown_event.is_set():
            try:
                async with websockets.connect(BINANCE_WS, ping_interval=150, max_queue=None) as ws:
                    log.info("[shard %d/%d] WS connected", self.shard_id+1, self.shard_count)
                    self.wsm = WSManager(ws)

                    # 1) 先启动 reader，确保订阅后马上消费
                    reader_task = asyncio.create_task(self._ws_reader(ws))

                    # 2) 白名单（可能失败，get_valid_usdt_symbols 不会抛异常）
                    whitelist = await get_valid_usdt_symbols()

                    full_syms = set(await load_full_symbols(self.pool))
                    my_syms = {s for s in full_syms if self.owns(s)}

                    streams_all = build_streams(list(my_syms), INTERVAL)
                    if whitelist:
                        streams = filter_streams_with_whitelist(streams_all, whitelist, interval=INTERVAL)
                    else:
                        log.warning("[shard %d] Whitelist empty; falling back to probing mode (small-batch SUB+ACK).",
                                    self.shard_id)
                        streams = streams_all  # 探测模式：ACK 兜底

                    if len(streams) > 1024:
                        raise RuntimeError(f"[shard {self.shard_id}] streams {len(streams)} exceed 1024")

                    # 分批 + ACK 订阅
                    await self.wsm.subscribe(streams)

                    # 直接使用my_syms作为current_symbols，因为my_syms已经是正确格式的symbol
                    self.current_symbols = my_syms
                    self.current_streams = set(streams)

                    updater_task  = asyncio.create_task(self._symbol_updater())
                    backfill_task = asyncio.create_task(backfill_range(self.pool, sorted(list(self.current_symbols))))
                    shutdown_task = asyncio.create_task(_await_shutdown(shutdown_event))

                    done, pending = await asyncio.wait(
                        [reader_task, updater_task, backfill_task, shutdown_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    for t in pending:
                        t.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await t
            except (ConnectionClosed, OSError) as e:
                log.warning("[shard %d] WS disconnected: %s", self.shard_id, e)
            except Exception as e:
                log.exception("[shard %d] WS error: %s", self.shard_id, e)

            if shutdown_event.is_set():
                break
            await asyncio.sleep(backoff)
            backoff = min(MAX_RETRY_SEC, backoff * 2)
            log.info("[shard %d] Reconnecting WS (backoff=%ss)...", self.shard_id, backoff)

    async def _on_control_ack(self, msg: dict):
        if self.wsm:
            await self.wsm.handle_control_ack(msg)

    async def _ws_reader(self, ws):
        try:
            while True:
                msg = await ws.recv()
                data = json.loads(msg)

                # 控制消息 ACK（含 id + result/code）
                if isinstance(data, dict) and ("id" in data) and ("result" in data or "code" in data):
                    await self._on_control_ack(data)
                    continue

                # 事件负载：/stream -> {"stream": "...", "data": {...}}；/ws -> {...}
                event = data.get("data", data)
                k = event.get("k")
                if not k:
                    continue

                symbol_lc = k["s"].lower()
                if not self.owns(symbol_lc):
                    continue

                # 将symbol转换为大写并用/分隔的形式
                # 例如：btcusdt -> BTC/USDT, ethusdt -> ETH/USDT
                symbol_upper = k["s"].upper()
                # 假设symbol格式为BASEQUOTE（如BTCUSDT），在倒数4个字符前插入/
                if len(symbol_upper) >= 4:
                    symbol_formatted = symbol_upper[:-4] + "/" + symbol_upper[-4:]
                else:
                    symbol_formatted = symbol_upper  # 如果长度不足，保持原样

                row = (
                    EXCHANGE, symbol_formatted,
                    ms_to_ts(k["t"]), ms_to_ts(k["T"]),
                    k["o"], k["h"], k["l"], k["c"],
                    k["v"], k.get("q","0"), k.get("V","0"), k.get("Q","0"),
                    k.get("n",0), bool(k["x"])
                )
                await self.buf.add(row)
        except ConnectionClosedOK:
            return
        except ConnectionClosed as e:
            log.warning("[shard %d] reader closed: %s", self.shard_id, e)
            return

    async def _symbol_updater(self):
        while True:
            await asyncio.sleep(SYMBOL_POLL_SEC)
            try:
                self.last_poll_ts = datetime.now(timezone.utc)

                latest_full = set(await load_full_symbols(self.pool))
                latest_my   = {s for s in latest_full if self.owns(s)}

                to_add_syms = latest_my - self.current_symbols
                to_del_syms = self.current_symbols - latest_my

                if to_add_syms or to_del_syms:
                    whitelist = await get_valid_usdt_symbols()

                    to_add_streams_all = build_streams(list(to_add_syms), INTERVAL)
                    to_add_streams = (filter_streams_with_whitelist(to_add_streams_all, whitelist, INTERVAL)
                                      if whitelist else to_add_streams_all)
                    to_del_streams = build_streams(list(to_del_syms), INTERVAL)

                    if to_add_streams:
                        await self.wsm.subscribe(to_add_streams)
                    if to_del_streams:
                        await self.wsm.unsubscribe(to_del_streams)

                    self.current_symbols = latest_my
                    # 将latest_my中的symbol转换为小写无分隔符格式用于构建streams
                    symbols_lc = []
                    for symbol in latest_my:
                        symbol_lc = symbol.replace("/", "").lower()
                        symbols_lc.append(symbol_lc)
                    self.current_streams = set(build_streams(symbols_lc, INTERVAL))
                    log.info("[shard %d] Hot update: +%d / -%d symbols",
                             self.shard_id, len(to_add_syms), len(to_del_syms))
            except Exception as e:
                log.warning("[shard %d] updater error: %s", self.shard_id, e)

# ===================== 启动器 =====================
async def _await_shutdown(evt: asyncio.Event):
    await evt.wait()

async def main():
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def _handle_sig():
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_sig)
        except NotImplementedError:
            pass

    pool = await asyncpg.create_pool(dsn=PG_DSN, min_size=1, max_size=10)

    try:
        # 计算需要的分片数
        full_syms = await load_full_symbols(pool)
        streams = build_streams(full_syms, INTERVAL)
        shard_count = compute_shard_count(len(streams))
        log.info("Loaded %d symbols (%d streams). shard_count=%d",
                 len(full_syms), len(streams), shard_count)

        shards = [Shard(i, shard_count, pool) for i in range(shard_count)]
        tasks = [asyncio.create_task(s.run(shutdown_event)) for s in shards]

        await shutdown_event.wait()
        for t in tasks:
            t.cancel()
        for t in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await t
    finally:
        await pool.close()

if __name__ == "__main__":
    asyncio.run(main())