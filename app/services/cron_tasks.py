"""
定时任务服务 - 统一管理所有定时任务的执行逻辑
"""
import secrets
from datetime import datetime, timedelta
from app.utils.timezone import now as beijing_now


# 任务定义
CRON_TASKS = {
    'domain_expiry_reminder': {
        'name': '域名到期提醒',
        'name_en': 'Domain Expiry Reminder',
        'description': '检查即将到期的域名，发送提醒邮件',
        'description_en': 'Check expiring domains and send reminder emails',
        'schedule': '09:00',
        'schedule_type': 'daily'
    },
    'domain_expiry_disable': {
        'name': '停用到期域名',
        'name_en': 'Disable Expired Domains',
        'description': '将已过期的域名设置为停用状态',
        'description_en': 'Disable domains that have expired',
        'schedule': '每小时',
        'schedule_type': 'hourly'
    },
    'domain_expiry_delete': {
        'name': '删除过期域名',
        'name_en': 'Delete Expired Domains',
        'description': '删除过期超过指定天数的域名及其DNS记录',
        'description_en': 'Delete domains expired for specified days',
        'schedule': '03:00',
        'schedule_type': 'daily'
    },
    'domain_auto_renew': {
        'name': '域名自动续费',
        'name_en': 'Domain Auto Renew',
        'description': '处理开启自动续费的域名',
        'description_en': 'Process domains with auto-renew enabled',
        'schedule': '08:00',
        'schedule_type': 'daily'
    },
    'idle_domain_reminder': {
        'name': '空置域名提醒',
        'name_en': 'Idle Domain Reminder',
        'description': '检查空置域名，发送提醒邮件',
        'description_en': 'Check idle domains and send reminder emails',
        'schedule': '10:00',
        'schedule_type': 'daily'
    },
    'idle_domain_delete': {
        'name': '删除空置域名',
        'name_en': 'Delete Idle Domains',
        'description': '删除长期空置的域名',
        'description_en': 'Delete domains idle for too long',
        'schedule': '04:00',
        'schedule_type': 'daily'
    },
    'database_backup': {
        'name': '数据库备份',
        'name_en': 'Database Backup',
        'description': '自动备份数据库',
        'description_en': 'Automatic database backup',
        'schedule': '03:30',
        'schedule_type': 'daily'
    },
    'cleanup_logs': {
        'name': '清理过期日志',
        'name_en': 'Cleanup Old Logs',
        'description': '清理30天前的操作日志和任务日志',
        'description_en': 'Clean up logs older than 30 days',
        'schedule': '04:30',
        'schedule_type': 'daily'
    },
    'heartbeat': {
        'name': '站点心跳',
        'name_en': 'Site Heartbeat',
        'description': '发送站点心跳检测',
        'description_en': 'Send site heartbeat',
        'schedule': '02:00',
        'schedule_type': 'daily'
    },
    'expire_transfers': {
        'name': '过期转移处理',
        'name_en': 'Expire Pending Transfers',
        'description': '将过期的待验证转移请求标记为已过期',
        'description_en': 'Mark expired pending transfer requests as expired',
        'schedule': '每5分钟',
        'schedule_type': 'interval'
    }
}


class CronTaskService:
    """定时任务服务"""
    
    @staticmethod
    def get_secret_key():
        """获取或生成Cron密钥"""
        from app.models import Setting
        key = Setting.get('cron_secret_key', '')
        if not key:
            key = secrets.token_urlsafe(32)
            Setting.set('cron_secret_key', key)
        return key
    
    @staticmethod
    def regenerate_secret_key():
        """重新生成Cron密钥"""
        from app.models import Setting
        key = secrets.token_urlsafe(32)
        Setting.set('cron_secret_key', key)
        return key
    
    @staticmethod
    def verify_secret_key(key):
        """验证Cron密钥"""
        from app.models import Setting
        stored_key = Setting.get('cron_secret_key', '')
        return stored_key and key == stored_key
    
    @staticmethod
    def get_task_list(locale='zh'):
        """获取任务列表"""
        from app.models import CronLog
        
        tasks = []
        for task_id, task_info in CRON_TASKS.items():
            # 获取最后一次执行记录
            last_log = CronLog.query.filter_by(task_id=task_id).order_by(CronLog.started_at.desc()).first()
            
            tasks.append({
                'id': task_id,
                'name': task_info['name'] if locale == 'zh' else task_info['name_en'],
                'description': task_info['description'] if locale == 'zh' else task_info['description_en'],
                'schedule': task_info['schedule'],
                'schedule_type': task_info['schedule_type'],
                'last_run': last_log.started_at.strftime('%Y-%m-%d %H:%M:%S') if last_log else None,
                'last_status': last_log.status if last_log else None
            })
        
        return tasks
    
    @staticmethod
    def run_task(task_id, trigger_type='manual', triggered_by=None):
        """执行单个任务"""
        from app.models import CronLog
        
        if task_id not in CRON_TASKS:
            return {'success': False, 'message': f'未知任务: {task_id}'}
        
        task_info = CRON_TASKS[task_id]
        
        # 开始记录
        log = CronLog.start_log(
            task_id=task_id,
            task_name=task_info['name'],
            trigger_type=trigger_type,
            triggered_by=triggered_by
        )
        
        try:
            # 执行任务
            result = CronTaskService._execute_task(task_id)
            
            # 完成记录
            CronLog.finish_log(log.id, status='success', result=result)
            
            return {
                'success': True,
                'task_id': task_id,
                'task_name': task_info['name'],
                'result': result,
                'duration': log.duration
            }
        except Exception as e:
            # 记录错误
            CronLog.finish_log(log.id, status='failed', error_message=str(e))
            
            return {
                'success': False,
                'task_id': task_id,
                'task_name': task_info['name'],
                'error': str(e)
            }
    
    @staticmethod
    def run_all_tasks(triggered_by=None):
        """执行所有任务（强制执行，用于URL触发）"""
        results = {
            'executed': [],
            'failed': []
        }
        
        for task_id in CRON_TASKS.keys():
            result = CronTaskService.run_task(
                task_id=task_id,
                trigger_type='external',
                triggered_by=triggered_by
            )
            
            if result['success']:
                results['executed'].append(result)
            else:
                results['failed'].append(result)
        
        return results
    
    @staticmethod
    def _execute_task(task_id):
        """执行具体任务逻辑"""
        if task_id == 'domain_expiry_reminder':
            return CronTaskService._task_domain_expiry_reminder()
        elif task_id == 'domain_expiry_disable':
            return CronTaskService._task_domain_expiry_disable()
        elif task_id == 'domain_expiry_delete':
            return CronTaskService._task_domain_expiry_delete()
        elif task_id == 'domain_auto_renew':
            return CronTaskService._task_domain_auto_renew()
        elif task_id == 'idle_domain_reminder':
            return CronTaskService._task_idle_domain_reminder()
        elif task_id == 'idle_domain_delete':
            return CronTaskService._task_idle_domain_delete()
        elif task_id == 'database_backup':
            return CronTaskService._task_database_backup()
        elif task_id == 'cleanup_logs':
            return CronTaskService._task_cleanup_logs()
        elif task_id == 'heartbeat':
            return CronTaskService._task_heartbeat()
        elif task_id == 'expire_transfers':
            return CronTaskService._task_expire_transfers()
        else:
            raise ValueError(f'未实现的任务: {task_id}')

    
    @staticmethod
    def _task_domain_expiry_reminder():
        """域名到期提醒"""
        from app import db
        from app.models import Subdomain, User, Setting
        from app.models.email_template import EmailTemplate
        from app.services.email import EmailService
        
        # 检查功能是否启用
        if Setting.get('domain_expiry_reminder_enabled', '1') != '1':
            return {'skipped': True, 'reason': '功能已禁用'}
        
        if not EmailService.is_configured():
            return {'skipped': True, 'reason': '邮件服务未配置'}
        
        site_name = Setting.get('site_name', '六趣DNS')
        site_url = Setting.get('site_url', '')
        base_url = site_url.rstrip('/') if site_url else ''
        
        # 获取提醒天数配置
        days_str = Setting.get('domain_expiry_reminder_days', '7,3,2,1')
        try:
            reminder_days = [int(d.strip()) for d in days_str.split(',') if d.strip().isdigit()]
        except:
            reminder_days = [7, 3, 2, 1]
        
        now = beijing_now()
        sent_count = 0
        domains_notified = []
        
        for days in reminder_days:
            target_date = now + timedelta(days=days)
            start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            
            expiring = Subdomain.query.filter(
                Subdomain.expires_at >= start,
                Subdomain.expires_at < end,
                Subdomain.status == 1
            ).all()
            
            for sub in expiring:
                user = User.query.get(sub.user_id)
                if user:
                    renew_url = f'{base_url}/user/domains/{sub.id}' if base_url else f'/user/domains/{sub.id}'
                    
                    subject, html = EmailTemplate.render('domain_expiry', {
                        'site_name': site_name,
                        'domain_name': sub.full_name,
                        'days_remaining': str(days),
                        'expires_at': sub.expires_at.strftime('%Y-%m-%d %H:%M'),
                        'renew_url': renew_url
                    })
                    
                    if subject and html:
                        success, _ = EmailService.send(user.email, subject, html)
                        if success:
                            sent_count += 1
                            domains_notified.append({
                                'domain': sub.full_name,
                                'user': user.username,
                                'days': days
                            })
        
        return {
            'sent_count': sent_count,
            'reminder_days': reminder_days,
            'domains': domains_notified
        }
    
    @staticmethod
    def _task_domain_expiry_disable():
        """停用到期域名"""
        from app import db
        from app.models import Subdomain, Setting
        
        disable_days = int(Setting.get('domain_expiry_disable_days', '0'))
        now = beijing_now()
        disable_target = now - timedelta(days=disable_days)
        
        expired = Subdomain.query.filter(
            Subdomain.expires_at <= disable_target,
            Subdomain.expires_at != None,
            Subdomain.status == 1
        ).all()
        
        disabled_domains = []
        for sub in expired:
            sub.status = 0
            disabled_domains.append(sub.full_name)
        
        if expired:
            db.session.commit()
        
        return {
            'disabled_count': len(disabled_domains),
            'domains': disabled_domains
        }
    
    @staticmethod
    def _task_domain_expiry_delete():
        """删除过期域名"""
        from app import db
        from app.models import Subdomain, DnsRecord, User, Setting
        from app.models.email_template import EmailTemplate
        from app.models.domain_transfer import DomainTransfer
        from app.services.email import EmailService
        
        site_name = Setting.get('site_name', '六趣DNS')
        site_url = Setting.get('site_url', '')
        base_url = site_url.rstrip('/') if site_url else ''
        
        delete_days = int(Setting.get('domain_expiry_delete_days', '30'))
        delete_target = beijing_now() - timedelta(days=delete_days)
        
        expired_subs = Subdomain.query.filter(
            Subdomain.expires_at <= delete_target,
            Subdomain.expires_at != None
        ).all()
        
        deleted_domains = []
        deleted_records = 0
        
        for sub in expired_subs:
            user = User.query.get(sub.user_id)
            domain_name = sub.full_name
            subdomain_id = sub.id
            user_email = user.email if user else None
            expires_at_str = sub.expires_at.strftime('%Y-%m-%d %H:%M') if sub.expires_at else ''
            
            # 获取 DNS 服务
            dns_service = sub.domain.get_dns_service() if sub.domain else None
            zone_id = sub.domain.get_zone_id() if sub.domain else None
            
            # 删除 DNS 服务商上的记录
            records = sub.records.all()
            for record in records:
                try:
                    if record.cf_record_id and dns_service and zone_id:
                        dns_service.delete_record(zone_id, record.cf_record_id)
                except Exception:
                    pass
                deleted_records += 1
            
            # 删除关联的转移记录（避免外键约束错误）
            DomainTransfer.query.filter_by(subdomain_id=subdomain_id).delete()
            
            # 删除域名
            db.session.delete(sub)
            deleted_domains.append(domain_name)
            
            # 发送删除通知邮件
            if user_email and EmailService.is_configured():
                new_domain_url = f'{base_url}/user/domains/new' if base_url else '/user/domains/new'
                
                subject, html = EmailTemplate.render('domain_deleted', {
                    'site_name': site_name,
                    'domain_name': domain_name,
                    'expires_at': expires_at_str,
                    'deleted_at': beijing_now().strftime('%Y-%m-%d %H:%M'),
                    'new_domain_url': new_domain_url
                })
                
                if subject and html:
                    EmailService.send(user_email, subject, html)
        
        if deleted_domains:
            db.session.commit()
        
        return {
            'deleted_count': len(deleted_domains),
            'deleted_records': deleted_records,
            'domains': deleted_domains
        }
    
    @staticmethod
    def _task_domain_auto_renew():
        """域名自动续费"""
        from app.services.auto_renew import AutoRenewService
        result = AutoRenewService.process_auto_renew()
        return result
    
    @staticmethod
    def _task_idle_domain_reminder():
        """空置域名提醒"""
        from app.services.idle_domain_checker import IdleDomainChecker
        from app.models import Setting
        
        if Setting.get('idle_domain_check_enabled', '1') != '1':
            return {'skipped': True, 'reason': '功能已禁用'}
        
        idle_domains = IdleDomainChecker.check_for_reminder()
        
        sent_count = 0
        domains_notified = []
        for subdomain in idle_domains:
            success = IdleDomainChecker.send_reminder(subdomain)
            if success:
                sent_count += 1
                domains_notified.append(subdomain.full_name)
        
        return {
            'sent_count': sent_count,
            'domains': domains_notified
        }
    
    @staticmethod
    def _task_idle_domain_delete():
        """删除空置域名"""
        from app.services.idle_domain_checker import IdleDomainChecker
        from app.models import Setting
        
        if Setting.get('idle_domain_check_enabled', '1') != '1':
            return {'skipped': True, 'reason': '功能已禁用'}
        
        idle_domains = IdleDomainChecker.check_for_deletion()
        
        deleted_count = 0
        deleted_domains = []
        for subdomain in idle_domains:
            domain_name = subdomain.full_name
            success = IdleDomainChecker.delete_idle_domain(subdomain)
            if success:
                deleted_count += 1
                deleted_domains.append(domain_name)
        
        return {
            'deleted_count': deleted_count,
            'domains': deleted_domains
        }
    
    @staticmethod
    def _task_database_backup():
        """数据库备份"""
        import subprocess
        import os
        import gzip
        import shutil
        from pathlib import Path
        from dotenv import load_dotenv
        
        load_dotenv()
        
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '3306')
        db_name = os.getenv('DB_NAME', 'dns_system')
        db_user = os.getenv('DB_USER', 'root')
        db_password = os.getenv('DB_PASSWORD', '')
        
        backup_dir = Path(__file__).parent.parent.parent / 'backups'
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = beijing_now().strftime('%Y%m%d_%H%M%S')
        backup_file = backup_dir / f'{db_name}_{timestamp}.sql'
        
        cmd = [
            'mysqldump',
            f'--host={db_host}',
            f'--port={db_port}',
            f'--user={db_user}',
            '--single-transaction',
            '--routines',
            '--triggers',
            db_name
        ]
        
        if db_password:
            cmd.insert(1, f'--password={db_password}')
        
        try:
            with open(backup_file, 'w', encoding='utf-8') as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
            
            if result.returncode != 0:
                backup_file.unlink(missing_ok=True)
                raise Exception(f'mysqldump 失败: {result.stderr}')
            
            # 压缩
            compressed_file = Path(str(backup_file) + '.gz')
            with open(backup_file, 'rb') as f_in:
                with gzip.open(compressed_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            backup_file.unlink()
            
            file_size = compressed_file.stat().st_size / 1024 / 1024
            
            # 清理旧备份
            retention_days = int(os.getenv('BACKUP_RETENTION_DAYS', '7'))
            cutoff_date = beijing_now() - timedelta(days=retention_days)
            cleaned = 0
            for old_file in backup_dir.glob('*.sql*'):
                file_mtime = datetime.fromtimestamp(old_file.stat().st_mtime)
                if file_mtime < cutoff_date:
                    old_file.unlink()
                    cleaned += 1
            
            return {
                'backup_file': compressed_file.name,
                'file_size_mb': round(file_size, 2),
                'old_backups_cleaned': cleaned
            }
        except FileNotFoundError:
            return {'skipped': True, 'reason': 'mysqldump 命令未找到'}
        except Exception as e:
            raise e
    
    @staticmethod
    def _task_cleanup_logs():
        """清理过期日志"""
        from app import db
        from app.models import OperationLog, CronLog
        
        cutoff = beijing_now() - timedelta(days=30)
        
        # 清理操作日志
        op_deleted = OperationLog.query.filter(OperationLog.created_at < cutoff).delete()
        
        # 清理任务日志
        cron_deleted = CronLog.query.filter(CronLog.created_at < cutoff).delete()
        
        db.session.commit()
        
        return {
            'operation_logs_deleted': op_deleted,
            'cron_logs_deleted': cron_deleted
        }
    
    @staticmethod
    def _task_heartbeat():
        """站点心跳"""
        from app.services.heartbeat import send_heartbeat
        send_heartbeat()
        return {'sent': True}
    
    @staticmethod
    def _task_expire_transfers():
        """过期转移处理"""
        from app.services.transfer_service import TransferService
        
        expired_count = TransferService.expire_pending_transfers()
        
        return {
            'expired_count': expired_count
        }
