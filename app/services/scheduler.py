"""
定时任务服务 - 处理域名到期提醒、停用和删除
"""
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.utils.timezone import now as beijing_now


# 优化：减少线程池大小，降低内存占用
scheduler = BackgroundScheduler(
    executors={
        'default': {'type': 'threadpool', 'max_workers': 2}  # 默认10，减少到2
    },
    job_defaults={
        'coalesce': True,        # 合并错过的任务
        'max_instances': 1,      # 每个任务最多1个实例
        'misfire_grace_time': 60 # 错过任务的宽限时间
    }
)


def get_expiry_reminder_days():
    """从数据库获取到期提醒天数配置"""
    from app.models import Setting
    days_str = Setting.get('domain_expiry_reminder_days', '7,3,2,1')
    try:
        return [int(d.strip()) for d in days_str.split(',') if d.strip().isdigit()]
    except:
        return [7, 3, 2, 1]


def init_scheduler(app):
    """初始化定时任务"""
    
    @scheduler.scheduled_job(CronTrigger(hour=9, minute=0))
    def check_expiring_domains():
        """每天9点检查即将到期的域名，发送提醒邮件"""
        with app.app_context():
            from app import db
            from app.models import Subdomain, User, Setting
            from app.models.email_template import EmailTemplate
            from app.services.email import EmailService
            
            # 检查功能是否启用
            if Setting.get('domain_expiry_reminder_enabled', '1') != '1':
                return
            
            if not EmailService.is_configured():
                return
            
            site_name = Setting.get('site_name', '六趣DNS')
            site_url = Setting.get('site_url', '')
            base_url = site_url.rstrip('/') if site_url else ''
            
            # 从数据库获取提醒天数配置
            reminder_days = get_expiry_reminder_days()
            
            for days in reminder_days:
                target_date = beijing_now() + timedelta(days=days)
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
                        
                        # 使用邮件模板
                        subject, html = EmailTemplate.render('domain_expiry', {
                            'site_name': site_name,
                            'domain_name': sub.full_name,
                            'days_remaining': str(days),
                            'expires_at': sub.expires_at.strftime('%Y-%m-%d %H:%M'),
                            'renew_url': renew_url
                        })
                        
                        if subject and html:
                            EmailService.send(user.email, subject, html)
                            print(f'[Scheduler] Sent expiry reminder to {user.email} for {sub.full_name} ({days} days)')
    
    @scheduler.scheduled_job(CronTrigger(minute=0))
    def check_expired_domains():
        """每小时检查已到期域名，设置为停用状态"""
        with app.app_context():
            from app import db
            from app.models import Subdomain, Setting
            
            # 获取过期停用天数配置（0表示立即停用）
            disable_days = int(Setting.get('domain_expiry_disable_days', '0'))
            
            now = beijing_now()
            disable_target = now - timedelta(days=disable_days)
            
            expired = Subdomain.query.filter(
                Subdomain.expires_at <= disable_target,
                Subdomain.expires_at != None,
                Subdomain.status == 1
            ).all()
            
            for sub in expired:
                sub.status = 0  # 停用
                print(f'[Scheduler] Domain {sub.full_name} expired and disabled')
            
            if expired:
                db.session.commit()
    
    @scheduler.scheduled_job(CronTrigger(hour=3, minute=0))
    def delete_expired_domains():
        """每天凌晨3点删除到期超过指定天数的域名（包括DNS记录）"""
        with app.app_context():
            from app import db
            from app.models import Subdomain, DnsRecord, User, Setting
            from app.models.email_template import EmailTemplate
            from app.models.domain_transfer import DomainTransfer
            from app.services.email import EmailService
            
            site_name = Setting.get('site_name', '六趣DNS')
            site_url = Setting.get('site_url', '')
            base_url = site_url.rstrip('/') if site_url else ''
            
            # 从数据库获取删除天数配置（默认3天）
            delete_days = int(Setting.get('domain_expiry_delete_days', '3'))
            delete_target = beijing_now() - timedelta(days=delete_days)
            
            # 查找到期超过指定天数的域名
            expired_subs = Subdomain.query.filter(
                Subdomain.expires_at <= delete_target,
                Subdomain.expires_at != None
            ).all()
            
            deleted_domains = 0
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
                    except Exception as e:
                        print(f'[Scheduler] Failed to delete DNS record: {e}')
                    deleted_records += 1
                
                # 删除 DNS 服务商上的NS记录（如果已转移NS）
                if sub.ns_mode == 1 and dns_service and zone_id:
                    try:
                        result = dns_service.get_records(zone_id, subdomain=sub.full_name, type='NS')
                        ns_records = result.get('list', [])
                        for ns_record in ns_records:
                            try:
                                dns_service.delete_record(zone_id, ns_record.record_id)
                            except:
                                pass
                    except Exception as e:
                        print(f'[Scheduler] Failed to delete NS records: {e}')
                
                # 删除关联的转移记录（避免外键约束错误）
                DomainTransfer.query.filter_by(subdomain_id=subdomain_id).delete()
                
                # 删除域名（级联删除DNS记录）
                db.session.delete(sub)
                deleted_domains += 1
                print(f'[Scheduler] Deleted expired domain: {domain_name}')
                
                # 发送删除通知邮件
                if user_email and EmailService.is_configured():
                    new_domain_url = f'{base_url}/user/domains/new' if base_url else '/user/domains/new'
                    
                    # 使用邮件模板
                    subject, html = EmailTemplate.render('domain_deleted', {
                        'site_name': site_name,
                        'domain_name': domain_name,
                        'expires_at': expires_at_str,
                        'deleted_at': beijing_now().strftime('%Y-%m-%d %H:%M'),
                        'new_domain_url': new_domain_url
                    })
                    
                    if subject and html:
                        EmailService.send(user_email, subject, html)
                        print(f'[Scheduler] Sent deletion notice to {user_email} for {domain_name}')
            
            if deleted_domains > 0:
                db.session.commit()
                print(f'[Scheduler] Total {deleted_domains} domains and {deleted_records} DNS records deleted')
    
    @scheduler.scheduled_job(CronTrigger(hour=8, minute=0))
    def process_auto_renew():
        """每天8点处理自动续费（仅处理用户开启自动续费的域名）"""
        with app.app_context():
            from app.services.auto_renew import AutoRenewService
            result = AutoRenewService.process_auto_renew()
            if not result.get('disabled'):
                print(f'[Scheduler] Auto renew completed: success={result["success"]}, failed={result["failed"]}, skipped={result["skipped"]}')
    
    @scheduler.scheduled_job(CronTrigger(hour=2, minute=0))
    def daily_heartbeat():
        """每天凌晨2点发送站点心跳"""
        with app.app_context():
            from app.services.heartbeat import send_heartbeat
            send_heartbeat()
    
    @scheduler.scheduled_job(CronTrigger(hour=10, minute=0))
    def check_idle_domains_reminder():
        """每天10点检查空置域名，发送提醒邮件"""
        with app.app_context():
            from app.services.idle_domain_checker import IdleDomainChecker
            from app.models import Setting
            
            # 检查功能是否启用
            if Setting.get('idle_domain_check_enabled', '1') != '1':
                return
            
            idle_domains = IdleDomainChecker.check_for_reminder()
            
            sent_count = 0
            for subdomain in idle_domains:
                success = IdleDomainChecker.send_reminder(subdomain)
                if success:
                    sent_count += 1
                    print(f'[Scheduler] Sent idle reminder for {subdomain.full_name}')
            
            if sent_count > 0:
                print(f'[Scheduler] Total {sent_count} idle domain reminders sent')
    
    @scheduler.scheduled_job(CronTrigger(hour=4, minute=0))
    def delete_idle_domains():
        """每天凌晨4点删除长期空置的域名"""
        with app.app_context():
            from app.services.idle_domain_checker import IdleDomainChecker
            from app.models import Setting
            
            # 检查功能是否启用
            if Setting.get('idle_domain_check_enabled', '1') != '1':
                return
            
            idle_domains = IdleDomainChecker.check_for_deletion()
            
            deleted_count = 0
            for subdomain in idle_domains:
                success = IdleDomainChecker.delete_idle_domain(subdomain)
                if success:
                    deleted_count += 1
                    print(f'[Scheduler] Deleted idle domain: {subdomain.full_name}')
            
            if deleted_count > 0:
                print(f'[Scheduler] Total {deleted_count} idle domains deleted')
    
    # 启动调度器
    if not scheduler.running:
        scheduler.start()
        print('[Scheduler] Started')
    
    # 启动时发送首次心跳（延迟5秒执行，确保应用完全启动）
    import threading
    def delayed_heartbeat():
        import time
        time.sleep(5)
        with app.app_context():
            try:
                from app.services.heartbeat import send_heartbeat
                send_heartbeat()
            except Exception:
                pass
    
    threading.Thread(target=delayed_heartbeat, daemon=True).start()
