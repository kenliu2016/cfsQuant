#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Celery配置文件

此文件包含Celery的基本配置，用于管理后台任务队列
"""
import os
from celery import Celery
from celery.schedules import crontab
import yaml

# 加载数据库配置
def load_db_config(config_path: str = "config/db_config.yaml") -> dict:
    """加载数据库配置信息"""
    # 确保配置文件路径是绝对路径
    if not os.path.isabs(config_path):
        # 获取项目根目录
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # 构建相对于项目根目录的绝对路径
        config_path = os.path.join(current_dir, config_path)
    
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    
    return raw

# 加载Redis配置
_db_config = load_db_config()
REDIS_HOST = os.environ.get('REDIS_HOST', _db_config.get('redis', {}).get('host', 'localhost'))
REDIS_PORT = int(os.environ.get('REDIS_PORT', _db_config.get('redis', {}).get('port', 6379)))
REDIS_DB = int(os.environ.get('REDIS_DB', _db_config.get('redis', {}).get('db', 0)))

# 创建Celery应用实例
celery_app = Celery(
    'cfsQuant',
    broker=f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}',
    backend=f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}',
    include=['app.services.tuning_service']
)

# 配置Celery应用
celery_app.conf.update(
    # 基本配置
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='Asia/Shanghai',
    enable_utc=True,
    
    # 任务队列配置
    task_default_queue='default',
    task_queues={
        'default': {
            'exchange': 'default',
            'exchange_type': 'direct',
            'routing_key': 'default',
        },
        'tuning': {
            'exchange': 'tuning',
            'exchange_type': 'direct',
            'routing_key': 'tuning',
        },
        'backtest': {
            'exchange': 'backtest',
            'exchange_type': 'direct',
            'routing_key': 'backtest',
        },
    },
    task_routes={
        'app.services.tuning_service.*': {'queue': 'tuning'},
    },
    
    # 任务执行配置
    worker_prefetch_multiplier=1,  # 每个worker预取的任务数
    worker_max_tasks_per_child=100,  # 每个worker进程执行的最大任务数，防止内存泄漏
    worker_concurrency=4,  # worker并发数，根据CPU核心数调整
    
    # 任务超时和重试配置
    task_soft_time_limit=3600,  # 任务软超时时间（秒）
    task_time_limit=7200,  # 任务硬超时时间（秒）
    task_reject_on_worker_lost=True,  # 当worker丢失时拒绝任务
    
    # 结果存储配置
    result_expires=86400,  # 结果存储时间（秒），默认为1天
    result_persistent=True,  # 结果持久化
    
    # 并发配置
    broker_pool_limit=10,  # 连接池大小
    broker_connection_timeout=30,  # 连接超时时间
    broker_connection_retry=True,  # 连接重试
    broker_connection_retry_on_startup=True,  # 启动时重试连接
    
    # 事件配置
    worker_send_task_events=True,  # 发送任务事件
    task_send_sent_event=True,  # 发送任务发送事件
)

# 配置定时任务（如果需要）
celery_app.conf.beat_schedule = {
    # 'example-task': {
    #     'task': 'app.services.example_task',
    #     'schedule': crontab(minute=0, hour=0),  # 每天凌晨执行
    #     'args': (),
    # },
}

# 启动Celery worker的命令：
# celery -A app.celery_config worker --loglevel=info --queue=tuning
# 
# 启动Celery beat的命令（如果需要定时任务）：
# celery -A app.celery_config beat --loglevel=info