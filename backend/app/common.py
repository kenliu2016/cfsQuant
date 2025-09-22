import logging
import os
from pathlib import Path


def setup_logger_with_file_handler(
    logger_name: str,
    log_filename: str,
    log_level: int = logging.DEBUG,
    log_dir: str = "logs",
    mode: str = 'w',
    propagate: bool = False
) -> logging.Logger:
    """
    配置带有文件处理器的日志记录器
    
    参数:
        logger_name: 日志记录器名称
        log_filename: 日志文件名
        log_level: 日志级别，默认为DEBUG
        log_dir: 日志目录，默认为项目根目录下的'logs'
        mode: 文件打开模式，'w'表示覆盖，'a'表示追加，默认为'w'
        propagate: 是否向上级记录器传递消息，默认为False
    
    返回:
        配置好的日志记录器实例
    """
    # 直接使用绝对路径设置项目根目录，确保日志文件位置正确
    project_root = '/Users/aaronkliu/Documents/project/cfsQuant'
    
    # 创建日志目录（如果不存在）
    logs_directory = os.path.join(project_root, log_dir)
    os.makedirs(logs_directory, exist_ok=True)
    
    # 构建完整的日志文件路径
    log_file_path = os.path.join(logs_directory, log_filename)
    
    # 获取或创建日志记录器
    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)
    
    # 移除已有的处理器（避免重复添加）
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_file_path, mode=mode)
    file_handler.setLevel(log_level)
    
    # 设置日志格式
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler.setFormatter(formatter)
    
    # 添加处理器到日志记录器
    logger.addHandler(file_handler)
    
    # 设置是否向上级记录器传递消息
    logger.propagate = propagate
    
    return logger