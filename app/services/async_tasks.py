"""
异步任务服务
使用线程池处理耗时任务（如邮件发送）
生产环境建议使用 Celery
"""
import threading
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from app.utils.logger import get_logger

logger = get_logger('dns.async_tasks')

# 线程池
_executor = ThreadPoolExecutor(max_workers=5)

# 任务队列
_task_queue = Queue()


def submit_task(func, *args, **kwargs):
    """
    提交异步任务
    
    Args:
        func: 要执行的函数
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        Future: 任务Future对象
    """
    future = _executor.submit(func, *args, **kwargs)
    return future


def send_email_async(to_email, subject, html_content):
    """
    异步发送邮件
    
    Args:
        to_email: 收件人
        subject: 主题
        html_content: HTML内容
    """
    def _send():
        try:
            from app.services.email import EmailService
            success, msg = EmailService.send(to_email, subject, html_content)
            if success:
                logger.info(f'邮件发送成功: {to_email}')
            else:
                logger.error(f'邮件发送失败: {to_email}, {msg}')
        except Exception as e:
            logger.error(f'邮件发送异常: {to_email}, {e}')
    
    submit_task(_send)


def send_verification_async(to_email, token, verification_type, site_url):
    """
    异步发送验证邮件
    
    Args:
        to_email: 收件人
        token: 验证Token
        verification_type: 验证类型
        site_url: 站点URL
    """
    def _send():
        try:
            from app.services.email import EmailService
            success, msg = EmailService.send_verification(to_email, token, verification_type, site_url)
            if success:
                logger.info(f'验证邮件发送成功: {to_email}, 类型: {verification_type}')
            else:
                logger.error(f'验证邮件发送失败: {to_email}, {msg}')
        except Exception as e:
            logger.error(f'验证邮件发送异常: {to_email}, {e}')
    
    submit_task(_send)


def send_expiry_reminder_async(user_email, subdomain_name, expires_at, site_url):
    """
    异步发送到期提醒邮件
    
    Args:
        user_email: 用户邮箱
        subdomain_name: 域名
        expires_at: 到期时间
        site_url: 站点URL
    """
    def _send():
        try:
            from app.services.email_templates import EmailTemplateService
            from app.services.email import EmailService
            from app.utils.timezone import now as beijing_now
            
            days_remaining = (expires_at - beijing_now()).days
            
            # 使用统一的模板渲染方法
            subject, html = EmailTemplateService.render_email('domain_expiry', {
                'domain_name': subdomain_name,
                'days_remaining': days_remaining,
                'expires_at': expires_at.strftime('%Y-%m-%d %H:%M'),
                'renew_url': f"{site_url}/user/domains"
            })
            
            if not subject or not html:
                logger.error(f'邮件模板 domain_expiry 不存在')
                return
            
            success, msg = EmailService.send(user_email, subject, html)
            if success:
                logger.info(f'到期提醒发送成功: {user_email}, 域名: {subdomain_name}')
            else:
                logger.error(f'到期提醒发送失败: {user_email}, {msg}')
        except Exception as e:
            logger.error(f'到期提醒发送异常: {user_email}, {e}')
    
    submit_task(_send)


class TaskQueue:
    """
    简单的任务队列
    用于需要顺序执行的任务
    """
    
    def __init__(self, workers=1):
        self._queue = Queue()
        self._workers = []
        self._running = False
        self._worker_count = workers
    
    def start(self):
        """启动工作线程"""
        if self._running:
            return
        
        self._running = True
        for _ in range(self._worker_count):
            worker = threading.Thread(target=self._process_queue, daemon=True)
            worker.start()
            self._workers.append(worker)
    
    def stop(self):
        """停止工作线程"""
        self._running = False
        # 放入None来唤醒所有工作线程
        for _ in self._workers:
            self._queue.put(None)
    
    def add_task(self, func, *args, **kwargs):
        """添加任务到队列"""
        self._queue.put((func, args, kwargs))
    
    def _process_queue(self):
        """处理队列中的任务"""
        while self._running:
            try:
                task = self._queue.get(timeout=1)
                if task is None:
                    break
                
                func, args, kwargs = task
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    logger.error(f'任务执行失败: {e}')
            except:
                continue


# 邮件任务队列（单线程顺序发送，避免SMTP连接问题）
email_queue = TaskQueue(workers=1)


def init_async_tasks():
    """初始化异步任务服务"""
    email_queue.start()
    logger.info('异步任务服务已启动')


def shutdown_async_tasks():
    """关闭异步任务服务"""
    email_queue.stop()
    _executor.shutdown(wait=False)
    logger.info('异步任务服务已关闭')
