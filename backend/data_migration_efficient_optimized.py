#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化的高效数据迁移脚本
使用PostgreSQL原生的INSERT INTO ... SELECT语句进行数据迁移
适用于表结构完全相同的场景，特别是源表无分区而目标表有分区的情况
优化点：减小批处理大小，增加更详细的日志，优化分页策略
"""

import psycopg2
import logging
from datetime import datetime
import argparse
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'data_migration_efficient_optimized_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
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

def get_table_count(conn, table_name):
    """获取表的记录数"""
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cur.fetchone()[0]
            logger.info(f"表 '{table_name}' 共有 {count:,} 条记录")
            return count
    except psycopg2.Error as e:
        logger.error(f"获取表 '{table_name}' 记录数失败: {e}")
        raise

def migrate_data_efficient(conn, source_table, target_table, batch_size=100000):
    """
    使用PostgreSQL原生的INSERT INTO ... SELECT语句高效迁移数据
    适用于表结构完全相同的情况
    优化点：减小批处理大小，增加详细日志，优化分页策略
    """
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
        
        # 验证表结构是否兼容
        if set(source_columns) != set(target_columns):
            logger.warning(f"源表和目标表的列不完全相同，但仍尝试迁移共同的列")
            common_columns = list(set(source_columns) & set(target_columns))
            columns_str = ', '.join(common_columns)
        else:
            # 如果表结构完全相同，可以使用简化语法
            columns_str = '*'
        
        # 获取源表的记录总数
        total_count = get_table_count(conn, source_table)
        
        if total_count == 0:
            logger.info(f"源表 '{source_table}' 为空，跳过迁移")
            return 0
        
        # 分批迁移数据
        migrated_count = 0
        batch_num = 1
        
        with conn.cursor() as cur:
            # 获取源表的主键列，用于分页
            primary_key_columns = []
            cur.execute("""
                SELECT a.attname
                FROM   pg_index i
                JOIN   pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE  i.indrelid = %s::regclass
                AND    i.indisprimary;
            """, (source_table,))
            for row in cur.fetchall():
                primary_key_columns.append(row[0])
            
            if not primary_key_columns:
                logger.warning(f"源表 '{source_table}' 没有主键，使用LIMIT/OFFSET方式分页")
                
                # 使用LIMIT/OFFSET方式分批迁移
                while migrated_count < total_count:
                    start_time = time.time()
                    
                    # 构建INSERT语句
                    insert_query = f"""
                        INSERT INTO {target_table}
                        SELECT {columns_str} FROM {source_table}
                        LIMIT %s OFFSET %s
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
                    
                    # 执行迁移
                    logger.info(f"执行批次 {batch_num}: LIMIT {batch_size}, OFFSET {migrated_count}")
                    cur.execute(insert_query, (batch_size, migrated_count))
                    batch_migrated = cur.rowcount
                    
                    if batch_migrated == 0:
                        logger.warning(f"批次 {batch_num} 没有迁移任何记录，可能已完成")
                        break
                    
                    migrated_count += batch_migrated
                    duration = time.time() - start_time
                    
                    progress_percent = (migrated_count / total_count) * 100 if total_count > 0 else 0
                    logger.info(f"批次 {batch_num}: 已迁移 {migrated_count:,}/{total_count:,} 条记录 ({progress_percent:.2f}%), 批次迁移 {batch_migrated:,} 条, 耗时: {duration:.2f} 秒")
                    batch_num += 1
                    
                    # 定期提交事务，避免事务过大
                    if batch_num % 10 == 0:
                        conn.commit()
                        logger.info(f"已提交部分事务，当前已迁移 {migrated_count:,} 条记录")
            else:
                # 如果有主键，使用更高效的主键范围分页
                logger.info(f"使用主键列 '{', '.join(primary_key_columns)}' 进行高效分页")
                
                # 对于复合主键，使用datetime列进行分页，因为它是时间序列数据
                if len(primary_key_columns) > 1:
                    # 尝试使用datetime列进行分页，更适合时间序列数据
                    if 'datetime' in source_columns:
                        logger.info("检测到datetime列，使用datetime进行分页，更适合时间序列数据")
                        primary_key = 'datetime'
                    else:
                        # 否则使用第一个主键列
                        primary_key = primary_key_columns[0]
                else:
                    primary_key = primary_key_columns[0]
                
                # 获取主键范围
                cur.execute(f"SELECT MIN({primary_key}), MAX({primary_key}) FROM {source_table}")
                min_pk, max_pk = cur.fetchone()
                
                if min_pk is None or max_pk is None:
                    logger.info(f"源表 '{source_table}' 为空或主键值异常，跳过迁移")
                    return 0
                
                # 计算步长
                if isinstance(min_pk, (int, float)) or isinstance(min_pk, datetime):
                    # 数值型或日期时间型主键
                    if isinstance(min_pk, datetime):
                        # 日期时间型主键处理
                        logger.info(f"使用日期时间型主键 '{primary_key}' 进行分页")
                        # 计算总时间范围
                        time_diff = max_pk - min_pk
                        # 计算每批应处理的时间范围
                        batch_time_diff = time_diff * (batch_size / total_count)
                        current_pk = min_pk
                        
                        while current_pk < max_pk:
                            start_time = time.time()
                            next_pk = current_pk + batch_time_diff
                            
                            # 构建INSERT语句
                            insert_query = f"""
                                INSERT INTO {target_table}
                                SELECT {columns_str} FROM {source_table}
                                WHERE {primary_key} >= %s AND {primary_key} < %s
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
                            
                            # 执行迁移
                            logger.info(f"执行批次 {batch_num}: {primary_key} >= {current_pk}, {primary_key} < {next_pk}")
                            cur.execute(insert_query, (current_pk, next_pk))
                            batch_migrated = cur.rowcount
                            
                            if batch_migrated == 0:
                                logger.warning(f"批次 {batch_num} 没有迁移任何记录，调整时间范围")
                                current_pk = next_pk
                                continue
                            
                            migrated_count += batch_migrated
                            current_pk = next_pk
                            duration = time.time() - start_time
                            
                            progress_percent = (migrated_count / total_count) * 100 if total_count > 0 else 0
                            logger.info(f"批次 {batch_num}: 已迁移 {migrated_count:,}/{total_count:,} 条记录 ({progress_percent:.2f}%), 批次迁移 {batch_migrated:,} 条, 耗时: {duration:.2f} 秒")
                            batch_num += 1
                            
                            # 定期提交事务，避免事务过大
                            if batch_num % 10 == 0:
                                conn.commit()
                                logger.info(f"已提交部分事务，当前已迁移 {migrated_count:,} 条记录")
                        
                        # 处理最后一批可能遗漏的数据
                        if migrated_count < total_count:
                            logger.info(f"处理最后一批数据: {primary_key} >= {current_pk}")
                            insert_query = f"""
                                INSERT INTO {target_table}
                                SELECT {columns_str} FROM {source_table}
                                WHERE {primary_key} >= %s
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
                            cur.execute(insert_query, (current_pk,))
                            batch_migrated = cur.rowcount
                            migrated_count += batch_migrated
                            logger.info(f"最后一批: 额外迁移 {batch_migrated:,} 条记录")
                    else:
                        # 数值型主键
                        step = (max_pk - min_pk) / ((total_count + batch_size - 1) // batch_size)
                        current_pk = min_pk
                        
                        while current_pk < max_pk:
                            start_time = time.time()
                            next_pk = current_pk + step
                            
                            # 构建INSERT语句
                            insert_query = f"""
                                INSERT INTO {target_table}
                                SELECT {columns_str} FROM {source_table}
                                WHERE {primary_key} >= %s AND {primary_key} < %s
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
                            
                            # 执行迁移
                            logger.info(f"执行批次 {batch_num}: {primary_key} >= {current_pk}, {primary_key} < {next_pk}")
                            cur.execute(insert_query, (current_pk, next_pk))
                            batch_migrated = cur.rowcount
                            
                            if batch_migrated == 0:
                                logger.warning(f"批次 {batch_num} 没有迁移任何记录，调整步长")
                                current_pk = next_pk
                                continue
                            
                            migrated_count += batch_migrated
                            current_pk = next_pk
                            duration = time.time() - start_time
                            
                            progress_percent = (migrated_count / total_count) * 100 if total_count > 0 else 0
                            logger.info(f"批次 {batch_num}: 已迁移 {migrated_count:,}/{total_count:,} 条记录 ({progress_percent:.2f}%), 批次迁移 {batch_migrated:,} 条, 耗时: {duration:.2f} 秒")
                            batch_num += 1
                        
                        # 处理最后一批可能遗漏的数据
                        if migrated_count < total_count:
                            logger.info(f"处理最后一批数据: {primary_key} >= {current_pk}")
                            insert_query = f"""
                                INSERT INTO {target_table}
                                SELECT {columns_str} FROM {source_table}
                                WHERE {primary_key} >= %s
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
                            cur.execute(insert_query, (current_pk,))
                            batch_migrated = cur.rowcount
                            migrated_count += batch_migrated
                            logger.info(f"最后一批: 额外迁移 {batch_migrated:,} 条记录")
                else:
                    # 非数值型主键，回退到LIMIT/OFFSET方式，但使用更小的批处理大小
                    logger.warning(f"主键 '{primary_key}' 不是数值型或日期时间型，回退到LIMIT/OFFSET方式分页")
                    while migrated_count < total_count:
                        start_time = time.time()
                        
                        insert_query = f"""
                            INSERT INTO {target_table}
                            SELECT {columns_str} FROM {source_table}
                            LIMIT %s OFFSET %s
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
                        
                        logger.info(f"执行批次 {batch_num}: LIMIT {batch_size}, OFFSET {migrated_count}")
                        cur.execute(insert_query, (batch_size, migrated_count))
                        batch_migrated = cur.rowcount
                        
                        if batch_migrated == 0:
                            logger.warning(f"批次 {batch_num} 没有迁移任何记录，可能已完成")
                            break
                        
                        migrated_count += batch_migrated
                        duration = time.time() - start_time
                        
                        progress_percent = (migrated_count / total_count) * 100 if total_count > 0 else 0
                        logger.info(f"批次 {batch_num}: 已迁移 {migrated_count:,}/{total_count:,} 条记录 ({progress_percent:.2f}%), 批次迁移 {batch_migrated:,} 条, 耗时: {duration:.2f} 秒")
                        batch_num += 1
                    
                    # 增加定期提交，避免事务过大
                    if batch_num % 10 == 0:
                        conn.commit()
                        logger.info(f"已提交部分事务，当前已迁移 {migrated_count:,} 条记录")
        
        # 提交事务
        conn.commit()
        logger.info(f"数据迁移完成: {migrated_count:,} 条记录从 {source_table} 迁移到 {target_table}")
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
    parser = argparse.ArgumentParser(description='优化的高效数据迁移工具')
    parser.add_argument('--batch-size', type=int, default=100000, help='每批处理的记录数，默认100,000')
    parser.add_argument('--tables', type=str, choices=['minute', 'hour', 'day', 'all'], default='all', 
                        help='要迁移的表类型，默认迁移所有表')
    parser.add_argument('--test', action='store_true', help='测试模式，只迁移少量数据')
    
    args = parser.parse_args()
    
    # 根据参数选择要迁移的表
    selected_tables = []
    if args.tables == 'all':
        selected_tables = table_mappings
    else:
        for mapping in table_mappings:
            if args.tables in mapping['source']:
                selected_tables.append(mapping)
    
    # 测试模式下使用更小的批处理大小
    batch_size = args.batch_size
    if args.test:
        batch_size = 1000  # 测试模式只迁移1000条记录
        logger.info(f"测试模式启用: 批处理大小设置为 {batch_size}")
    
    conn = None
    try:
        # 建立数据库连接
        conn = get_db_connection()
        
        # 迁移数据
        total_migrated = 0
        for mapping in selected_tables:
            source_table = mapping['source']
            target_table = mapping['target']
            
            logger.info(f"开始高效迁移数据: {source_table} -> {target_table}")
            count = migrate_data_efficient(conn, source_table, target_table, batch_size)
            total_migrated += count
        
        logger.info(f"所有迁移任务完成，共迁移 {total_migrated:,} 条记录")
    
    except Exception as e:
        logger.error(f"迁移失败: {e}")
        return 1
    finally:
        if conn:
            conn.close()
            logger.info("已关闭数据库连接")
    
    return 0

if __name__ == "__main__":
    exit(main())