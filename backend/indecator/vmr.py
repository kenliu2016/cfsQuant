#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VMR（成交市值比）全自动计算与可视化系统
Author: aaron
Date: 2025-10-09
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

# 添加项目根目录到Python路径，以便能够导入app模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.common.logger import LoggerFactory

# 使用项目统一的日志工具
logger = LoggerFactory.get_logger("indecator.vmr")

from app.db import get_engine

# ========== 用户配置区 ==========
EXCHANGE = "binance"
SYMBOLS = ["BTC/USDT", "ETH/USDT"]
WINDOW_HOURS = 24
ACTIVE_THRESHOLD = 0.05
TIMEFRAME = "1h"  # 可选: "1m", "1h", "1d"
USE_PLOTLY = True
# =================================


# ========== 数据源映射 ==========
TABLE_MAP = {
    "1m": "minute_realtime",
    "1h": "hour_realtime",
    "1d": "day_realtime"
}
TABLE_NAME = TABLE_MAP[TIMEFRAME]
# =================================

# 添加项目根目录和backend目录到Python路径，以便能导入app.db
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
backend_dir = os.path.join(project_root, 'backend')
sys.path.append(project_root)
sys.path.append(backend_dir)

from app.db import get_engine

# === PostgreSQL 连接 ===
engine = get_engine()


def fetch_data(symbol: str, start_date=None, end_date=None):
    """从 PostgreSQL 读取历史数据"""
    engine = get_engine()
    where_clause = f"WHERE exchange='{EXCHANGE}' AND code='{EXCHANGE}-{symbol}'"
    if start_date:
        where_clause += f" AND datetime >= '{start_date}'"
    if end_date:
        where_clause += f" AND datetime <= '{end_date}'"
    
    query = f"""
        SELECT datetime, volume, close, volume AS market_cap
        FROM {TABLE_NAME}
        {where_clause}
        ORDER BY datetime ASC;
    """
    df = pd.read_sql(query, engine)
    return df


def compute_vmr(df: pd.DataFrame, window_hours=24):
    """计算成交市值比"""
    if df.empty:
        return df

    df = df.sort_values("datetime").set_index("datetime")
    window = f"{window_hours}H"

    df['cum_volume'] = df['volume'].rolling(window=window).sum()
    df['start_marketcap'] = df['market_cap'].shift(1)
    df['vmr'] = df['start_marketcap'] / df['cum_volume']
    df = df.reset_index()
    df = df.dropna(subset=['vmr'])
    return df


def save_to_db(df: pd.DataFrame, symbol: str):
    """写入 vmr_metrics 表"""
    if df.empty:
        return
    df_to_save = df[['datetime', 'vmr']].copy()
    df_to_save['exchange'] = EXCHANGE
    df_to_save['code'] = symbol
    df_to_save['timeframe'] = TIMEFRAME
    df_to_save['window_hours'] = WINDOW_HOURS
    df_to_save['threshold'] = ACTIVE_THRESHOLD
    df_to_save['is_active'] = df_to_save['vmr'] > ACTIVE_THRESHOLD
    df_to_save['created_at'] = datetime.utcnow()

    engine = get_engine()
    df_to_save.to_sql('vmr_metrics', engine, if_exists='append', index=False)
    logger.info(f"VMR指标计算完成，共处理 {len(df)} 条数据")


def plot_vmr_plotly(vmr_dict, threshold=0.005):
    fig = go.Figure()
    for symbol, df in vmr_dict.items():
        fig.add_trace(go.Scatter(
            x=df['datetime'],
            y=df['vmr'],
            mode='lines',
            name=symbol
        ))

    fig.add_hline(y=threshold, line_dash="dot",
                  annotation_text=f"高活跃阈值 ({threshold})",
                  annotation_position="top left")

    fig.update_layout(
        title=f"多币种成交市值比（VMR）趋势 [{TIMEFRAME}] (窗口={WINDOW_HOURS}h)",
        xaxis_title="日期",
        yaxis_title="VMR 值",
        yaxis_tickformat=".4f",
        legend_title="币种",
        template="plotly_white",
        hovermode="x unified"
    )
    fig.show()


def main():
    logger.info(f"启动 VMR 指标计算 ({EXCHANGE}, timeframe={TIMEFRAME}, window={WINDOW_HOURS}h)")
    vmr_dict = {}
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    for sym in SYMBOLS:
        logger.info(f"获取数据: {sym}")
        df = fetch_data(sym, start_date, end_date)
        if df.empty:
            logger.warning(f"无数据: {sym}")
            continue

        vmr_df = compute_vmr(df, window_hours=WINDOW_HOURS)
        save_to_db(vmr_df, sym)
        vmr_dict[sym] = vmr_df

    if not vmr_dict:
        logger.error("没有任何币种可绘制。")
        return

    if USE_PLOTLY:
        plot_vmr_plotly(vmr_dict, threshold=ACTIVE_THRESHOLD)


if __name__ == "__main__":
    main()
