#!/usr/bin/env python3
# 完全独立的日志测试脚本，不依赖项目其他模块

import os
import logging
import json

def setup_logger():
    """设置独立的日志记录器"""
    # 确定日志目录和文件路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(current_dir, "logs")
    
    # 确保logs目录存在
    os.makedirs(logs_dir, exist_ok=True)
    
    log_file = os.path.join(logs_dir, "backtest_trades_debug.log")
    
    # 创建日志记录器
    logger = logging.getLogger("independent_log_test")
    logger.setLevel(logging.DEBUG)
    
    # 清除可能存在的处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    
    # 设置日志格式
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler.setFormatter(formatter)
    
    # 添加处理器到记录器
    logger.addHandler(file_handler)
    
    # 确保日志记录器不会传播到根记录器
    logger.propagate = False
    
    print(f"独立日志记录器已配置在: {log_file}")
    return logger, log_file

def main():
    """独立测试日志功能"""
    try:
        print("开始独立测试日志功能...")
        
        # 设置独立的日志记录器
        logger, log_file = setup_logger()
        
        # 准备测试数据
        strategy = "test_strategy"
        code = "000001.SZ"
        merged_params = {
            "start_date": "2023-01-01",
            "end_date": "2023-01-02",
            "grid_number": 5,
            "funds": 10000,
            "test_parameter": "independent_log_test"
        }
        
        print(f"记录测试日志 - 策略: {strategy}, 标的: {code}")
        print(f"参数: {merged_params}")
        
        # 记录日志
        logger.info(f"回测参数已合并 - 策略: {strategy}, 标的: {code}")
        logger.info(f"合并后的完整参数: {json.dumps(merged_params, ensure_ascii=False)}")
        logger.debug(f"这是一条调试日志 - {strategy}:{code}")
        
        print("日志记录完成")
        
        # 检查日志文件
        print(f"\n日志文件路径: {log_file}")
        
        if os.path.exists(log_file):
            print(f"日志文件大小: {os.path.getsize(log_file)} 字节")
            print("\n日志文件内容预览:")
            with open(log_file, 'r') as f:
                lines = f.readlines()
                # 打印最后10行日志
                for line in lines[-10:]:
                    print(line.strip())
        else:
            print("警告: 日志文件不存在!")
            
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()