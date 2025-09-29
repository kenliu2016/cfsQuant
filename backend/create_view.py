#!/usr/bin/env python
"""创建市场记录统计视图的脚本"""

import os
import sys
from sqlalchemy import text

# 添加项目根目录到Python路径，确保能正确导入app模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import execute


def create_market_records_count_view():
    """创建market_records_count视图"""
    try:
        # 获取SQL文件的绝对路径
        sql_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'db',
            'market_records_count_view.sql'
        )
        
        # 检查文件是否存在
        if not os.path.exists(sql_file_path):
            print(f"错误: 找不到SQL文件: {sql_file_path}")
            sys.exit(1)
        
        # 读取SQL文件内容
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # 执行SQL，使用text()包装SQL语句
        print(f"正在创建视图: market_records_count")
        execute(text(sql_content))
        print("视图创建成功!")
        
    except Exception as e:
        print(f"创建视图失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    create_market_records_count_view()