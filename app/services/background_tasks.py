"""
后台任务管理器
使用 ThreadPoolExecutor 执行后台任务，替代 Celery
"""
import uuid
import logging
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Callable, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    status: str  # pending, running, completed, failed
    progress: Dict[str, int] = field(default_factory=dict)  # {'current': int, 'total': int}
    result: Any = None
    error: Optional[str] = None
    submitted_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class BackgroundTaskManager:
    """
    后台任务管理器
    使用线程池执行异步任务，提供任务状态跟踪功能
    """
    
    # 线程池
    _executor: Optional[ThreadPoolExecutor] = None
    _max_workers: int = 2
    _max_queue_size: int = 100
    
    # 任务存储：{task_id: TaskInfo}
    _tasks: Dict[str, TaskInfo] = {}
    _futures: Dict[str, Future] = {}
    
    # 线程锁
    _lock = threading.Lock()
    
    # 初始化标志
    _initialized = False
    
    @classmethod
    def initialize(cls, max_workers: int = 2, max_queue_size: int = 100):
        """
        初始化任务管理器
        
        Args:
            max_workers: 最大工作线程数
            max_queue_size: 最大队列大小
        """
        if cls._initialized:
            return
        
        cls._max_workers = max_workers
        cls._max_queue_size = max_queue_size
        cls._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix='bg_task_'
        )
        cls._initialized = True
        logger.info(f'BackgroundTaskManager initialized with {max_workers} workers')
    
    @classmethod
    def _ensure_initialized(cls):
        """确保已初始化"""
        if not cls._initialized:
            cls.initialize()
    
    @classmethod
    def submit_task(cls, task_func: Callable, *args, **kwargs) -> str:
        """
        提交后台任务
        
        Args:
            task_func: 任务函数
            *args, **kwargs: 任务参数
            
        Returns:
            task_id: 任务ID
            
        Raises:
            RuntimeError: 队列已满
        """
        cls._ensure_initialized()
        
        # 检查队列大小
        with cls._lock:
            if len(cls._tasks) >= cls._max_queue_size:
                raise RuntimeError('后台任务队列已满，请稍后重试')
            
            # 生成任务ID
            task_id = str(uuid.uuid4())
            
            # 创建任务信息
            task_info = TaskInfo(
                task_id=task_id,
                status='pending'
            )
            cls._tasks[task_id] = task_info
        
        # 提交任务
        try:
            future = cls._executor.submit(cls._task_wrapper, task_id, task_func, *args, **kwargs)
            cls._futures[task_id] = future
            logger.info(f'Task {task_id} submitted')
            return task_id
        except Exception as e:
            # 提交失败，删除任务信息
            with cls._lock:
                cls._tasks.pop(task_id, None)
            logger.error(f'Failed to submit task: {e}')
            raise
    
    @classmethod
    def _task_wrapper(cls, task_id: str, task_func: Callable, *args, **kwargs):
        """
        任务包装器，处理任务执行和状态更新
        
        Args:
            task_id: 任务ID
            task_func: 任务函数
            *args, **kwargs: 任务参数
        """
        # 更新状态为运行中
        with cls._lock:
            task_info = cls._tasks.get(task_id)
            if task_info:
                task_info.status = 'running'
                task_info.started_at = datetime.now()
        
        logger.info(f'Task {task_id} started')
        
        try:
            # 执行任务
            result = task_func(*args, **kwargs)
            
            # 更新状态为完成
            with cls._lock:
                task_info = cls._tasks.get(task_id)
                if task_info:
                    task_info.status = 'completed'
                    task_info.result = result
                    task_info.completed_at = datetime.now()
            
            logger.info(f'Task {task_id} completed successfully')
            return result
            
        except Exception as e:
            # 更新状态为失败
            with cls._lock:
                task_info = cls._tasks.get(task_id)
                if task_info:
                    task_info.status = 'failed'
                    task_info.error = str(e)
                    task_info.completed_at = datetime.now()
            
            logger.error(f'Task {task_id} failed: {e}', exc_info=True)
            raise
    
    @classmethod
    def get_task_status(cls, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息，如果任务不存在返回 None
            {
                'task_id': str,
                'status': 'pending|running|completed|failed',
                'progress': {'current': int, 'total': int},
                'result': any,
                'error': str,
                'submitted_at': datetime,
                'started_at': datetime,
                'completed_at': datetime
            }
        """
        with cls._lock:
            task_info = cls._tasks.get(task_id)
            if not task_info:
                return None
            
            return {
                'task_id': task_info.task_id,
                'status': task_info.status,
                'progress': task_info.progress.copy(),
                'result': task_info.result,
                'error': task_info.error,
                'submitted_at': task_info.submitted_at,
                'started_at': task_info.started_at,
                'completed_at': task_info.completed_at
            }
    
    @classmethod
    def update_task_progress(cls, task_id: str, current: int, total: int):
        """
        更新任务进度
        
        Args:
            task_id: 任务ID
            current: 当前进度
            total: 总数
        """
        with cls._lock:
            task_info = cls._tasks.get(task_id)
            if task_info:
                task_info.progress = {'current': current, 'total': total}
                logger.debug(f'Task {task_id} progress: {current}/{total}')
    
    @classmethod
    def cancel_task(cls, task_id: str) -> bool:
        """
        取消任务（尽力而为，不保证一定能取消）
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功取消
        """
        with cls._lock:
            future = cls._futures.get(task_id)
            task_info = cls._tasks.get(task_id)
            
            if not future or not task_info:
                return False
            
            # 如果任务还未开始，可以取消
            if task_info.status == 'pending':
                cancelled = future.cancel()
                if cancelled:
                    task_info.status = 'cancelled'
                    task_info.completed_at = datetime.now()
                    logger.info(f'Task {task_id} cancelled')
                return cancelled
            
            # 如果任务已经在运行，无法取消
            return False
    
    @classmethod
    def cleanup_old_tasks(cls, keep_count: int = 100):
        """
        清理旧任务，保留最近的 N 个任务
        
        Args:
            keep_count: 保留的任务数量
        """
        with cls._lock:
            if len(cls._tasks) <= keep_count:
                return
            
            # 按完成时间排序，删除最早的任务
            completed_tasks = [
                (task_id, task_info)
                for task_id, task_info in cls._tasks.items()
                if task_info.status in ('completed', 'failed', 'cancelled')
            ]
            
            if len(completed_tasks) > keep_count:
                # 按完成时间排序
                completed_tasks.sort(key=lambda x: x[1].completed_at or datetime.min)
                
                # 删除最早的任务
                to_remove = completed_tasks[:len(completed_tasks) - keep_count]
                for task_id, _ in to_remove:
                    cls._tasks.pop(task_id, None)
                    cls._futures.pop(task_id, None)
                
                logger.info(f'Cleaned up {len(to_remove)} old tasks')
    
    @classmethod
    def get_all_tasks(cls) -> Dict[str, Dict[str, Any]]:
        """
        获取所有任务状态
        
        Returns:
            所有任务的状态信息
        """
        with cls._lock:
            return {
                task_id: {
                    'task_id': task_info.task_id,
                    'status': task_info.status,
                    'progress': task_info.progress.copy(),
                    'submitted_at': task_info.submitted_at,
                    'started_at': task_info.started_at,
                    'completed_at': task_info.completed_at
                }
                for task_id, task_info in cls._tasks.items()
            }
    
    @classmethod
    def shutdown(cls, wait: bool = True):
        """
        关闭任务管理器
        
        Args:
            wait: 是否等待所有任务完成
        """
        if cls._executor:
            logger.info('Shutting down BackgroundTaskManager')
            cls._executor.shutdown(wait=wait)
            cls._initialized = False
