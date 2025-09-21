#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库DDL导出工具
功能：导出PostgreSQL数据库中所有表、视图、索引等的DDL（数据定义语言）
作者：Auto-Generated
日期：2023-11-14
"""

import os
import sys
import yaml
import logging
from datetime import datetime
from typing import List, Dict, Any
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('../logs/export_ddl.log', 'w', 'utf-8')
    ]
)
logger = logging.getLogger(__name__)

class DDLExporter:
    def __init__(self, config_path: str = None):
        """初始化DDL导出器"""
        self.config_path = config_path or os.environ.get("DB_CONFIG", "config/db_config.yaml")
        self.db_config = self.load_db_config()
        self.conn = None
        self.output_file = None
        
    def load_db_config(self) -> Dict[str, Any]:
        """加载数据库配置"""
        with open(self.config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        
        pg = dict(raw.get("postgres", {}))
        # 兼容 dbname / database 两种命名
        dbname = pg.get("dbname") or pg.get("database")
        pg["dbname"] = dbname
        
        # 环境变量覆盖
        if os.environ.get("PGHOST"):
            pg["host"] = os.environ["PGHOST"]
        if os.environ.get("PGPORT"):
            try:
                pg["port"] = int(os.environ["PGPORT"])
            except ValueError:
                pg["port"] = os.environ["PGPORT"]
        if os.environ.get("PGDATABASE"):
            pg["dbname"] = os.environ["PGDATABASE"]
        if os.environ.get("PGUSER"):
            pg["user"] = os.environ["PGUSER"]
        if os.environ.get("PGPASSWORD"):
            pg["password"] = os.environ["PGPASSWORD"]
        
        # 默认端口
        pg.setdefault("port", 5432)
        return pg
    
    def connect(self):
        """连接到PostgreSQL数据库"""
        try:
            logger.info(f"正在连接到数据库: {self.db_config.get('dbname')}@({self.db_config.get('host')}:{self.db_config.get('port')})")
            self.conn = psycopg2.connect(
                host=self.db_config["host"],
                port=self.db_config["port"],
                dbname=self.db_config["dbname"],
                user=self.db_config["user"],
                password=self.db_config["password"],
            )
            self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            logger.info(f"成功连接到数据库: {self.db_config['dbname']}@({self.db_config['host']}:{self.db_config['port']})")
        except Exception as e:
            logger.error(f"连接数据库失败: {str(e)}")
            sys.exit(1)
    
    def disconnect(self):
        """断开数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("已断开数据库连接")
    
    def export_ddl(self, output_file: str = None):
        """导出所有DDL到文件"""
        # 默认输出文件名
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"db_ddl_export_{timestamp}.sql"
        
        self.output_file = output_file
        logger.info(f"准备导出DDL到文件: {output_file}")
        
        # 连接数据库
        self.connect()
        
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                logger.info("正在写入文件头信息")
                # 添加文件头信息
                f.write(f"-- 数据库DDL导出\n")
                f.write(f"-- 数据库: {self.db_config['dbname']}\n")
                f.write(f"-- 主机: {self.db_config['host']}:{self.db_config['port']}\n")
                f.write(f"-- 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("-- 导出内容: 表、视图、索引、序列等\n")
                f.write("\nSET statement_timeout = 0;\n")
                f.write("SET lock_timeout = 0;\n")
                f.write("SET idle_in_transaction_session_timeout = 0;\n")
                f.write("SET client_encoding = 'UTF8';\n")
                f.write("SET standard_conforming_strings = on;\n")
                f.write("SELECT pg_catalog.set_config('search_path', '', false);\n")
                f.write("SET check_function_bodies = false;\n")
                f.write("SET xmloption = content;\n")
                f.write("SET client_min_messages = warning;\n")
                f.write("SET row_security = off;\n\n")
                
                # 导出扩展
                logger.info("正在导出数据库扩展")
                f.write("-- === 扩展 ===\n")
                self._export_extensions(f)
                f.write("\n")
                
                # 导出序列
                logger.info("正在导出数据库序列")
                f.write("-- === 序列 ===\n")
                self._export_sequences(f)
                f.write("\n")
                
                # 导出表结构
                logger.info("正在导出表结构")
                f.write("-- === 表结构 ===\n")
                self._export_tables(f)
                f.write("\n")
                
                # 导出视图
                logger.info("正在导出视图")
                f.write("-- === 视图 ===\n")
                self._export_views(f)
                f.write("\n")
                
                # 导出索引
                logger.info("正在导出索引")
                f.write("-- === 索引 ===\n")
                self._export_indexes(f)
                f.write("\n")
                
                # 导出触发器
                logger.info("正在导出触发器")
                f.write("-- === 触发器 ===\n")
                self._export_triggers(f)
                f.write("\n")
                
                # 导出函数
                logger.info("正在导出函数")
                f.write("-- === 函数 ===\n")
                self._export_functions(f)
                f.write("\n")
                
                # 导出约束（除主键和唯一约束外的其他约束）
                logger.info("正在导出其他约束")
                f.write("-- === 其他约束 ===\n")
                self._export_other_constraints(f)
                f.write("\n")
                
                # 添加结尾信息
                f.write("-- DDL导出完成\n")
                
            logger.info(f"DDL导出成功，保存至: {output_file}")
        except Exception as e:
            logger.error(f"导出DDL失败: {str(e)}")
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                    logger.info(f"已删除部分导出的文件: {output_file}")
                except:
                    pass
            sys.exit(1)
        finally:
            self.disconnect()
    
    def _export_extensions(self, f):
        """导出数据库扩展"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        quote_ident(e.extname) AS extension_name,
                        e.extversion AS version
                    FROM
                        pg_catalog.pg_extension e
                    WHERE
                        e.extname NOT IN ('plpgsql', 'pg_stat_statements') -- 排除内置扩展
                    ORDER BY
                        e.extname;
                """)
                extensions = cur.fetchall()
                
                if not extensions:
                    logger.info("未找到需要导出的数据库扩展")
                    f.write("-- 未找到需要导出的数据库扩展\n\n")
                    return
                
                logger.info(f"找到 {len(extensions)} 个数据库扩展")
                for ext_name, version in extensions:
                    logger.debug(f"正在导出扩展: {ext_name} (版本: {version})")
                    f.write(f"-- 扩展: {ext_name} (版本: {version})\n")
                    f.write(f"CREATE EXTENSION IF NOT EXISTS {ext_name} WITH VERSION '{version}';\n\n")
        except Exception as e:
            logger.error(f"导出数据库扩展时出错: {str(e)}")
            # 继续执行其他导出任务，不中断整个流程
    
    def _export_sequences(self, f):
        """导出序列"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        c.relname AS sequence_name,
                        pg_catalog.pg_get_serial_sequence(c.relname, a.attname) AS owning_column,
                        d.adsrc AS default_value
                    FROM
                        pg_catalog.pg_class c
                    JOIN
                        pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    LEFT JOIN
                        pg_catalog.pg_attribute a ON a.attrelid = c.oid
                    LEFT JOIN
                        pg_catalog.pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
                    WHERE
                        c.relkind = 'S'
                        AND n.nspname = 'public'
                    ORDER BY
                        c.relname;
                """)
                sequences = cur.fetchall()
                
                if not sequences:
                    logger.info("未找到需要导出的数据库序列")
                    f.write("-- 未找到需要导出的数据库序列\n\n")
                    return
                
                logger.info(f"找到 {len(sequences)} 个数据库序列")
                for seq_name, owning_col, default_val in sequences:
                    try:
                        with self.conn.cursor() as sub_cur:
                            # 检查是否为serial类型自动创建的序列
                            sub_cur.execute("SELECT pg_get_serial_sequence(relname, attname) FROM pg_class JOIN pg_attribute ON attrelid = oid WHERE atttypid = 'pg_catalog.serial'::regtype AND attrelid = (SELECT oid FROM pg_class WHERE relname = %s)", (seq_name.replace('_seq', ''),))
                            result = sub_cur.fetchone()
                            if result and result[0] == f"public.{seq_name}":
                                logger.debug(f"跳过serial类型自动创建的序列: {seq_name}")
                                continue
                            
                            try:
                                # 尝试使用PostgreSQL 14+的函数获取创建语句
                                sub_cur.execute(f"SELECT pg_get_create_table_statement('{seq_name}'::regclass)")
                                create_stmt = sub_cur.fetchone()[0]
                                if create_stmt:
                                    logger.debug(f"正在导出序列: {seq_name}")
                                    f.write(f"-- 序列: {seq_name}\n")
                                    f.write(f"{create_stmt};")
                                    f.write("\n\n")
                            except Exception as inner_e:
                                # 如果PostgreSQL版本较低，使用传统方法
                                logger.debug(f"使用传统方法导出序列: {seq_name}, 原因: {str(inner_e)}")
                                # 对于较旧的PostgreSQL版本，我们需要构建CREATE SEQUENCE语句
                                sub_cur.execute("""
                                    SELECT
                                        start_value, min_value, max_value, increment_by, cycle
                                    FROM
                                        pg_catalog.pg_sequences
                                    WHERE
                                        schemaname = 'public' AND sequencename = %s;
                                """, (seq_name,))
                                seq_info = sub_cur.fetchone()
                                if seq_info:
                                    start_val, min_val, max_val, increment, cycle = seq_info
                                    create_stmt = f"CREATE SEQUENCE public.{seq_name} START WITH {start_val} INCREMENT BY {increment} MINVALUE {min_val} MAXVALUE {max_val}"
                                    if cycle:
                                        create_stmt += " CYCLE"
                                    else:
                                        create_stmt += " NO CYCLE"
                                    f.write(f"-- 序列: {seq_name}\n")
                                    f.write(f"{create_stmt};")
                                    f.write("\n\n")
                    except Exception as inner_e:
                        logger.error(f"导出序列 {seq_name} 时出错: {str(inner_e)}")
                        # 继续处理下一个序列
        except Exception as e:
            logger.error(f"导出数据库序列时出错: {str(e)}")
            # 继续执行其他导出任务，不中断整个流程
    
    def _export_tables(self, f):
        """导出表结构"""
        try:
            with self.conn.cursor() as cur:
                # 获取所有表名
                cur.execute("""
                    SELECT
                        c.relname AS table_name
                    FROM
                        pg_catalog.pg_class c
                    JOIN
                        pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE
                        c.relkind = 'r' -- 只选择表
                        AND n.nspname = 'public' -- 只选择public模式
                        AND c.relname NOT IN ('pg_stat_statements') -- 排除系统表
                    ORDER BY
                        c.relname;
                """)
                tables = cur.fetchall()
                
                if not tables:
                    logger.info("未找到需要导出的数据库表")
                    f.write("-- 未找到需要导出的数据库表\n\n")
                    return
                
                logger.info(f"找到 {len(tables)} 个数据库表")
                
                # 尝试不同的方法获取表的创建语句
                methods_tried = 0
                
                # 方法1: 使用pg_get_create_table_statement（PostgreSQL 14+）
                try:
                    method1_success = False
                    for table_name, in tables:
                        try:
                            cur.execute(f"SELECT pg_get_create_table_statement('public.{table_name}'::regclass)")
                            create_stmt = cur.fetchone()[0]
                            if create_stmt:
                                logger.debug(f"正在导出表: {table_name} (使用PostgreSQL 14+方法)")
                                f.write(f"-- 表: {table_name}\n")
                                f.write(f"{create_stmt};")
                                f.write("\n\n")
                                method1_success = True
                        except Exception as inner_e:
                            logger.warning(f"使用PostgreSQL 14+方法导出表 {table_name} 失败: {str(inner_e)}")
                            # 继续处理下一个表
                    methods_tried = 1
                except Exception as e:
                    logger.warning(f"使用PostgreSQL 14+方法导出表失败: {str(e)}")
                    methods_tried = 1  # 标记为已尝试过，但仍然允许尝试方法2
                
                # 方法2: 使用information_schema.columns和pg_constraint
                if methods_tried == 1 and not method1_success:
                    logger.info("使用传统方法导出表结构")
                    for table_name, in tables:
                        try:
                            # 获取表注释
                            cur.execute("""
                                SELECT
                                    obj_description(c.oid)
                                FROM
                                    pg_catalog.pg_class c
                                WHERE
                                    c.relname = %s
                                    AND c.relkind = 'r';
                            """, (table_name,))
                            comment_row = cur.fetchone()
                            comment = comment_row[0] if comment_row else None
                            
                            if comment:
                                f.write(f"-- 表: {table_name} - {comment}\n")
                            else:
                                f.write(f"-- 表: {table_name}\n")
                            
                            # 获取列信息
                            cur.execute("""
                                SELECT
                                    a.attname AS column_name,
                                    t.typname AS data_type,
                                    a.attnotnull AS is_not_null,
                                    pg_get_expr(d.adbin, d.adrelid) AS default_value,
                                    col_description(a.attrelid, a.attnum) AS column_comment
                                FROM
                                    pg_catalog.pg_attribute a
                                JOIN
                                    pg_catalog.pg_type t ON a.atttypid = t.oid
                                JOIN
                                    pg_catalog.pg_class c ON a.attrelid = c.oid
                                LEFT JOIN
                                    pg_catalog.pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
                                WHERE
                                    c.relname = %s
                                    AND a.attnum > 0 -- 排除系统列
                                    AND NOT a.attisdropped -- 排除已删除的列
                                ORDER BY
                                    a.attnum;
                            """, (table_name,))
                            columns = cur.fetchall()
                            
                            if not columns:
                                logger.warning(f"表 {table_name} 没有找到列信息")
                                f.write(f"-- 警告: 表 {table_name} 没有找到列信息\n\n")
                                continue
                            
                            logger.debug(f"正在导出表: {table_name} (使用传统方法)")
                            # 构建CREATE TABLE语句
                            f.write(f"CREATE TABLE IF NOT EXISTS public.{table_name} (\n")
                            col_defs = []
                            
                            for col_name, data_type, is_not_null, default_val, col_comment in columns:
                                col_def = f"    {col_name} {data_type}"
                                if is_not_null:
                                    col_def += " NOT NULL"
                                if default_val:
                                    col_def += f" DEFAULT {default_val}"
                                col_defs.append(col_def)
                            
                            # 获取主键约束
                            cur.execute("""
                                SELECT
                                    conname,
                                    pg_get_constraintdef(oid)
                                FROM
                                    pg_catalog.pg_constraint
                                WHERE
                                    conrelid = (SELECT oid FROM pg_catalog.pg_class WHERE relname = %s)
                                    AND contype = 'p';
                            """, (table_name,))
                            pkey = cur.fetchone()
                            if pkey:
                                col_defs.append(f"    {pkey[1]}")
                            
                            # 获取唯一约束
                            cur.execute("""
                                SELECT
                                    conname,
                                    pg_get_constraintdef(oid)
                                FROM
                                    pg_catalog.pg_constraint
                                WHERE
                                    conrelid = (SELECT oid FROM pg_catalog.pg_class WHERE relname = %s)
                                    AND contype = 'u';
                            """, (table_name,))
                            unique_constraints = cur.fetchall()
                            for conname, condef in unique_constraints:
                                col_defs.append(f"    {condef}")
                            
                            f.write(",\n".join(col_defs))
                            f.write("\n);\n")
                            
                            # 添加列注释
                            for col_name, _, _, _, col_comment in columns:
                                if col_comment:
                                    # 在f-string外部处理引号替换
                                    escaped_comment = col_comment.replace("'", "''")
                                    f.write(f"COMMENT ON COLUMN public.{table_name}.{col_name} IS '{escaped_comment}';\n")
                            
                            # 添加表注释
                            if comment:
                                # 在f-string外部处理引号替换
                                escaped_table_comment = comment.replace("'", "''")
                                f.write(f"COMMENT ON TABLE public.{table_name} IS '{escaped_table_comment}';\n")
                            
                            f.write("\n")
                        except Exception as inner_e:
                            logger.error(f"导出表 {table_name} 时出错: {str(inner_e)}")
                            # 继续处理下一个表
        except Exception as e:
            logger.error(f"导出数据库表结构时出错: {str(e)}")
            # 继续执行其他导出任务，不中断整个流程
    
    def _export_views(self, f):
        """导出视图"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        c.relname AS view_name,
                        pg_get_viewdef(c.oid, TRUE) AS view_definition
                    FROM
                        pg_catalog.pg_class c
                    JOIN
                        pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE
                        c.relkind = 'v' -- 只选择视图
                        AND n.nspname = 'public'
                    ORDER BY
                        c.relname;
                """)
                views = cur.fetchall()
                
                if not views:
                    logger.info("未找到需要导出的数据库视图")
                    f.write("-- 未找到需要导出的数据库视图\n\n")
                    return
                
                logger.info(f"找到 {len(views)} 个数据库视图")
                for view_name, view_def in views:
                    try:
                        logger.debug(f"正在导出视图: {view_name}")
                        f.write(f"-- 视图: {view_name}\n")
                        f.write(f"CREATE OR REPLACE VIEW public.{view_name} AS\n")
                        f.write(f"{view_def};\n\n")
                    except Exception as inner_e:
                        logger.error(f"导出视图 {view_name} 时出错: {str(inner_e)}")
                        # 继续处理下一个视图
        except Exception as e:
            logger.error(f"导出数据库视图时出错: {str(e)}")
            # 继续执行其他导出任务，不中断整个流程
    
    def _export_indexes(self, f):
        """导出索引"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        i.relname AS index_name,
                        t.relname AS table_name,
                        pg_get_indexdef(i.oid) AS index_def
                    FROM
                        pg_catalog.pg_class i
                    JOIN
                        pg_catalog.pg_index ix ON ix.indexrelid = i.oid
                    JOIN
                        pg_catalog.pg_class t ON ix.indrelid = t.oid
                    JOIN
                        pg_catalog.pg_namespace n ON n.oid = i.relnamespace
                    WHERE
                        i.relkind = 'i' -- 只选择索引
                        AND n.nspname = 'public'
                        AND NOT ix.indisprimary -- 排除主键索引
                        AND NOT ix.indisunique -- 排除唯一索引
                    ORDER BY
                        t.relname, i.relname;
                """)
                indexes = cur.fetchall()
                
                if not indexes:
                    logger.info("未找到需要导出的数据库索引")
                    f.write("-- 未找到需要导出的数据库索引\n\n")
                    return
                
                logger.info(f"找到 {len(indexes)} 个数据库索引")
                for index_name, table_name, index_def in indexes:
                    try:
                        logger.debug(f"正在导出索引: {index_name} (表: {table_name})")
                        f.write(f"-- 索引: {index_name} (表: {table_name})\n")
                        # 确保语句以分号结尾
                        if not index_def.strip().endswith(';'):
                            index_def += ';'
                        f.write(f"{index_def}\n\n")
                    except Exception as inner_e:
                        logger.error(f"导出索引 {index_name} 时出错: {str(inner_e)}")
                        # 继续处理下一个索引
        except Exception as e:
            logger.error(f"导出数据库索引时出错: {str(e)}")
            # 继续执行其他导出任务，不中断整个流程
    
    def _export_triggers(self, f):
        """导出触发器"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        t.tgname AS trigger_name,
                        c.relname AS table_name,
                        pg_get_triggerdef(t.oid) AS trigger_def
                    FROM
                        pg_catalog.pg_trigger t
                    JOIN
                        pg_catalog.pg_class c ON t.tgrelid = c.oid
                    JOIN
                        pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE
                        NOT t.tgisinternal -- 排除内部触发器
                        AND n.nspname = 'public'
                    ORDER BY
                        c.relname, t.tgname;
                """)
                triggers = cur.fetchall()
                
                if not triggers:
                    logger.info("未找到需要导出的数据库触发器")
                    f.write("-- 未找到需要导出的数据库触发器\n\n")
                    return
                
                logger.info(f"找到 {len(triggers)} 个数据库触发器")
                for trigger_name, table_name, trigger_def in triggers:
                    try:
                        logger.debug(f"正在导出触发器: {trigger_name} (表: {table_name})")
                        f.write(f"-- 触发器: {trigger_name} (表: {table_name})\n")
                        # 确保语句以分号结尾
                        if not trigger_def.strip().endswith(';'):
                            trigger_def += ';'
                        f.write(f"{trigger_def}\n\n")
                    except Exception as inner_e:
                        logger.error(f"导出触发器 {trigger_name} 时出错: {str(inner_e)}")
                        # 继续处理下一个触发器
        except Exception as e:
            logger.error(f"导出数据库触发器时出错: {str(e)}")
            # 继续执行其他导出任务，不中断整个流程
    
    def _export_functions(self, f):
        """导出函数"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        p.proname AS function_name,
                        pg_get_functiondef(p.oid) AS function_def
                    FROM
                        pg_catalog.pg_proc p
                    JOIN
                        pg_catalog.pg_namespace n ON n.oid = p.pronamespace
                    WHERE
                        n.nspname = 'public'
                        AND NOT p.proisagg -- 排除聚合函数
                    ORDER BY
                        p.proname;
                """)
                functions = cur.fetchall()
                
                if not functions:
                    logger.info("未找到需要导出的数据库函数")
                    f.write("-- 未找到需要导出的数据库函数\n\n")
                    return
                
                logger.info(f"找到 {len(functions)} 个数据库函数")
                for func_name, func_def in functions:
                    try:
                        logger.debug(f"正在导出函数: {func_name}")
                        f.write(f"-- 函数: {func_name}\n")
                        # 确保语句以分号结尾
                        if not func_def.strip().endswith(';'):
                            func_def += ';'
                        f.write(f"{func_def}\n\n")
                    except Exception as inner_e:
                        logger.error(f"导出函数 {func_name} 时出错: {str(inner_e)}")
                        # 继续处理下一个函数
        except Exception as e:
            logger.error(f"导出数据库函数时出错: {str(e)}")
            # 继续执行其他导出任务，不中断整个流程
    
    def _export_other_constraints(self, f):
        """导出其他约束（外键约束等）"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        c.conname AS constraint_name,
                        t.relname AS table_name,
                        pg_get_constraintdef(c.oid) AS constraint_def
                    FROM
                        pg_catalog.pg_constraint c
                    JOIN
                        pg_catalog.pg_class t ON c.conrelid = t.oid
                    JOIN
                        pg_catalog.pg_namespace n ON n.oid = t.relnamespace
                    WHERE
                        n.nspname = 'public'
                        AND c.contype NOT IN ('p', 'u') -- 排除主键和唯一约束
                    ORDER BY
                        t.relname, c.conname;
                """)
                constraints = cur.fetchall()
                
                if not constraints:
                    logger.info("未找到需要导出的其他数据库约束")
                    f.write("-- 未找到需要导出的其他数据库约束\n\n")
                    return
                
                logger.info(f"找到 {len(constraints)} 个其他数据库约束")
                for constraint_name, table_name, constraint_def in constraints:
                    try:
                        logger.debug(f"正在导出约束: {constraint_name} (表: {table_name})")
                        f.write(f"-- 约束: {constraint_name} (表: {table_name})\n")
                        f.write(f"ALTER TABLE public.{table_name} ADD {constraint_def};\n\n")
                    except Exception as inner_e:
                        logger.error(f"导出约束 {constraint_name} 时出错: {str(inner_e)}")
                        # 继续处理下一个约束
        except Exception as e:
            logger.error(f"导出其他数据库约束时出错: {str(e)}")
            # 继续执行其他导出任务，不中断整个流程

if __name__ == "__main__":
    # 获取命令行参数
    output_file = None
    if len(sys.argv) > 1:
        output_file = sys.argv[1]
    
    # 初始化并导出DDL
    exporter = DDLExporter()
    try:
        exporter.connect()
        exporter.export_ddl(output_file)
    finally:
        exporter.disconnect()