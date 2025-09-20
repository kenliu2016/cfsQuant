
"""策略：grid_fixed_strategy.py
    固定网格单边做多策略实现
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple

# 默认策略参数
DEFAULT_PARAMS = {
    "H_price": None,  # 网格最高价
    "L_price": None,  # 网格最低价
    "N": 10,          # 网格数量
    "F": 10000.0,      # 初始资金
    "R": 0.5,         # 资金使用率
    "ref_period": 120, #获取最高价最低价的bar的范围
    "atr_window": 14, #计算ATR的窗口
    "fee_rate": 0.001,  # 交易费率
    "slippage": 0.00002,    # 滑点
    "per_grid_amount": None,  # 每格固定金额（覆盖计算值）
    "stop_loss_price": None,   # 止损价格
    "min_trade_amount": 0.0    # 最小交易金额
}


def init_grid_params(H_price: float, L_price: float, N: int, F: float, R: float,
                     fee_rate: float = 0.001, explicit_A: float = None) -> Tuple[Dict[str, Any], List[str]]:
    """
    根据PRD（产品需求文档）公式初始化网格参数。
    返回计算出的参数字典和警报字符串列表（如有红色警报）。
    
    公式（根据PRD）：
      D = (H - L) / N  # 网格间距
      网格点 P_i = H - (i-1)*D, i=1..N+1  => P1=H, P_{N+1}=L
      买入点 = P2..P_{N+1} (N个点)
      卖出点 = P1..P_N (N个点)
      sum_inv = sum(1 / p for p in 买入点)
      A = (F * R) / (N - L * sum_inv)  # 每格交易金额
      idle_fund = F - A * N  # 闲置资金
      收益率：min_yield, max_yield, avg_yield (扣除2*fee_rate)
      极端情况下平均成本 = N / sum_inv
      最大回撤 = (A*N - A*sum_inv*L) / F
    """
    alerts: List[str] = []  # 警报列表
    computed = {}  # 计算结果字典

    # 基础参数检查
    if H_price is None or L_price is None:
        raise ValueError("必须提供H_price和L_price参数。")
    if L_price >= H_price:
        raise ValueError("L_price必须小于H_price。")
    if N <= 0:
        raise ValueError("N必须是正整数。")
    if F <= 0:
        raise ValueError("F必须为正数。")
    if not (0 <= R <= 1):
        alerts.append("[PARAM_WARNING] R应在[0,1]范围内。")

    D = (H_price - L_price) / float(N)  # 网格间距
    # 生成网格点 P0..PN -> 使用1-based描述但存储为浮点数列表
    points = [H_price - i * D for i in range(0, N + 1)]  # P0=H, P_N=L ; 对应PRD中的P1..P_{N+1}
    buy_points = points[1:]  # P2..P_{N+1}，买入点
    sell_points = points[:-1]  # P1..P_N，卖出点

    # 计算sum_inv = sum(1/p for p in buy_points)
    # 防御性处理：避免零或负价格
    if any(p <= 0 for p in buy_points):
        alerts.append("[PARAM_ERROR] 一个或多个买入点价格<=0 - 无效网格。")
        sum_inv = float('inf')
    else:
        # 严格数值累加，避免大量网格时的微小浮点误差
        sum_inv = 0.0
        for p in buy_points:
            sum_inv += 1.0 / float(p)

    # 计算A的分母
    denom = float(N) - float(L_price) * sum_inv
    A = None
    if explicit_A is not None:
        A = float(explicit_A)  # 如果明确指定了A，则使用指定值
    else:
        # 如果denom <= 0 => 公式给出负的或无限的A -> 无效网格
        if denom <= 0:
            A = -1.0
        else:
            A = (F * R) / denom

    # 诊断/警告信息
    if denom <= 0:
        alerts.append(
            "[RISK_ALERT] 网格公式分母<=0 -- 网格不可行。"
            "这意味着 (N - L * sum(1/P_buy)) <= 0。"
            "建议增大 R、减小 N 或降低 L_price。"
        )

    if A is not None and A <= 0:
        alerts.append(
            "[RISK_ALERT] 计算出的每格金额A <= 0。网格参数无效或风险过小。"
        )

    # 总投资金额
    total_invest = (A * N) if (A is not None and A > 0 and np.isfinite(A)) else float('inf')
    # 闲置资金
    idle_fund = F - total_invest if np.isfinite(total_invest) else float('-inf')

    # 收益率计算（扣除两倍费率）
    # 根据PRD：D / 买入价格 * 100% - 2*费率*100%
    # min_yield对应高价格区域（最小D/买入价格），max_yield对应低价格区域
    if len(buy_points) > 0:
        min_yield = (D / max(buy_points)) * 100.0 - 2.0 * fee_rate * 100.0  # 最小收益率
        max_yield = (D / min(buy_points)) * 100.0 - 2.0 * fee_rate * 100.0  # 最大收益率
        avg_buy_price = sum(buy_points) / float(len(buy_points))  # 平均买入价格
        avg_yield = (D / avg_buy_price) * 100.0 - 2.0 * fee_rate * 100.0  # 平均收益率
    else:
        min_yield = max_yield = avg_yield = 0.0

    # 极端情况下的平均成本（所有网格被触发）
    avg_cost_extreme = (float(N) / sum_inv) if sum_inv != 0 and np.isfinite(sum_inv) else float('inf')

    # 最大回撤（根据PRD公式）
    # PRD公式：max_drawdown = (A * N - A * sum_inv * L_price) / F
    if A is not None and np.isfinite(A):
        max_drawdown = (A * N - A * sum_inv * L_price) / float(F)
    else:
        max_drawdown = float('inf')

    # 更新计算结果字典
    computed.update({
        'D': D,                   # 网格间距
        'points': points,         # 所有网格点
        'buy_points': buy_points, # 买入点
        'sell_points': sell_points, # 卖出点
        'sum_inv': sum_inv,       # 买入点倒数和
        'A': A,                   # 每格交易金额
        'idle_fund': idle_fund,   # 闲置资金
        'min_yield_pct': min_yield, # 最小收益率百分比
        'max_yield_pct': max_yield, # 最大收益率百分比
        'avg_yield_pct': avg_yield, # 平均收益率百分比
        'avg_cost_extreme': avg_cost_extreme, # 极端情况下的平均成本
        'max_drawdown_fraction': max_drawdown, # 最大回撤比例
        'denom': denom            # 计算A时的分母值
    })

    return computed, alerts

def suggest_grid_bounds(df, ref_period, atr_window):
    """
    根据历史行情推荐网格上下轨.
    """
    if df.empty:
        return None

    df_tail = df.tail(ref_period)
    max_hist = df_tail['high'].max()
    min_hist = df_tail['low'].min()

    # 计算 ATR
    import ta
    atr_indicator = ta.volatility.AverageTrueRange(
        high=df_tail['high'], low=df_tail['low'],
        close=df_tail['close'], window=atr_window
    )
    atr = atr_indicator.average_true_range().iloc[-1]

    # 默认上下轨
    L_price = min_hist
    H_price = max_hist

    # ATR 扩展推荐
    L_price_ext = max(0.0, L_price - atr)   # 避免负数价格
    H_price_ext = H_price + atr

    return {
        "max_hist": max_hist,
        "min_hist": min_hist,
        "atr": atr,
        "L_price": L_price,
        "H_price": H_price,
        "L_price_ext": L_price_ext,
        "H_price_ext": H_price_ext
    }

def run(df: pd.DataFrame, params: Dict[str, Any]):
    """
    主要策略函数，实现固定网格单边做多策略行为。
    
    参数:
        df: 包含OHLC数据的DataFrame
        params: 策略参数字典，会与DEFAULT_PARAMS合并
    
    返回:
        包含以下键的字典:
        - data: 处理后的DataFrame，包含仓位、现金、持仓等信息
        - grid_levels: 网格级别信息列表
        - alerts: 警报信息列表
        - metrics: 策略表现指标
    """
    # 防御性复制，避免修改原始数据
    df = df.copy()
    # 快速检查数据是否为空
    if df.empty:
        df['position'] = 0.0
        return {'data': df, 'grid_levels': [], 'alerts': ["EMPTY_DATA"], 'metrics': {}}

    # 确保必要的列存在
    required = ['open', 'high', 'low', 'close']
    for c in required:
        if c not in df.columns:
            raise ValueError(f"缺少必要列: {c}")

    # 合并参数与默认值
    p = DEFAULT_PARAMS.copy()
    if params:
        p.update(params)

    # 提取关键参数
    H = p.get('H_price')
    L = p.get('L_price')
    N = int(p.get('N', 50))
    F = float(p.get('F', 1000.0))
    R = float(p.get('R', 0.2))
    ref_period = int(p.get('ref_period', 120))
    atr_window = int(p.get('atr_window', 14))
    fee_rate = float(p.get('fee_rate', DEFAULT_PARAMS['fee_rate']))
    slippage = float(p.get('slippage', 0.0))
    explicit_A = p.get('per_grid_amount', None)
    stop_loss_price_param = p.get('stop_loss_price', None)
    min_trade_amount = float(p.get('min_trade_amount', 0.0))
    symbol = p.get('symbol', None)

    alerts: List[str] = []
    # 基础参数检查
    if H is None or L is None:
        # 如果没有提供H_price和L_price，调用suggest_grid_bounds获取推荐值
        grid_bounds = suggest_grid_bounds(df,ref_period,atr_window)
        if grid_bounds is None:
            raise ValueError("参数中必须提供H_price和L_price，且历史数据不能为空。")
        # 使用扩展推荐的最高价和最低价
        H = grid_bounds['H_price_ext']
        L = grid_bounds['L_price_ext']
        alerts.append(f"[INFO] 使用推荐的网格边界值: H_price={H:.6f}, L_price={L:.6f}")
    if L >= H:
        raise ValueError("L_price必须小于H_price。")

    # 初始化网格参数
    computed, init_alerts = init_grid_params(H, L, N, F, R, fee_rate, explicit_A)
    alerts.extend(init_alerts)

    # 提取计算出的网格参数
    D = computed['D']
    points = computed['points']
    buy_points = computed['buy_points']
    sell_points = computed['sell_points']
    sum_inv = computed['sum_inv']
    A = computed['A']
    idle_fund = computed['idle_fund']
    max_drawdown = computed['max_drawdown_fraction']

    # 如果明确指定了A，则覆盖计算值
    if explicit_A is not None:
        A = float(explicit_A)

    # 警告：如果当前价格超出网格范围[L,H]（检查最后收盘价）
    current_price = float(df['close'].iloc[-1])
    if current_price > H or current_price < L:
        alerts.append(f"[PRICE_ALERT] 当前价格 {current_price:.6f} 超出网格范围 [{L:.6f}, {H:.6f}]。")

    # 准备网格单元格：索引0..N-1，每个单元格包含上轨、下轨等信息
    cells = []
    for i in range(N):
        cells.append({
            'index': i,
            'upper': float(points[i]),   # 单元格上轨价格（卖出价格）
            'lower': float(points[i + 1]), # 单元格下轨价格（买入价格）
            'flag': 0,    # 0=未触发，1=持有中
            'qty': 0.0,   # 持有数量
            'cost': 0.0,  # 总成本（名义金额 + 买入费用）
            'buy_notional': 0.0,  # 买入名义金额
            'execs': []   # 已执行的买入记录列表（用于审计）
        })

    # 如果未提供止损价格，计算建议的止损价：L - D（低于最低网格一格）
    if stop_loss_price_param is None:
        stop_loss_price = L - D
    else:
        stop_loss_price = float(stop_loss_price_param)

    # 账户状态变量
    cash = float(F)  # 现金
    realized_profit = 0.0  # 已实现利润
    total_qty = 0.0  # 总持仓数量
    total_cost = 0.0  # 累计买入总成本（含手续费）
    positions_timeseries = []  # 仓位时间序列
    cash_ts = []  # 现金时间序列
    holdings_ts = []  # 持仓价值时间序列
    equity_ts = []  # 总资产（现金+持仓）时间序列
    avg_cost_ts = []  # 平均成本时间序列

    # 合理性检查：如果A*N > F => 仍然允许但发出警告（应该已经在前面捕获）
    if np.isfinite(A) and A * N > F + 1e-9:
        alerts.append(
            f"[RISK_ALERT] 买入所有网格所需资金A*N = {A * N:.2f} 超过初始资金F = {F:.2f}。"
        )

    # 按时间顺序遍历每一行数据
    for idx, row in df.iterrows():
        low = float(row['low'])
        high = float(row['high'])
        close = float(row['close'])

        # 买入处理：对于每个未触发的单元格，如果价格触及下轨，则买入
        for cell in cells:
            if cell['flag'] == 0:
                lower = cell['lower']
                # 触发买入条件
                if low <= lower + 1e-12:
                    # 执行价格（买入时支付滑点上浮）
                    exec_price = lower * (1.0 + slippage)
                    notional = float(A)  # 名义交易金额
                    # 检查最小交易金额
                    if notional < min_trade_amount:
                        # 跳过执行
                        continue
                    # 计算交易数量
                    qty = notional / exec_price
                    # 计算买入手续费
                    buy_fee = notional * fee_rate
                    # 计算总现金流出
                    total_out = notional + buy_fee
                    cash -= total_out
                    # 更新单元格状态
                    cell['flag'] = 1
                    cell['qty'] += qty
                    cell['cost'] += total_out
                    cell['buy_notional'] += notional
                    cell['execs'].append({'type': 'buy', 'price': exec_price, 'qty': qty, 'notional': notional, 'fee': buy_fee})
                    # 更新全局状态
                    total_qty += qty
                    total_cost += total_out

        # 卖出处理：对于每个已触发的单元格（flag==1），如果价格触及上轨，则卖出该单元格的持仓
        for cell in cells:
            if cell['flag'] == 1 and cell['qty'] > 0:
                upper = cell['upper']
                # 触发卖出条件
                if high >= upper - 1e-12:
                    # 执行价格（卖出时扣除滑点下浮）
                    exec_price = upper * (1.0 - slippage)
                    qty = cell['qty']
                    # 计算销售收入
                    proceeds = qty * exec_price
                    # 计算卖出手续费
                    sell_fee = proceeds * fee_rate
                    # 计算净收入
                    net = proceeds - sell_fee
                    cash += net
                    # 计算已实现利润 = 净收入 - 该单元格成本
                    realized = net - cell['cost']
                    realized_profit += realized
                    # 更新全局状态
                    total_qty -= qty
                    total_cost -= cell['cost']
                    # 重置单元格状态
                    cell['flag'] = 0
                    cell['qty'] = 0.0
                    cell['cost'] = 0.0
                    cell['buy_notional'] = 0.0
                    cell['execs'].append({'type': 'sell', 'price': exec_price, 'qty': qty, 'proceeds': proceeds, 'fee': sell_fee, 'realized': realized})

        # 计算持仓估值（使用收盘价）
        holdings_val = 0.0
        for cell in cells:
            if cell['qty'] > 0:
                holdings_val += cell['qty'] * close
        # 计算总资产
        equity = cash + holdings_val

        # 记录时间序列数据
        positions_timeseries.append(equity / F if F > 0 else 0.0)
        cash_ts.append(cash)
        holdings_ts.append(holdings_val)
        equity_ts.append(equity)
        avg_cost = (total_cost / total_qty) if total_qty > 0 else 0.0
        avg_cost_ts.append(avg_cost)

    # 创建结果DataFrame并添加时间序列数据
    df_result = df.copy().reset_index(drop=True)
    # 确保长度匹配（如果重置索引改变了索引）
    df_result['position'] = positions_timeseries
    df_result['cash'] = cash_ts
    df_result['holdings'] = holdings_ts
    df_result['equity'] = equity_ts
    df_result['avg_cost'] = avg_cost_ts

    # 构建grid_levels输出：网格点 + 单元格标注 + 止损线
    grid_levels = []
    for i, pval in enumerate(points):
        grid_levels.append({'name': f'P{i}', 'price': float(pval)})
    # for i in range(N):
    #     grid_levels.append({'name': f'格#{i} 上轨(卖出)', 'price': float(cells[i]['upper'])})
    #     grid_levels.append({'name': f'格#{i} 下轨(买入)', 'price': float(cells[i]['lower'])})
    grid_levels.append({'name': '止损线(建议)', 'price': float(stop_loss_price)})
    grid_levels = sorted(grid_levels, key=lambda x: x['price'])

    # 计算策略表现指标
    eq_arr = np.array(equity_ts, dtype=float) if len(equity_ts) > 0 else np.array([float(F)])
    # 计算峰值序列（累计最大值）
    peak = np.maximum.accumulate(eq_arr)
    # 计算回撤序列
    dd = (peak - eq_arr) / (peak + 1e-12)
    # 计算最大回撤
    max_dd_series = float(np.max(dd)) if eq_arr.size > 0 else 0.0

    # 计算未实现盈亏
    unrealized_pnl = (total_qty * df_result['close'].iloc[-1]) - total_cost if total_qty > 0 else 0.0

    metrics = {
        'final_cash': float(cash),  # 最终现金
        'final_holdings_value': float(holdings_ts[-1]) if holdings_ts else 0.0,  # 最终持仓价值
        'final_equity': float(equity_ts[-1]) if equity_ts else float(cash),  # 最终总资产
        'realized_profit': float(realized_profit),  # 已实现利润
        'unrealized_pnl': float(unrealized_pnl),  # 未实现盈亏
        'total_quantity': float(total_qty),  # 总持仓数量
        'avg_cost': float(avg_cost_ts[-1]) if avg_cost_ts else 0.0,  # 平均成本
        'max_drawdown_series': float(max_dd_series),  # 时间序列中的最大回撤
        'computed': {  # 计算出的网格参数
            'D': float(D),
            'A': float(A) if np.isfinite(A) else None,
            'idle_fund': float(idle_fund) if np.isfinite(idle_fund) else None,
            'sum_inv': float(sum_inv) if np.isfinite(sum_inv) else None,
            'max_drawdown_formula': float(max_drawdown) if np.isfinite(max_drawdown) else None,
        }
    }

    # 如果之前发现风险标志，添加人类友好的警报摘要
    # 将初始化警告转换为可读字符串
    if len(alerts) == 0:
        # 可能添加的合理性检查
        if A is None or not np.isfinite(A):
            alerts.append("[RISK_ALERT] 每格金额A无效或无限大。")
    # 去重
    alerts = list(dict.fromkeys(alerts))

    # 返回的'data'只包含回测引擎所需的必要列
    col_list = ['open', 'high', 'low', 'close']
    if 'volume' in df_result.columns:
        col_list.append('volume')
    col_list.extend(['position', 'cash', 'holdings', 'equity', 'avg_cost'])
    df_result = df_result[col_list]

    return {
        'data': df_result,
        'grid_levels': grid_levels,
        'alerts': alerts,
        'metrics': metrics
    }