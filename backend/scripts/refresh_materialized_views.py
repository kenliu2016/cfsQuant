#!/usr/bin/env python3
"""
物化视图自动刷新脚本
该脚本用于定时刷新dashboard相关的物化视图，实现每15分钟自动更新
"""

import psycopg2
import time
import logging
import sys
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/materialized_views_refresh.log'),
        logging.StreamHandler()
    ]
)

def refresh_materialized_views():
    """
    刷新所有dashboard相关的物化视图
    """
    try:
        # 连接数据库
        conn = psycopg2.connect(
            host='localhost',
            port='5432',
            database='quant',
            user='cfs',
            password='Cc563479,.'
        )
        
        cursor = conn.cursor()
        
        # 需要刷新的物化视图列表
        materialized_views = [
            'dashboard_market_sentiment',
            'dashboard_strong_weak_coins', 
            'dashboard_coin_analysis',
            'dashboard_summary_view'
        ]
        
        refresh_results = {}
        
        for view_name in materialized_views:
            try:
                # 检查物化视图是否存在
                cursor.execute('''
                    SELECT schemaname, matviewname 
                    FROM pg_matviews 
                    WHERE schemaname = 'public' 
                    AND matviewname = %s;
                ''', (view_name,))
                
                if cursor.fetchone():
                    # 刷新物化视图
                    start_time = datetime.now()
                    cursor.execute(f'REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name};')
                    end_time = datetime.now()
                    
                    refresh_time = (end_time - start_time).total_seconds()
                    refresh_results[view_name] = {
                        'status': 'success',
                        'refresh_time': refresh_time
                    }
                    
                    logging.info(f'✓ 成功刷新物化视图: {view_name} (耗时: {refresh_time:.2f}秒)')
                else:
                    refresh_results[view_name] = {
                        'status': 'not_found',
                        'refresh_time': 0
                    }
                    logging.warning(f'⚠ 物化视图不存在: {view_name}')
                    
            except Exception as e:
                refresh_results[view_name] = {
                    'status': 'error',
                    'error': str(e)
                }
                logging.error(f'✗ 刷新物化视图失败 {view_name}: {e}')
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return refresh_results
        
    except Exception as e:
        logging.error(f'✗ 数据库连接失败: {e}')
        return {'error': str(e)}

def main():
    """
    主函数 - 实现每15分钟自动刷新
    """
    logging.info('=== 物化视图自动刷新服务启动 ===')
    logging.info('配置: 每15分钟刷新一次物化视图')
    
    refresh_interval = 15 * 60  # 15分钟（秒）
    
    while True:
        try:
            # 记录开始时间
            cycle_start = datetime.now()
            logging.info(f'开始刷新周期: {cycle_start.strftime("%Y-%m-%d %H:%M:%S")}')
            
            # 刷新物化视图
            results = refresh_materialized_views()
            
            # 记录结束时间
            cycle_end = datetime.now()
            cycle_duration = (cycle_end - cycle_start).total_seconds()
            
            # 统计结果
            success_count = sum(1 for r in results.values() if r.get('status') == 'success')
            error_count = sum(1 for r in results.values() if r.get('status') == 'error')
            not_found_count = sum(1 for r in results.values() if r.get('status') == 'not_found')
            
            logging.info(f'刷新周期完成: 成功={success_count}, 失败={error_count}, 不存在={not_found_count}, 总耗时={cycle_duration:.2f}秒')
            
            # 计算下一次刷新时间
            next_refresh = cycle_start.timestamp() + refresh_interval
            wait_time = max(0, next_refresh - datetime.now().timestamp())
            
            if wait_time > 0:
                logging.info(f'等待下一次刷新: {wait_time:.0f}秒后 ({datetime.fromtimestamp(next_refresh).strftime("%H:%M:%S")})')
                time.sleep(wait_time)
            else:
                # 如果刷新耗时超过了间隔时间，立即开始下一次刷新
                logging.warning('刷新耗时超过间隔时间，立即开始下一次刷新')
                
        except KeyboardInterrupt:
            logging.info('收到中断信号，停止服务')
            break
        except Exception as e:
            logging.error(f'刷新周期发生错误: {e}')
            # 发生错误时等待一段时间再重试
            time.sleep(60)

if __name__ == '__main__':
    # 测试模式：单次刷新
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        import sys
        print('=== 测试模式：单次刷新物化视图 ===')
        results = refresh_materialized_views()
        print('刷新完成:', results)
    else:
        # 正常模式：持续运行
        main()