"""
定时任务执行日志模型
"""
from datetime import datetime
from app import db
from app.utils.timezone import now as beijing_now


class CronLog(db.Model):
    """定时任务执行日志"""
    __tablename__ = 'cron_logs'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(db.String(50), nullable=False, index=True, comment='任务ID')
    task_name = db.Column(db.String(100), nullable=False, comment='任务名称')
    trigger_type = db.Column(db.String(20), default='auto', comment='触发方式: auto/manual/api')
    triggered_by = db.Column(db.String(100), nullable=True, comment='触发者(用户名/IP)')
    status = db.Column(db.String(20), default='running', comment='执行状态: running/success/failed')
    started_at = db.Column(db.DateTime, nullable=False, default=beijing_now, comment='开始时间')
    finished_at = db.Column(db.DateTime, nullable=True, comment='结束时间')
    duration = db.Column(db.Integer, nullable=True, comment='耗时(秒)')
    result = db.Column(db.JSON, nullable=True, comment='执行结果')
    error_message = db.Column(db.Text, nullable=True, comment='错误信息')
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'task_name': self.task_name,
            'triggered_by': self.trigger_type,  # 前端使用 triggered_by 显示触发方式
            'trigger_user': self.triggered_by,  # 触发者用户名
            'status': self.status,
            'started_at': self.started_at.strftime('%Y-%m-%d %H:%M:%S') if self.started_at else None,
            'finished_at': self.finished_at.strftime('%Y-%m-%d %H:%M:%S') if self.finished_at else None,
            'duration': self.duration,
            'result': self.result,
            'error_message': self.error_message,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }
    
    @classmethod
    def start_log(cls, task_id, task_name, trigger_type='auto', triggered_by=None):
        """开始记录任务执行"""
        log = cls(
            task_id=task_id,
            task_name=task_name,
            trigger_type=trigger_type,
            triggered_by=triggered_by,
            status='running',
            started_at=beijing_now()
        )
        db.session.add(log)
        db.session.commit()
        return log
    
    @classmethod
    def finish_log(cls, log_id, status='success', result=None, error_message=None):
        """完成任务执行记录"""
        log = cls.query.get(log_id)
        if log:
            log.status = status
            log.finished_at = beijing_now()
            log.duration = int((log.finished_at - log.started_at).total_seconds())
            log.result = result
            log.error_message = error_message
            db.session.commit()
        return log
    
    @classmethod
    def get_last_execution(cls, task_id):
        """获取任务最后一次成功执行记录"""
        return cls.query.filter_by(
            task_id=task_id,
            status='success'
        ).order_by(cls.started_at.desc()).first()
    
    @classmethod
    def cleanup_old_logs(cls, days=30):
        """清理指定天数前的日志"""
        from datetime import timedelta
        cutoff = beijing_now() - timedelta(days=days)
        deleted = cls.query.filter(cls.created_at < cutoff).delete()
        db.session.commit()
        return deleted
