#!/usr/bin/env python3
"""
物化视图索引创建脚本
该脚本为物化视图创建唯一索引，以支持并发刷新功能
"""

import psycopg2
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def create_materialized_view_indexes():
    """
    为物化视图创建唯一索引
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
        
        # 物化视图索引配置
        index_configs = [
            {
                'view_name': 'dashboard_market_sentiment',
                'index_name': 'idx_dashboard_market_sentiment_unique',
                'index_columns': 'total_coins, rising_coins, falling_coins'
            },
            {
                'view_name': 'dashboard_strong_weak_coins',
                'index_name': 'idx_dashboard_strong_weak_coins_unique',
                'index_columns': 'symbol, current_price'
            },
            {
                'view_name': 'dashboard_coin_analysis',
                'index_name': 'idx_dashboard_coin_analysis_unique',
                'index_columns': 'symbol'
            },
            {
                'view_name': 'dashboard_summary_view',
                'index_name': 'idx_dashboard_summary_view_unique',
                'index_columns': 'total_coins, rising_coins, falling_coins'
            }
        ]
        
        results = {}
        
        for config in index_configs:
            view_name = config['view_name']
            index_name = config['index_name']
            index_columns = config['index_columns']
            
            try:
                # 检查物化视图是否存在
                cursor.execute('''
                    SELECT schemaname, matviewname 
                    FROM pg_matviews 
                    WHERE schemaname = 'public' 
                    AND matviewname = %s;
                ''', (view_name,))
                
                if cursor.fetchone():
                    # 检查索引是否已存在
                    cursor.execute('''
                        SELECT indexname 
                        FROM pg_indexes 
                        WHERE schemaname = 'public' 
                        AND tablename = %s 
                        AND indexname = %s;
                    ''', (view_name, index_name))
                    
                    if cursor.fetchone():
                        logging.info(f'索引已存在: {index_name}')
                        results[view_name] = {'status': 'exists', 'index_name': index_name}
                    else:
                        # 创建唯一索引
                        create_index_sql = f'''
                            CREATE UNIQUE INDEX CONCURRENTLY {index_name} 
                            ON {view_name} ({index_columns});
                        '''
                        
                        cursor.execute(create_index_sql)
                        logging.info(f'✓ 成功创建索引: {index_name} 在物化视图 {view_name} 上')
                        results[view_name] = {'status': 'created', 'index_name': index_name}
                else:
                    logging.warning(f'物化视图不存在: {view_name}')
                    results[view_name] = {'status': 'view_not_found'}
                    
            except Exception as e:
                logging.error(f'✗ 创建索引失败 {view_name}: {e}')
                results[view_name] = {'status': 'error', 'error': str(e)}
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return results
        
    except Exception as e:
        logging.error(f'✗ 数据库连接失败: {e}')
        return {'error': str(e)}

if __name__ == '__main__':
    print('=== 创建物化视图唯一索引 ===')
    results = create_materialized_view_indexes()
    print('索引创建完成:', results)