"""
域名空置检测服务
"""
from datetime import timedelta
from app import db
from app.models import Subdomain, User, Setting
from app.services.email import EmailService
from app.utils.timezone import now as beijing_now


class IdleDomainChecker:
    """域名空置检测器"""
    
    @staticmethod
    def check_for_reminder():
        """检查需要提醒的空置域名"""
        # 检查功能是否启用
        if Setting.get('idle_domain_check_enabled', '1') != '1':
            return []
        
        reminder_days = int(Setting.get('idle_domain_reminder_days', '7'))
        target_date = beijing_now() - timedelta(days=reminder_days)
        
        # 查询条件:
        # 1. 注册时间 >= reminder_days 天
        # 2. 未转移NS (ns_mode = 0)
        # 3. 未发送过提醒 (idle_reminder_sent_at IS NULL)
        # 4. 状态正常 (status = 1)
        idle_domains = Subdomain.query.filter(
            Subdomain.created_at <= target_date,
            Subdomain.ns_mode == 0,
            Subdomain.idle_reminder_sent_at.is_(None),
            Subdomain.status == 1
        ).all()
        
        # 过滤出真正没有记录的域名
        idle_domains = [s for s in idle_domains if s.records.count() == 0]
        
        return idle_domains
    
    @staticmethod
    def check_for_deletion():
        """检查需要删除的空置域名"""
        # 检查功能是否启用
        if Setting.get('idle_domain_check_enabled', '1') != '1':
            print('[IdleDomainChecker] Idle domain check is disabled')
            return []
        
        delete_days = int(Setting.get('idle_domain_delete_days', '10'))
        target_date = beijing_now() - timedelta(days=delete_days)
        
        print(f'[IdleDomainChecker] Checking for deletion: delete_days={delete_days}, target_date={target_date}')
        
        # 查询条件:
        # 1. 注册时间 >= delete_days 天
        # 2. 未转移NS (ns_mode = 0)
        # 3. 状态正常 (status = 1)
        idle_domains = Subdomain.query.filter(
            Subdomain.created_at <= target_date,
            Subdomain.ns_mode == 0,
            Subdomain.status == 1
        ).all()
        
        print(f'[IdleDomainChecker] Found {len(idle_domains)} domains matching criteria (before record check)')
        
        # 过滤出真正没有记录的域名
        idle_domains_no_records = []
        for s in idle_domains:
            record_count = s.records.count()
            if record_count == 0:
                idle_domains_no_records.append(s)
                print(f'[IdleDomainChecker] Domain {s.full_name} has no records, eligible for deletion')
            else:
                print(f'[IdleDomainChecker] Domain {s.full_name} has {record_count} records, skipping')
        
        print(f'[IdleDomainChecker] Total {len(idle_domains_no_records)} domains eligible for deletion')
        return idle_domains_no_records
    
    @staticmethod
    def send_reminder(subdomain):
        """发送空置提醒邮件"""
        user = subdomain.user
        if not user or not user.email:
            return False
        
        try:
            from app.services.email_templates import EmailTemplateService
            
            reminder_days = int(Setting.get('idle_domain_reminder_days', '7'))
            delete_days = int(Setting.get('idle_domain_delete_days', '10'))
            site_url = Setting.get('site_url', 'http://localhost:5000')
            
            # 使用统一的模板渲染方法
            subject, html = EmailTemplateService.render_email('idle_domain_reminder', {
                'username': user.username,
                'domain_name': subdomain.full_name,
                'days': reminder_days,
                'delete_days': delete_days,
                'site_url': site_url
            })
            
            if not subject or not html:
                print(f'[IdleDomainChecker] Email template idle_domain_reminder not found')
                return False
            
            success, msg = EmailService.send(user.email, subject, html)
            
            if success:
                # 记录提醒发送时间
                subdomain.idle_reminder_sent_at = beijing_now()
                db.session.commit()
                return True
            else:
                print(f'[IdleDomainChecker] Failed to send reminder to {user.email}: {msg}')
                return False
        except Exception as e:
            print(f'[IdleDomainChecker] Error sending reminder: {e}')
            return False
    
    @staticmethod
    def delete_idle_domain(subdomain):
        """删除空置域名"""
        user = subdomain.user
        domain_name = subdomain.full_name
        user_email = user.email if user else None
        subdomain_id = subdomain.id
        
        try:
            # 获取 DNS 服务
            dns_service = subdomain.domain.get_dns_service() if subdomain.domain else None
            zone_id = subdomain.domain.get_zone_id() if subdomain.domain else None
            
            # 删除 DNS 服务商上的记录（虽然应该没有记录，但为了保险起见）
            records = subdomain.records.all()
            for record in records:
                try:
                    if record.cf_record_id and dns_service and zone_id:
                        dns_service.delete_record(zone_id, record.cf_record_id)
                except Exception as e:
                    print(f'[IdleDomainChecker] Failed to delete DNS record: {e}')
            
            # 删除 DNS 服务商上的NS记录（如果已转移NS）
            if subdomain.ns_mode == 1 and dns_service and zone_id:
                try:
                    result = dns_service.get_records(zone_id, subdomain=subdomain.full_name, type='NS')
                    ns_records = result.get('list', [])
                    for ns_record in ns_records:
                        try:
                            dns_service.delete_record(zone_id, ns_record.record_id)
                        except:
                            pass
                except Exception as e:
                    print(f'[IdleDomainChecker] Failed to delete NS records: {e}')
            
            # 删除关联的转移记录（避免外键约束错误）
            from app.models.domain_transfer import DomainTransfer
            DomainTransfer.query.filter_by(subdomain_id=subdomain_id).delete()
            
            # 删除域名（级联删除DNS记录）
            db.session.delete(subdomain)
            db.session.commit()
            
            # 发送删除通知邮件
            if user_email and EmailService.is_configured():
                try:
                    from app.services.email_templates import EmailTemplateService
                    
                    delete_days = int(Setting.get('idle_domain_delete_days', '10'))
                    site_url = Setting.get('site_url', 'http://localhost:5000')
                    
                    # 使用统一的模板渲染方法
                    subject, html = EmailTemplateService.render_email('idle_domain_deleted', {
                        'username': user.username if user else 'User',
                        'domain_name': domain_name,
                        'days': delete_days,
                        'site_url': site_url
                    })
                    
                    if subject and html:
                        EmailService.send(user_email, subject, html)
                except Exception as e:
                    print(f'[IdleDomainChecker] Failed to send deletion notice: {e}')
            
            return True
        except Exception as e:
            print(f'[IdleDomainChecker] Failed to delete idle domain {domain_name}: {e}')
            return False
