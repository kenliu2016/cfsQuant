"""
Dashboard物化视图应用脚本
该脚本用于创建和刷新dashboard相关的物化视图

功能特性：
1. 智能SQL语句分割（处理函数定义中的分号）
2. 详细的错误报告和日志记录
3. 视图创建后的验证和刷新
4. 支持并发刷新和普通刷新

Usage:
    python backend/scripts/apply_dashboard_views.py
"""

import os
import sys
from pathlib import Path

# Add the parent directory to Python path to import common modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.db import get_engine
from common.logger import LoggerFactory
from sqlalchemy import text


logger = LoggerFactory.get_logger("scripts.apply_dashboard_views")


SQL_FILE = Path(__file__).resolve().parent.parent / "dbscripts" / "dashboard_materialized_views.sql"


DROP_STATEMENTS = """
DROP MATERIALIZED VIEW IF EXISTS dashboard_summary_view CASCADE;
DROP MATERIALIZED VIEW IF EXISTS dashboard_coin_analysis CASCADE;
DROP MATERIALIZED VIEW IF EXISTS dashboard_strong_weak_coins CASCADE;
DROP MATERIALIZED VIEW IF EXISTS dashboard_market_sentiment CASCADE;
DROP FUNCTION IF EXISTS refresh_all_dashboard_views() CASCADE;
DROP PROCEDURE IF EXISTS manual_refresh_dashboard_views() CASCADE;
"""


def split_sql_statements(sql_content):
    """
    智能分割SQL语句，正确处理函数定义中的分号
    
    Args:
        sql_content: SQL文件内容
        
    Returns:
        list: 分割后的SQL语句列表
    """
    sql_statements = []
    current_statement = ""
    in_function = False
    in_dollar_quote = False
    dollar_quote_tag = ""
    
    for line in sql_content.split('\n'):
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith('--'):
            continue
            
        # 检查是否进入函数定义
        if 'CREATE OR REPLACE FUNCTION' in stripped_line.upper():
            in_function = True
        
        # 检查是否进入dollar-quoted字符串
        if '$$' in stripped_line and not in_dollar_quote:
            in_dollar_quote = True
            dollar_quote_tag = '$$'
        elif dollar_quote_tag in stripped_line and in_dollar_quote:
            in_dollar_quote = False
            dollar_quote_tag = ""
        
        current_statement += line + '\n'
        
        # 如果不在函数定义或dollar-quoted字符串中，且遇到分号，则分割语句
        if not in_function and not in_dollar_quote and stripped_line.endswith(';'):
            sql_statements.append(current_statement.strip())
            current_statement = ""
        
        # 检查完整的函数定义结束
        if in_function and 'LANGUAGE plpgsql;' in stripped_line and not in_dollar_quote:
            in_function = False
            sql_statements.append(current_statement.strip())
            current_statement = ""
    
    # 添加最后一个语句（如果有）
    if current_statement.strip():
        sql_statements.append(current_statement.strip())
    
    return sql_statements


def check_view_exists(conn, view_name):
    """
    检查物化视图是否存在
    
    Args:
        conn: 数据库连接
        view_name: 视图名称
        
    Returns:
        bool: 视图是否存在
    """
    try:
        with conn.connection.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_matviews 
                    WHERE matviewname = %s
                );
            """, (view_name,))
            
            exists = cur.fetchone()[0]
            logger.info(f"物化视图 {view_name} {'存在' if exists else '不存在'}")
            return exists
            
    except Exception as e:
        logger.error(f"检查物化视图 {view_name} 存在性失败: {e}")
        return False


def refresh_view(conn, view_name):
    """
    刷新物化视图
    
    Args:
        conn: 数据库连接
        view_name: 视图名称
        
    Returns:
        bool: 刷新是否成功
    """
    try:
        with conn.connection.cursor() as cur:
            # 尝试并发刷新
            refresh_sql = f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name};"
            cur.execute(refresh_sql)
            
        logger.info(f"物化视图 {view_name} 并发刷新成功")
        return True
        
    except Exception as e:
        logger.warning(f"物化视图 {view_name} 并发刷新失败: {e}")
        
        # 如果并发刷新失败，尝试普通刷新
        try:
            with conn.connection.cursor() as cur:
                refresh_sql = f"REFRESH MATERIALIZED VIEW {view_name};"
                cur.execute(refresh_sql)
            
            logger.info(f"物化视图 {view_name} 普通刷新成功")
            return True
        except Exception as e2:
            logger.error(f"物化视图 {view_name} 普通刷新也失败: {e2}")
            return False


def get_view_row_count(conn, view_name):
    """
    获取物化视图的行数
    
    Args:
        conn: 数据库连接
        view_name: 视图名称
        
    Returns:
        int: 行数，失败返回-1
    """
    try:
        with conn.connection.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {view_name};")
            count = cur.fetchone()[0]
        
        logger.info(f"物化视图 {view_name} 有 {count} 行数据")
        return count
        
    except Exception as e:
        logger.error(f"获取物化视图 {view_name} 行数失败: {e}")
        return -1


def run():
    """主执行函数"""
    if not SQL_FILE.exists():
        logger.error(f"Dashboard SQL文件不存在: {SQL_FILE}")
        sys.exit(1)

    engine = get_engine()

    try:
        # 读取SQL文件内容
        sql_content = SQL_FILE.read_text(encoding="utf-8")
        
        # 智能分割SQL语句
        sql_statements = split_sql_statements(sql_content)
        
        logger.info(f"SQL文件分割为 {len(sql_statements)} 个语句")
        
        # 执行所有SQL语句（使用自动提交模式）
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            for i, statement in enumerate(sql_statements, 1):
                if statement.strip():
                    try:
                        logger.info(f"执行SQL语句 {i}/{len(sql_statements)}")
                        conn.execute(text(statement))
                        logger.info(f"SQL语句 {i} 执行成功")
                    except Exception as e:
                        logger.error(f"SQL语句 {i} 执行失败: {e}")
                        logger.error(f"失败语句: {statement[:200]}...")
                        # 对于某些错误（如对象已存在），继续执行
                        if "already exists" in str(e).lower() or "does not exist" in str(e).lower():
                            logger.warning(f"忽略已知错误，继续执行: {e}")
                            continue
                        else:
                            raise
        
        logger.info("Dashboard物化视图创建完成")
        
        # 验证视图创建情况
        view_names = [
            'dashboard_market_sentiment',
            'dashboard_strong_weak_coins', 
            'dashboard_coin_analysis',
            'dashboard_summary_view'
        ]
        
        logger.info("验证物化视图创建情况...")
        
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            for view_name in view_names:
                if check_view_exists(conn, view_name):
                    # 获取行数
                    row_count = get_view_row_count(conn, view_name)
                    if row_count >= 0:
                        logger.info(f"✓ {view_name} 创建成功，包含 {row_count} 行数据")
                    else:
                        logger.warning(f"✓ {view_name} 创建成功，但无法获取行数")
                else:
                    logger.error(f"✗ {view_name} 创建失败")
        
        logger.info("Dashboard物化视图创建和验证完成")
        
    except Exception as e:
        logger.error(f"执行过程中发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run()
