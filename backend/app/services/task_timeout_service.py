import time
import logging
import threading
import time
from datetime import datetime, timedelta
from ..db import fetch_df, execute
from ..celery_config import celery_app
from .tuning_service import run_parameter_tuning

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 默认超时配置（单位：小时）
DEFAULT_TUNING_TASK_TIMEOUT = 24  # 调优任务默认24小时超时

# 轮询间隔（单位：分钟）
POLLING_INTERVAL = 30

class TaskTimeoutService:
    """
    任务超时处理服务
    负责检测和处理长时间运行的任务
    """
    def __init__(self):
        self.running = False
        self.thread = None
        self.interval = 1800  # 默认30分钟检查一次（秒）
        self.timeout_hours = DEFAULT_TUNING_TASK_TIMEOUT  # 默认超时时间
        self.check_table_structure = True  # 是否自动检查表结构
        
    def start(self, interval=1800, timeout_hours=DEFAULT_TUNING_TASK_TIMEOUT, check_table_structure=True):
        """启动任务超时检测服务
        
        Args:
            interval: 检查间隔（秒），默认为1800秒（30分钟）
            timeout_hours: 任务超时时间（小时），默认为DEFAULT_TUNING_TASK_TIMEOUT
            check_table_structure: 是否自动检查表结构，默认为True
        """
        if self.running:
            logger.warning("任务超时检测服务已经在运行中")
            return
            
        # 更新配置
        self.interval = interval
        self.timeout_hours = timeout_hours
        self.check_table_structure = check_table_structure
            
        self.running = True
        self.thread = threading.Thread(target=self._check_loop, daemon=True)
        self.thread.start()
        logger.info(f"任务超时检测服务已启动，检查间隔：{interval}秒，超时时间：{timeout_hours}小时")
        
    def stop(self):
        """停止任务超时检测服务"""
        if not self.running:
            logger.warning("任务超时检测服务未运行")
            return
            
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)  # 等待线程结束，最多5秒
        logger.info("任务超时检测服务已停止")
        
    def _check_loop(self):
        """持续检查任务超时的主循环"""
        while self.running:
            try:
                self.check_tuning_task_timeouts()
            except Exception as e:
                logger.error(f"检查任务超时过程中发生错误: {str(e)}")
            
            # 等待指定的时间间隔
            for _ in range(self.interval):  # 使用配置的间隔时间
                if not self.running:
                    break
                time.sleep(1)
    
    def check_tuning_task_timeouts(self):
        """检查调优任务是否超时"""
        logger.info("开始检查调优任务超时情况")
        
        try:
            # 检查是否存在start_time和timeout字段，如果不存在则添加
            if self.check_table_structure:
                self._ensure_timeout_columns()
            
            # 获取所有运行中超过超时时间的任务
            current_time = datetime.now()
            timeout_threshold = current_time - timedelta(hours=self.timeout_hours)
            
            # 首先确保所有running状态的任务都有start_time
            self._update_missing_start_times()
            
            # 查询超时任务
            query = """
            SELECT task_id, strategy, created_at, start_time 
            FROM tuning_tasks 
            WHERE status = 'running' AND start_time < :timeout_threshold
            """
            
            result = fetch_df(query, timeout_threshold=timeout_threshold.strftime('%Y-%m-%d %H:%M:%S'))
            
            if not result.empty:
                logger.warning(f"发现{len(result)}个超时的调优任务")
                
                for _, row in result.iterrows():
                    task_id = row['task_id']
                    strategy = row['strategy']
                    
                    logger.warning(f"任务超时: task_id={task_id}, strategy={strategy}, 开始时间={row['start_time']}")
                    
                    # 处理超时任务
                    self._handle_timeout_task(task_id)
            else:
                logger.info("没有发现超时的调优任务")
                
        except Exception as e:
            logger.error(f"检查调优任务超时失败: {str(e)}")
            
    def _ensure_timeout_columns(self):
        """确保tuning_tasks表中包含处理超时所需的列"""
        try:
            # 检查start_time列是否存在
            check_query = "SELECT column_name FROM information_schema.columns WHERE table_name = 'tuning_tasks' AND column_name = 'start_time'"
            start_time_result = fetch_df(check_query)
            
            # 如果start_time列不存在，添加它
            if start_time_result.empty:
                logger.info("向tuning_tasks表添加start_time列")
                execute("ALTER TABLE tuning_tasks ADD COLUMN start_time TIMESTAMP")
            
            # 检查timeout列是否存在且类型正确
            check_query_timeout = "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'tuning_tasks' AND column_name = 'timeout'"
            timeout_result = fetch_df(check_query_timeout)
            
            # 如果timeout列不存在或类型不是timestamp，添加或修改它
            if timeout_result.empty:
                logger.info("向tuning_tasks表添加timeout列（记录超时时间）")
                execute("ALTER TABLE tuning_tasks ADD COLUMN timeout TIMESTAMP")
            elif timeout_result.iloc[0]['data_type'] != 'timestamp':
                logger.warning("timeout列类型不正确，需要手动修改为timestamp类型")
                logger.warning("请运行SQL: ALTER TABLE tuning_tasks ALTER COLUMN timeout TYPE TIMESTAMP USING NULL")
            
            # 检查error列是否存在（用于存储错误信息）
            check_query_error = "SELECT column_name FROM information_schema.columns WHERE table_name = 'tuning_tasks' AND column_name = 'error'"
            error_result = fetch_df(check_query_error)
            
            # 如果error列不存在，添加它
            if error_result.empty:
                logger.info("向tuning_tasks表添加error列（记录错误信息）")
                execute("ALTER TABLE tuning_tasks ADD COLUMN error TEXT")
                
        except Exception as e:
            logger.error(f"确保表结构失败: {str(e)}")
            # 不抛出异常，继续执行
            
    def _update_missing_start_times(self):
        """更新缺少start_time的运行中任务"""
        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            update_query = """
            UPDATE tuning_tasks 
            SET start_time = COALESCE(start_time, created_at, :current_time) 
            WHERE status = 'running' AND start_time IS NULL
            """
            execute(update_query, current_time=current_time)
        except Exception as e:
            logger.error(f"更新任务开始时间失败: {str(e)}")
            
    def _handle_timeout_task(self, task_id: str):
        """处理超时任务
        
        1. 尝试取消Celery任务
        2. 更新数据库中的任务状态为error
        """
        try:
            # 尝试取消Celery任务
            try:
                task = run_parameter_tuning.AsyncResult(task_id)
                if task.state == 'RUNNING':
                    # Celery不支持直接取消正在运行的任务
                    # 这里我们记录日志，然后在数据库中更新状态
                    logger.warning(f"无法直接取消正在运行的Celery任务: {task_id}")
            except Exception as e:
                logger.error(f"取消Celery任务失败: {str(e)}")
                
            # 更新数据库中的任务状态
            error_msg = f"任务执行超时（超过{self.timeout_hours}小时）"
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 尝试使用不同的方式更新任务状态
            try:
                # 方法1: 更新status、timeout和error字段
                execute(
                    "UPDATE tuning_tasks SET status = :status, timeout = :timeout, error = :error WHERE task_id = :task_id",
                    task_id=task_id,
                    status='error',
                    timeout=current_time,
                    error=error_msg
                )
                logger.info(f"已将超时任务{task_id}标记为error，并存储错误信息")
            except Exception as e1:
                logger.warning(f"更新任务状态失败（方法1）: {str(e1)}")
                try:
                    # 方法2: 更新status和timeout字段（不包含error字段）
                    execute(
                        "UPDATE tuning_tasks SET status = :status, timeout = :timeout WHERE task_id = :task_id",
                        task_id=task_id,
                        status='error',
                        timeout=current_time
                    )
                    logger.info(f"已将超时任务{task_id}标记为error（仅更新status和timeout字段）")
                except Exception as e2:
                    logger.warning(f"更新任务状态失败（方法2）: {str(e2)}")
                    try:
                        # 方法3: 只更新status字段
                        execute(
                            "UPDATE tuning_tasks SET status = :status WHERE task_id = :task_id",
                            task_id=task_id,
                            status='error'
                        )
                        logger.info(f"已将超时任务{task_id}标记为error（仅更新status字段）")
                    except Exception as e3:
                        logger.error(f"更新任务状态失败（方法3）: {str(e3)}")
            
        except Exception as e:
            logger.error(f"处理超时任务{task_id}失败: {str(e)}")

# 创建单例实例
task_timeout_service = TaskTimeoutService()

# 启动服务（如果直接运行此脚本）
if __name__ == "__main__":
    try:
        task_timeout_service.start()
        logger.info("任务超时检测服务已在独立模式下启动")
        
        # 保持主进程运行
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在关闭任务超时检测服务...")
        task_timeout_service.stop()
        logger.info("任务超时检测服务已关闭")