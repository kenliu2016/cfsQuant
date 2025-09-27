#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据迁移脚本
将minute_realtime_1、hour_realtime_1、day_realtime_1表的数据迁移到对应的正式表
"""

import psycopg2
import logging
from datetime import datetime
import argparse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'data_migration_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 数据库连接配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'quant',
    'user': 'cfs',
    'password': 'Aa520@cfs'
}

# 迁移配置
table_mappings = [
    {'source': 'minute_realtime_1', 'target': 'minute_realtime'},
    {'source': 'hour_realtime_1', 'target': 'hour_realtime'},
    {'source': 'day_realtime_1', 'target': 'day_realtime'}
]


def get_db_connection():
    """建立数据库连接"""
    try:
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            dbname=DB_CONFIG['dbname'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )
        conn.autocommit = False  # 使用事务
        logger.info(f"成功连接到数据库: {DB_CONFIG['dbname']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}")
        return conn
    except psycopg2.Error as e:
        logger.error(f"数据库连接失败: {e}")
        raise


def check_table_exists(conn, table_name):
    """检查表是否存在"""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table_name,))
            exists = cur.fetchone()[0]
            logger.info(f"表 '{table_name}' 存在: {exists}")
            return exists
    except psycopg2.Error as e:
        logger.error(f"检查表 '{table_name}' 存在性失败: {e}")
        raise


def get_table_column_names(conn, table_name):
    """获取表的列名"""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table_name,))
            columns = [row[0] for row in cur.fetchall()]
            logger.info(f"表 '{table_name}' 的列: {columns}")
            return columns
    except psycopg2.Error as e:
        logger.error(f"获取表 '{table_name}' 列名失败: {e}")
        raise


def migrate_data(conn, source_table, target_table, batch_size=10000):
    """迁移数据，使用分批处理"""
    try:
        # 检查源表和目标表是否存在
        if not check_table_exists(conn, source_table):
            logger.warning(f"源表 '{source_table}' 不存在，跳过迁移")
            return 0
        
        if not check_table_exists(conn, target_table):
            logger.error(f"目标表 '{target_table}' 不存在，无法迁移")
            raise ValueError(f"目标表 '{target_table}' 不存在")
        
        # 获取源表和目标表的列名
        source_columns = get_table_column_names(conn, source_table)
        target_columns = get_table_column_names(conn, target_table)
        
        # 找出共同的列
        common_columns = list(set(source_columns) & set(target_columns))
        if not common_columns:
            logger.error(f"源表 '{source_table}' 和目标表 '{target_table}' 没有共同的列，无法迁移")
            raise ValueError(f"源表和目标表没有共同的列")
        
        # 按照源表的顺序排序共同的列
        common_columns_sorted = [col for col in source_columns if col in common_columns]
        logger.info(f"共同的列: {common_columns_sorted}")
        
        # 构建列字符串
        columns_str = ', '.join(common_columns_sorted)
        placeholders = ', '.join(['%s'] * len(common_columns_sorted))
        
        # 获取源表的记录总数
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {source_table}")
            total_count = cur.fetchone()[0]
            logger.info(f"源表 '{source_table}' 共有 {total_count} 条记录")
            
            if total_count == 0:
                logger.info(f"源表 '{source_table}' 为空，跳过迁移")
                return 0
        
        # 分批迁移数据
        migrated_count = 0
        offset = 0
        
        with conn.cursor() as cur:
            while offset < total_count:
                # 读取一批数据
                select_query = f"SELECT {columns_str} FROM {source_table} LIMIT %s OFFSET %s"
                cur.execute(select_query, (batch_size, offset))
                batch_data = cur.fetchall()
                
                if not batch_data:
                    break
                
                # 插入数据，使用 ON CONFLICT 处理冲突
                insert_query = f"""
                    INSERT INTO {target_table} ({columns_str})
                    VALUES ({placeholders})
                    ON CONFLICT (exchange, code, datetime) DO UPDATE
                    SET
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume,
                        raw = EXCLUDED.raw,
                        updated_at = CURRENT_TIMESTAMP
                """
                
                # 批量执行插入
                # 处理可能的JSON类型字段
                processed_batch_data = []
                for row in batch_data:
                    processed_row = []
                    for i, col in enumerate(common_columns_sorted):
                        value = row[i]
                        # 检查是否是JSONB字段
                        if col == 'raw' and isinstance(value, dict):
                            # 将字典转换为JSON字符串
                            import json
                            processed_row.append(json.dumps(value))
                        else:
                            processed_row.append(value)
                    processed_batch_data.append(processed_row)
                
                psycopg2.extras.execute_batch(cur, insert_query, processed_batch_data)
                
                # 更新计数
                batch_count = len(batch_data)
                migrated_count += batch_count
                offset += batch_size
                
                logger.info(f"已迁移 {migrated_count}/{total_count} 条记录 ({source_table} -> {target_table})")
        
        # 提交事务
        conn.commit()
        logger.info(f"数据迁移完成: {migrated_count} 条记录从 {source_table} 迁移到 {target_table}")
        return migrated_count
    
    except psycopg2.Error as e:
        logger.error(f"数据迁移失败: {e}")
        conn.rollback()
        raise
    except Exception as e:
        logger.error(f"迁移过程中发生错误: {e}")
        conn.rollback()
        raise


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='将测试表数据迁移到正式表')
    parser.add_argument('--batch-size', type=int, default=10000, help='每批处理的记录数')
    parser.add_argument('--tables', type=str, choices=['minute', 'hour', 'day', 'all'], default='all', 
                        help='要迁移的表类型，默认迁移所有表')
    
    args = parser.parse_args()
    
    # 根据参数选择要迁移的表
    selected_tables = []
    if args.tables == 'all':
        selected_tables = table_mappings
    else:
        for mapping in table_mappings:
            if args.tables in mapping['source']:
                selected_tables.append(mapping)
    
    conn = None
    try:
        # 建立数据库连接
        conn = get_db_connection()
        
        # 迁移数据
        total_migrated = 0
        for mapping in selected_tables:
            source_table = mapping['source']
            target_table = mapping['target']
            
            logger.info(f"开始迁移数据: {source_table} -> {target_table}")
            count = migrate_data(conn, source_table, target_table, args.batch_size)
            total_migrated += count
        
        logger.info(f"所有迁移任务完成，共迁移 {total_migrated} 条记录")
    
    except Exception as e:
        logger.error(f"迁移失败: {e}")
        return 1
    finally:
        if conn:
            conn.close()
            logger.info("已关闭数据库连接")
    
    return 0


if __name__ == "__main__":
    # 导入缺失的extras模块
    import psycopg2.extras
    exit(main())