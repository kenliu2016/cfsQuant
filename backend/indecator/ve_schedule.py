#!/usr/bin/env python3
"""
VE（波动率效率）指标定时任务执行脚本

该脚本负责定期计算和更新VE指标数据，支持不同时间周期的VE指标计算。

功能特性：
1. 支持高频、中频、低频周期的VE指标计算
2. 自动获取活跃交易对数据
3. 批量计算和存储VE指标结果
4. 错误处理和重试机制

作者: AI Assistant
创建时间: 2025-01-14
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import text

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)
sys.path.insert(0, current_dir)

from common.logger import LoggerFactory
from common.db import get_engine
from indecator.ve_calculator import VolatilityEfficiencyCalculator, fetch_active_usdt_symbols

logger = LoggerFactory.get_logger("indecator.ve_schedule")

# === 数据库连接 ===
engine = get_engine()

# === 周期配置 ===
PERIOD_CONFIGS = {
    'high_frequency': {
        'timeframes': ['3m', '5m', '15m', '30m'],
        'description': '高频周期 (3分钟, 5分钟, 15分钟, 30分钟)',
        'data_lookback_days': 7  # 7天数据
    },
    'medium_frequency': {
        'timeframes': ['1h', '2h', '4h'],
        'description': '中频周期 (1小时, 2小时, 4小时)',
        'data_lookback_days': 30  # 30天数据
    },
    'low_frequency': {
        'timeframes': ['1d', '2d', '3d'],
        'description': '低频周期 (1天, 2天, 3天)',
        'data_lookback_days': 365  # 1年数据
    }
}


def save_ve_result(exchange: str, symbol: str, timeframe: str, 
                  ve_data: dict, calculation_time: datetime) -> bool:
    """
    保存VE指标计算结果到数据库
    
    参数:
        exchange: 交易所名称
        symbol: 交易对符号
        timeframe: 时间周期
        ve_data: VE指标数据字典
        calculation_time: 计算时间
        
    返回:
        bool: 保存是否成功
    """
    try:
        sql = text("""
            INSERT INTO indecator_ve (
                exchange, symbol, timeframe, datetime, ve,
                actual_volatility, expected_volatility,
                volume_efficiency, volatility_efficiency, data_points
            ) VALUES (
                :exchange, :symbol, :timeframe, :datetime, :ve,
                :actual_volatility, :expected_volatility,
                :volume_efficiency, :volatility_efficiency, :data_points
            )
            ON CONFLICT (exchange, symbol, timeframe, datetime) 
            DO UPDATE SET
                ve = EXCLUDED.ve,
                actual_volatility = EXCLUDED.actual_volatility,
                expected_volatility = EXCLUDED.expected_volatility,
                volume_efficiency = EXCLUDED.volume_efficiency,
                volatility_efficiency = EXCLUDED.volatility_efficiency,
                data_points = EXCLUDED.data_points,
                updated_at = NOW()
        """)
        
        params = {
            'exchange': exchange,
            'symbol': symbol,
            'timeframe': timeframe,
            'datetime': calculation_time,
            've': ve_data.get('ve', 0.0),
            'actual_volatility': ve_data.get('actual_volatility', 0.0),
            'expected_volatility': ve_data.get('expected_volatility', 0.0),
            'volume_efficiency': ve_data.get('volume_efficiency', 1.0),
            'volatility_efficiency': ve_data.get('volatility_efficiency', 1.0),
            'data_points': ve_data.get('data_points', 0)
        }
        
        with engine.begin() as conn:
            conn.execute(sql, params)
        
        logger.info(f"保存VE指标成功: {exchange}-{symbol} {timeframe} VE={ve_data['ve']:.4f}")
        return True
        
    except Exception as e:
        logger.error(f"保存VE指标失败 {exchange}-{symbol} {timeframe}: {e}")
        return False


def create_batch_job(exchange: str, timeframe: str, symbols_count: int) -> int:
    """
    创建批量计算任务记录
    
    参数:
        exchange: 交易所名称
        timeframe: 时间周期
        symbols_count: 交易对数量
        
    返回:
        int: 任务ID
    """
    try:
        job_name = f"ve_calculation_{exchange}_{timeframe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        sql = text("""
            INSERT INTO indecator_ve_batch_jobs (
                job_name, exchange, timeframe, symbols_count, status
            ) VALUES (
                :job_name, :exchange, :timeframe, :symbols_count, 'running'
            )
            RETURNING id
        """)
        
        with engine.begin() as conn:
            result = conn.execute(sql, {
                'job_name': job_name,
                'exchange': exchange,
                'timeframe': timeframe,
                'symbols_count': symbols_count
            })
            job_id = result.scalar()
        
        logger.info(f"创建VE批量计算任务: {job_name} (ID: {job_id})")
        return job_id
        
    except Exception as e:
        logger.error(f"创建批量计算任务失败: {e}")
        return 0


def update_batch_job(job_id: int, processed_count: int, success_count: int, 
                    failed_count: int, status: str = 'running', 
                    error_message: str = None):
    """
    更新批量计算任务状态
    
    参数:
        job_id: 任务ID
        processed_count: 已处理数量
        success_count: 成功数量
        failed_count: 失败数量
        status: 任务状态
        error_message: 错误信息
    """
    try:
        sql = text("""
            UPDATE indecator_ve_batch_jobs 
            SET processed_count = :processed_count,
                success_count = :success_count,
                failed_count = :failed_count,
                status = :status,
                error_message = :error_message,
                updated_at = NOW()
            WHERE id = :job_id
        """)
        
        params = {
            'job_id': job_id,
            'processed_count': processed_count,
            'success_count': success_count,
            'failed_count': failed_count,
            'status': status,
            'error_message': error_message
        }
        
        if status == 'completed':
            params['completed_at'] = datetime.now()
            sql = text("""
                UPDATE indecator_ve_batch_jobs 
                SET processed_count = :processed_count,
                    success_count = :success_count,
                    failed_count = :failed_count,
                    status = :status,
                    error_message = :error_message,
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE id = :job_id
            """)
        
        with engine.begin() as conn:
            conn.execute(sql, params)
        
    except Exception as e:
        logger.error(f"更新批量计算任务失败: {e}")


def calculate_ve_for_period(exchange: str, symbols: list, timeframe: str, 
                          lookback_days: int, period_type: str) -> dict:
    """
    计算指定周期的VE指标
    
    参数:
        exchange: 交易所名称
        symbols: 交易对列表
        timeframe: 时间周期
        lookback_days: 回溯天数
        period_type: 周期类型
        
    返回:
        dict: 计算结果统计
    """
    logger.info(f"开始计算{period_type}周期VE指标: {exchange} {timeframe}")
    
    # 创建批量计算任务
    job_id = create_batch_job(exchange, timeframe, len(symbols))
    
    if job_id == 0:
        logger.error("创建批量计算任务失败，跳过本次计算")
        return {'success': 0, 'failed': len(symbols), 'total': len(symbols)}
    
    calculator = VolatilityEfficiencyCalculator(engine)
    processed_count = 0
    success_count = 0
    failed_count = 0
    
    calculation_time = datetime.now()
    
    for symbol in symbols:
        try:
            # 计算VE指标
            ve_data = calculator.calculate_ve_indicator(
                exchange, symbol, timeframe, lookback_days
            )
            
            # 保存结果
            if ve_data['data_points'] > 0:  # 确保有足够的数据点
                save_success = save_ve_result(
                    exchange, symbol, timeframe, ve_data, calculation_time
                )
                
                if save_success:
                    success_count += 1
                    logger.debug(f"VE指标计算成功: {exchange}-{symbol} VE={ve_data['ve']:.4f}")
                else:
                    failed_count += 1
                    logger.warning(f"VE指标保存失败: {exchange}-{symbol}")
            else:
                failed_count += 1
                logger.warning(f"数据点不足: {exchange}-{symbol} 数据点={ve_data['data_points']}")
                
        except Exception as e:
            failed_count += 1
            logger.error(f"VE指标计算失败 {exchange}-{symbol}: {e}")
        
        processed_count += 1
        
        # 每处理10个交易对更新一次任务状态
        if processed_count % 10 == 0:
            update_batch_job(job_id, processed_count, success_count, failed_count)
    
    # 更新最终任务状态
    final_status = 'completed' if failed_count < len(symbols) else 'failed'
    update_batch_job(job_id, processed_count, success_count, failed_count, final_status)
    
    logger.info(f"{period_type}周期VE指标计算完成: 成功{success_count}/失败{failed_count}/总计{len(symbols)}")
    
    return {
        'success': success_count,
        'failed': failed_count,
        'total': len(symbols),
        'job_id': job_id
    }


def run_ve_for_period(period_type: str, exchange: str = 'binance') -> dict:
    """
    运行指定周期的VE指标计算
    
    参数:
        period_type: 周期类型 (high_frequency, medium_frequency, low_frequency)
        exchange: 交易所名称
        
    返回:
        dict: 各时间周期的计算结果
    """
    if period_type not in PERIOD_CONFIGS:
        logger.error(f"不支持的周期类型: {period_type}")
        return {}
    
    config = PERIOD_CONFIGS[period_type]
    timeframes = config['timeframes']
    lookback_days = config['data_lookback_days']
    
    logger.info(f"开始执行{config['description']}VE指标计算")
    
    # 获取活跃交易对
    symbols = fetch_active_usdt_symbols(engine, exchange)
    
    if not symbols:
        logger.error(f"未找到{exchange}的活跃USDT交易对")
        return {}
    
    logger.info(f"获取到{len(symbols)}个活跃USDT交易对")
    
    results = {}
    
    for timeframe in timeframes:
        result = calculate_ve_for_period(
            exchange, symbols, timeframe, lookback_days, period_type
        )
        results[timeframe] = result
    
    return results


def main():
    """
    VE指标调度器主函数
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='VE指标计算调度器')
    parser.add_argument('--period', type=str, required=True,
                       choices=['high_frequency', 'medium_frequency', 'low_frequency', 'all'],
                       help='计算周期类型')
    parser.add_argument('--exchange', type=str, default='binance',
                       help='交易所名称 (默认: binance)')
    
    args = parser.parse_args()
    
    try:
        if args.period == 'all':
            # 执行所有周期
            for period_type in PERIOD_CONFIGS.keys():
                logger.info(f"开始执行{period_type}周期VE指标计算")
                results = run_ve_for_period(period_type, args.exchange)
                logger.info(f"{period_type}周期VE指标计算完成: {results}")
        else:
            # 执行指定周期
            results = run_ve_for_period(args.period, args.exchange)
            logger.info(f"VE指标计算完成: {results}")
        
        logger.info("VE指标计算任务全部完成")
        
    except Exception as e:
        logger.error(f"VE指标计算任务执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()