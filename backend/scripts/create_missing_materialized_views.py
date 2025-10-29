#!/usr/bin/env python3
"""
创建缺失的物化视图脚本
该脚本创建dashboard_coin_analysis和dashboard_summary_view物化视图
"""

import psycopg2
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def create_missing_materialized_views():
    """
    创建缺失的物化视图
    """
    try:
        # 连接数据库并设置自动提交模式
        conn = psycopg2.connect(
            host='localhost',
            port='5432',
            database='quant',
            user='cfs',
            password='Cc563479,.'
        )
        conn.autocommit = True
        
        cursor = conn.cursor()
        
        # 检查缺失的物化视图
        missing_views = []
        
        views_to_check = ['dashboard_coin_analysis', 'dashboard_summary_view']
        
        for view_name in views_to_check:
            cursor.execute('''
                SELECT schemaname, matviewname 
                FROM pg_matviews 
                WHERE schemaname = 'public' 
                AND matviewname = %s;
            ''', (view_name,))
            
            if not cursor.fetchone():
                missing_views.append(view_name)
                logging.info(f'发现缺失的物化视图: {view_name}')
            else:
                logging.info(f'物化视图已存在: {view_name}')
        
        if not missing_views:
            logging.info('所有物化视图都已存在，无需创建')
            return {'status': 'all_exist'}
        
        # 读取SQL文件内容
        with open('dbscripts/dashboard_materialized_views.sql', 'r') as f:
            sql_content = f.read()
        
        results = {}
        
        # 创建缺失的物化视图
        for view_name in missing_views:
            try:
                # 提取特定物化视图的创建语句
                if view_name == 'dashboard_coin_analysis':
                    # 查找dashboard_coin_analysis的创建语句
                    start_marker = '-- ============ Dashboard币种分析物化视图 ============'
                    end_marker = '-- ============ Dashboard汇总物化视图 ============'
                elif view_name == 'dashboard_summary_view':
                    # 查找dashboard_summary_view的创建语句
                    start_marker = '-- ============ Dashboard汇总物化视图 ============'
                    end_marker = '-- ============ 视图注释和说明 ============'
                
                start_idx = sql_content.find(start_marker)
                end_idx = sql_content.find(end_marker)
                
                if start_idx != -1 and end_idx != -1:
                    create_sql = sql_content[start_idx:end_idx]
                    
                    # 执行创建语句
                    cursor.execute(create_sql)
                    logging.info(f'✓ 成功创建物化视图: {view_name}')
                    results[view_name] = {'status': 'created'}
                else:
                    logging.error(f'✗ 在SQL文件中找不到物化视图定义: {view_name}')
                    results[view_name] = {'status': 'sql_not_found'}
                    
            except Exception as e:
                logging.error(f'✗ 创建物化视图失败 {view_name}: {e}')
                results[view_name] = {'status': 'error', 'error': str(e)}
        
        cursor.close()
        conn.close()
        
        return results
        
    except Exception as e:
        logging.error(f'✗ 数据库连接失败: {e}')
        return {'error': str(e)}

def create_simple_materialized_views():
    """
    创建简化的物化视图（如果复杂版本失败）
    """
    try:
        # 连接数据库并设置自动提交模式
        conn = psycopg2.connect(
            host='localhost',
            port='5432',
            database='quant',
            user='cfs',
            password='Cc563479,.'
        )
        conn.autocommit = True
        
        cursor = conn.cursor()
        
        results = {}
        
        # 创建简化的dashboard_coin_analysis
        try:
            create_coin_analysis_sql = '''
CREATE MATERIALIZED VIEW IF NOT EXISTS dashboard_coin_analysis AS
SELECT 
    symbol,
    close as current_price,
    market_cap,
    quote_volume as total_volume_24h,
    vmr as vmr_24h,
    NOW() as view_refresh_time
FROM market_ohlcv_1d
WHERE bucket >= NOW() - INTERVAL '1 day'
    AND market_cap > 100000000
    AND close > 0
WITH DATA;

CREATE INDEX IF NOT EXISTS idx_dashboard_coin_analysis_symbol 
    ON dashboard_coin_analysis(symbol);
'''
            cursor.execute(create_coin_analysis_sql)
            logging.info(f'✓ 成功创建简化版物化视图: dashboard_coin_analysis')
            results['dashboard_coin_analysis'] = {'status': 'created_simple'}
        except Exception as e:
            logging.error(f'✗ 创建简化版物化视图失败 dashboard_coin_analysis: {e}')
            results['dashboard_coin_analysis'] = {'status': 'error', 'error': str(e)}
        
        # 创建简化的dashboard_summary_view
        try:
            create_summary_sql = '''
CREATE MATERIALIZED VIEW IF NOT EXISTS dashboard_summary_view AS
SELECT 
    (SELECT COUNT(*) FROM market_ohlcv_1d WHERE bucket >= NOW() - INTERVAL '1 day' AND market_cap > 100000000) as total_coins,
    (SELECT COUNT(*) FROM market_ohlcv_1d WHERE bucket >= NOW() - INTERVAL '1 day' AND market_cap > 100000000 AND return_pct > 0) as rising_coins,
    (SELECT COUNT(*) FROM market_ohlcv_1d WHERE bucket >= NOW() - INTERVAL '1 day' AND market_cap > 100000000 AND return_pct < 0) as falling_coins,
    NOW() as last_updated
WITH DATA;

CREATE INDEX IF NOT EXISTS idx_dashboard_summary_view_last_updated 
    ON dashboard_summary_view(last_updated DESC);
'''
            cursor.execute(create_summary_sql)
            logging.info(f'✓ 成功创建简化版物化视图: dashboard_summary_view')
            results['dashboard_summary_view'] = {'status': 'created_simple'}
        except Exception as e:
            logging.error(f'✗ 创建简化版物化视图失败 dashboard_summary_view: {e}')
            results['dashboard_summary_view'] = {'status': 'error', 'error': str(e)}
        
        cursor.close()
        conn.close()
        
        return results
        
    except Exception as e:
        logging.error(f'✗ 数据库连接失败: {e}')
        return {'error': str(e)}

if __name__ == '__main__':
    print('=== 创建缺失的物化视图 ===')
    
    # 首先尝试使用SQL文件中的完整定义
    print('尝试使用SQL文件中的完整定义...')
    results = create_missing_materialized_views()
    
    # 如果完整定义失败，尝试简化版本
    if any(r.get('status') in ['sql_not_found', 'error'] for r in results.values() if isinstance(r, dict)):
        print('完整定义失败，尝试简化版本...')
        simple_results = create_simple_materialized_views()
        results.update(simple_results)
    
    print('创建完成:', results)