from datetime import datetime, timedelta
from sqlalchemy import and_, or_
from app import db
from app.models import User, EmailCampaign, EmailLog, Setting
from app.services.email import EmailService
from app.services.background_tasks import BackgroundTaskManager
import json
import logging

logger = logging.getLogger(__name__)


class EmailCampaignService:
    """群发邮件服务"""
    
    @staticmethod
    def create_campaign(name, subject, content, recipient_filter, scheduled_at=None, created_by=None):
        """创建群发任务"""
        campaign = EmailCampaign(
            name=name,
            subject=subject,
            content=content,
            recipient_filter=json.dumps(recipient_filter) if isinstance(recipient_filter, dict) else recipient_filter,
            scheduled_at=scheduled_at,
            created_by=created_by,
            status=EmailCampaign.STATUS_DRAFT
        )
        db.session.add(campaign)
        db.session.commit()
        return campaign
    
    @staticmethod
    def filter_recipients(recipient_filter):
        """
        筛选收件人
        支持的筛选条件:
        - role: 角色筛选 (admin/user)
        - activity_level: 活跃度筛选 (high/medium/low/dormant/lost)
        - min_balance: 最小余额
        - max_balance: 最大余额
        - registered_after: 注册时间起始
        - registered_before: 注册时间结束
        - user_ids: 自定义用户ID列表
        """
        if isinstance(recipient_filter, str):
            recipient_filter = json.loads(recipient_filter)
        
        # 只查询状态正常的用户
        query = User.query.filter(User.status == 1)
        
        # 角色筛选
        if recipient_filter.get('role'):
            if recipient_filter['role'] == 'admin':
                query = query.filter(User.role == User.ROLE_ADMIN)
            elif recipient_filter['role'] == 'user':
                query = query.filter(User.role == User.ROLE_USER)
        
        # 活跃度筛选
        if recipient_filter.get('activity_level'):
            level = recipient_filter['activity_level']
            now = datetime.now()
            
            if level == 'high':
                # 7天内活跃
                query = query.filter(User.last_activity_at >= now - timedelta(days=7))
            elif level == 'medium':
                # 7-30天活跃
                query = query.filter(
                    and_(
                        User.last_activity_at < now - timedelta(days=7),
                        User.last_activity_at >= now - timedelta(days=30)
                    )
                )
            elif level == 'low':
                # 30-90天活跃
                query = query.filter(
                    and_(
                        User.last_activity_at < now - timedelta(days=30),
                        User.last_activity_at >= now - timedelta(days=90)
                    )
                )
            elif level == 'dormant':
                # 90-180天活跃
                query = query.filter(
                    and_(
                        User.last_activity_at < now - timedelta(days=90),
                        User.last_activity_at >= now - timedelta(days=180)
                    )
                )
            elif level == 'lost':
                # 180天以上未活跃
                query = query.filter(User.last_activity_at < now - timedelta(days=180))
        
        # 余额筛选
        if recipient_filter.get('min_balance') is not None:
            query = query.filter(User.balance >= float(recipient_filter['min_balance']))
        if recipient_filter.get('max_balance') is not None:
            query = query.filter(User.balance <= float(recipient_filter['max_balance']))
        
        # 注册时间筛选
        if recipient_filter.get('registered_after'):
            query = query.filter(User.created_at >= datetime.fromisoformat(recipient_filter['registered_after']))
        if recipient_filter.get('registered_before'):
            query = query.filter(User.created_at <= datetime.fromisoformat(recipient_filter['registered_before']))
        
        # 自定义用户ID列表
        if recipient_filter.get('user_ids'):
            user_ids = recipient_filter['user_ids']
            if isinstance(user_ids, str):
                user_ids = [int(uid.strip()) for uid in user_ids.split(',') if uid.strip()]
            query = query.filter(User.id.in_(user_ids))
        
        return query.all()
    
    @staticmethod
    def replace_variables(content, user):
        """
        替换邮件内容中的变量
        支持的变量:
        - {username}: 用户名
        - {email}: 邮箱
        - {balance}: 余额
        - {site_name}: 站点名称
        - {site_url}: 站点地址
        """
        site_name = Setting.get('site_name', '六趣DNS')
        site_url = Setting.get('site_url', 'http://localhost:5000')
        
        replacements = {
            '{username}': user.username or user.email.split('@')[0],
            '{email}': user.email,
            '{balance}': f'{user.balance:.2f}',
            '{site_name}': site_name,
            '{site_url}': site_url
        }
        
        result = content
        for key, value in replacements.items():
            result = result.replace(key, str(value))
        
        return result
    
    @staticmethod
    def send_campaign(campaign_id):
        """
        发送群发任务（异步）
        将任务提交到后台任务管理器
        """
        campaign = EmailCampaign.query.get(campaign_id)
        if not campaign:
            return False, '任务不存在'
        
        if campaign.status == EmailCampaign.STATUS_SENDING:
            return False, '任务正在发送中'
        
        if campaign.status == EmailCampaign.STATUS_COMPLETED:
            return False, '任务已完成'
        
        # 提交异步任务
        try:
            task_id = BackgroundTaskManager.submit_task(
                EmailCampaignService._send_campaign_worker,
                campaign_id
            )
            
            # 更新状态为发送中，保存 task_id
            campaign.task_id = task_id
            campaign.status = EmailCampaign.STATUS_SENDING
            campaign.started_at = datetime.now()
            db.session.commit()
            
            return True, f'任务已提交，正在后台发送中 (Task ID: {task_id})'
        except Exception as e:
            logger.error(f'提交任务失败: {e}')
            return False, f'提交任务失败: {str(e)}'
    
    @staticmethod
    def _send_campaign_worker(campaign_id):
        """
        邮件群发工作函数（在后台线程中执行）
        
        Args:
            campaign_id: 群发任务ID
            
        Returns:
            dict: 发送结果统计
        """
        # 创建新的应用上下文
        from app import create_app
        app = create_app()
        
        with app.app_context():
            try:
                campaign = EmailCampaign.query.get(campaign_id)
                if not campaign:
                    logger.error(f'Campaign {campaign_id} not found')
                    return {'success': False, 'message': '任务不存在'}
                
                # 检查状态
                if campaign.status == EmailCampaign.STATUS_COMPLETED:
                    return {'success': False, 'message': '任务已完成'}
                
                # 筛选收件人
                try:
                    recipients = EmailCampaignService.filter_recipients(campaign.recipient_filter)
                    campaign.recipient_count = len(recipients)
                    db.session.commit()
                except Exception as e:
                    logger.error(f'Filter recipients failed: {e}')
                    campaign.status = EmailCampaign.STATUS_FAILED
                    db.session.commit()
                    return {'success': False, 'message': f'筛选收件人失败: {str(e)}'}
                
                if not recipients:
                    campaign.status = EmailCampaign.STATUS_COMPLETED
                    campaign.completed_at = datetime.now()
                    db.session.commit()
                    return {'success': True, 'message': '没有符合条件的收件人', 'sent': 0, 'failed': 0}
                
                # 批量发送邮件
                success_count = 0
                failed_count = 0
                batch_size = 10  # 每批次发送数量
                
                for i, user in enumerate(recipients):
                    try:
                        # 替换变量
                        subject = EmailCampaignService.replace_variables(campaign.subject, user)
                        content = EmailCampaignService.replace_variables(campaign.content, user)
                        
                        # 发送邮件
                        success, message = EmailService.send(user.email, subject, content)
                        
                        # 记录发送日志
                        log = EmailLog(
                            campaign_id=campaign.id,
                            user_id=user.id,
                            to_email=user.email,
                            subject=subject,
                            content=content,
                            status=EmailLog.STATUS_SENT if success else EmailLog.STATUS_FAILED,
                            error_message=None if success else message,
                            sent_at=datetime.now() if success else None
                        )
                        db.session.add(log)
                        
                        if success:
                            success_count += 1
                        else:
                            failed_count += 1
                            logger.warning(f'Send to {user.email} failed: {message}')
                        
                        # 每批次提交一次，更新进度
                        if (i + 1) % batch_size == 0:
                            campaign.sent_count = success_count + failed_count
                            campaign.success_count = success_count
                            campaign.failed_count = failed_count
                            db.session.commit()
                            
                            # 更新任务进度
                            if campaign.task_id:
                                BackgroundTaskManager.update_task_progress(
                                    campaign.task_id,
                                    current=i + 1,
                                    total=len(recipients)
                                )
                    
                    except Exception as e:
                        logger.error(f'Send to {user.email} error: {e}')
                        failed_count += 1
                        
                        # 记录失败日志
                        log = EmailLog(
                            campaign_id=campaign.id,
                            user_id=user.id,
                            to_email=user.email,
                            subject=campaign.subject,
                            content=campaign.content,
                            status=EmailLog.STATUS_FAILED,
                            error_message=str(e)
                        )
                        db.session.add(log)
                
                # 最终更新任务状态
                campaign.sent_count = success_count + failed_count
                campaign.success_count = success_count
                campaign.failed_count = failed_count
                campaign.status = EmailCampaign.STATUS_COMPLETED
                campaign.completed_at = datetime.now()
                db.session.commit()
                
                result = {
                    'success': True,
                    'message': f'发送完成: 成功{success_count}封, 失败{failed_count}封',
                    'sent': success_count + failed_count,
                    'success_count': success_count,
                    'failed_count': failed_count
                }
                
                logger.info(f'Campaign {campaign_id} completed: {result}')
                return result
                
            except Exception as e:
                logger.error(f'Send campaign {campaign_id} error: {e}', exc_info=True)
                
                # 更新任务状态为失败
                try:
                    campaign = EmailCampaign.query.get(campaign_id)
                    if campaign:
                        campaign.status = EmailCampaign.STATUS_FAILED
                        db.session.commit()
                except:
                    pass
                
                return {'success': False, 'message': f'发送失败: {str(e)}'}
    
    @staticmethod
    def get_campaign_progress(campaign_id):
        """获取任务发送进度"""
        campaign = EmailCampaign.query.get(campaign_id)
        if not campaign:
            return None
        
        return {
            'id': campaign.id,
            'name': campaign.name,
            'status': campaign.status,
            'recipient_count': campaign.recipient_count or 0,
            'sent_count': campaign.sent_count or 0,
            'success_count': campaign.success_count or 0,
            'failed_count': campaign.failed_count or 0,
            'progress_percent': campaign.progress_percent
        }
