"""
托管商免费套餐审核服务
处理托管商对免费套餐申请的审核逻辑
"""
from app import db
from app.models import FreePlanApplication, User, Plan, Setting
from app.services.free_plan_provision_service import FreePlanProvisionService
from app.services.email import EmailService
from app.services.email_templates import EmailTemplateService
from app.utils.timezone import now as beijing_now
from app.utils.logger import get_logger

logger = get_logger(__name__)


class HostFreePlanService:
    """托管商免费套餐审核服务"""
    
    @staticmethod
    def _get_site_url():
        """获取站点URL"""
        try:
            from flask import request
            if request:
                return request.host_url.rstrip('/')
        except:
            pass
        return Setting.get('site_url', 'http://localhost:5000')
    
    @staticmethod
    def review_application(application_id: int, host_id: int, action: str, 
                          reason: str = None, note: str = None) -> tuple:
        """
        托管商审核免费套餐申请
        
        Args:
            application_id: 申请ID
            host_id: 托管商用户ID
            action: 审核动作 'approve' 或 'reject'
            reason: 拒绝原因（拒绝时必填）
            note: 备注
            
        Returns:
            tuple: (success: bool, message: str, data: dict)
        """
        application = FreePlanApplication.query.get(application_id)
        
        if not application:
            return False, '申请不存在', {}
        
        plan = application.plan
        if not plan:
            return False, '套餐不存在', {}
        
        # 权限检查：只能审核自己的套餐
        if not plan.is_host_owned or plan.owner_id != host_id:
            return False, '无权审核此申请', {}
        
        # 状态检查
        if application.status != FreePlanApplication.STATUS_PENDING:
            return False, '申请已被处理', {}
        
        if application.is_host_reviewed:
            return False, '您已审核过此申请', {}
        
        # 更新托管商审核状态
        application.host_review_status = 'approved' if action == 'approve' else 'rejected'
        application.host_reviewed_by = host_id
        application.host_reviewed_at = beijing_now()
        
        if action == 'reject':
            # 拒绝：直接设置申请为拒绝状态
            if not reason:
                return False, '请填写拒绝原因', {}
            
            application.status = FreePlanApplication.STATUS_REJECTED
            application.host_rejection_reason = reason
            if note:
                application.host_admin_note = note
            
            try:
                db.session.commit()
                logger.info(f"托管商 {host_id} 拒绝免费套餐申请 {application_id}")
                
                # 发送邮件通知给用户
                try:
                    if application.user and application.user.email:
                        subject, html = EmailTemplateService.render_email('free_plan_rejected', {
                            'username': application.user.username,
                            'plan_name': plan.name,
                            'rejection_reason': reason,
                            'applications_url': f"{HostFreePlanService._get_site_url()}/user/free-plan-applications"
                        })
                        if subject and html:
                            EmailService.send(application.user.email, subject, html)
                            logger.info(f"已发送拒绝通知邮件给用户: {application.user.email}")
                except Exception as e:
                    logger.error(f"发送拒绝通知邮件失败: {e}")
                
                # 发送邮件通知给管理员（备案）
                try:
                    admin_email = Setting.get('admin_email', '')
                    if admin_email:
                        subject = f"【托管商审核】免费套餐申请已被拒绝 - {application.user.username}"
                        html = f"""
                        <h2>托管商已拒绝免费套餐申请</h2>
                        <p><strong>托管商：</strong>{plan.owner.username if plan.owner else '未知'}</p>
                        <p><strong>申请用户：</strong>{application.user.username}</p>
                        <p><strong>套餐名称：</strong>{plan.name}</p>
                        <p><strong>拒绝原因：</strong>{reason}</p>
                        <p style="margin:20px 0;"><a href="{HostFreePlanService._get_site_url()}/admin/free-plan-applications/{application.id}" style="display:inline-block;padding:12px 40px;background:#4F46E5;color:#fff;text-decoration:none;border-radius:6px;">查看详情</a></p>
                        """
                        EmailService.send(admin_email, subject, html)
                        logger.info(f"已发送拒绝备案邮件给管理员: {admin_email}")
                except Exception as e:
                    logger.error(f"发送管理员备案邮件失败: {e}")
                
                return True, '已拒绝申请', {'status': 'rejected'}
            except Exception as e:
                db.session.rollback()
                logger.error(f"托管商拒绝申请失败: {str(e)}", exc_info=True)
                return False, '系统错误', {}
        
        else:
            # 通过：立即自动开通
            application.status = FreePlanApplication.STATUS_APPROVED
            if note:
                application.host_admin_note = note
            
            try:
                db.session.commit()
                
                # 自动开通
                success, message, data = FreePlanProvisionService.auto_provision(
                    application.id, 
                    auto_create=True
                )
                
                if success:
                    logger.info(f"托管商 {host_id} 通过免费套餐申请 {application_id}，已自动开通")
                    
                    # 发送邮件通知给用户
                    try:
                        if application.user and application.user.email:
                            subdomain_info = data.get('subdomain', {})
                            subject, html = EmailTemplateService.render_email('free_plan_auto_provisioned', {
                                'username': application.user.username,
                                'subdomain_name': subdomain_info.get('full_name', ''),
                                'plan_name': plan.name,
                                'dns_url': f"{HostFreePlanService._get_site_url()}/user/domains/{subdomain_info.get('id', '')}/records" if subdomain_info.get('id') else '',
                                'domain_url': f"{HostFreePlanService._get_site_url()}/user/domains"
                            })
                            if subject and html:
                                EmailService.send(application.user.email, subject, html)
                                logger.info(f"已发送开通成功邮件给用户: {application.user.email}")
                    except Exception as e:
                        logger.error(f"发送开通成功邮件失败: {e}")
                    
                    # 发送邮件通知给管理员（备案）
                    try:
                        admin_email = Setting.get('admin_email', '')
                        if admin_email:
                            subdomain_info = data.get('subdomain', {})
                            subject = f"【托管商审核】免费套餐已自动开通 - {application.user.username}"
                            html = f"""
                            <h2 style="color:#10B981;">托管商已审核通过并自动开通</h2>
                            <p><strong>托管商：</strong>{plan.owner.username if plan.owner else '未知'}</p>
                            <p><strong>申请用户：</strong>{application.user.username}</p>
                            <p><strong>套餐名称：</strong>{plan.name}</p>
                            <p><strong>开通域名：</strong>{subdomain_info.get('full_name', '未知')}</p>
                            <p style="margin:20px 0;"><a href="{HostFreePlanService._get_site_url()}/admin/free-plan-applications/{application.id}" style="display:inline-block;padding:12px 40px;background:#10B981;color:#fff;text-decoration:none;border-radius:6px;">查看详情</a></p>
                            <p style="color:#999;font-size:12px;">此邮件为备案通知，无需处理。</p>
                            """
                            EmailService.send(admin_email, subject, html)
                            logger.info(f"已发送开通备案邮件给管理员: {admin_email}")
                    except Exception as e:
                        logger.error(f"发送管理员备案邮件失败: {e}")
                    
                    return True, '审核通过，域名已自动开通', {
                        'status': 'used',
                        'auto_created': True,
                        'subdomain': data.get('subdomain')
                    }
                else:
                    logger.error(f"托管商通过申请但自动开通失败: {message}")
                    
                    # 发送邮件通知给用户
                    try:
                        if application.user and application.user.email:
                            subject, html = EmailTemplateService.render_email('free_plan_approved', {
                                'username': application.user.username,
                                'plan_name': plan.name,
                                'domain_url': f"{HostFreePlanService._get_site_url()}/user/domains",
                                'admin_note_html': '',
                                'provision_error_html': f'<tr><td style="padding:10px 20px;"><span style="color:#EF4444;">⚠️ 自动开通失败：{message}</span><br><span style="color:#666;font-size:12px;">请手动创建域名或联系管理员</span></td></tr>'
                            })
                            if subject and html:
                                EmailService.send(application.user.email, subject, html)
                                logger.info(f"已发送审核通过邮件给用户: {application.user.email}")
                    except Exception as e:
                        logger.error(f"发送审核通过邮件失败: {e}")
                    
                    # 通知管理员处理
                    try:
                        admin_email = Setting.get('admin_email', '')
                        if admin_email:
                            subject = f"【需要处理】托管商审核通过但自动开通失败 - {application.user.username}"
                            html = f"""
                            <h2 style="color:#F59E0B;">⚠️ 需要处理：自动开通失败</h2>
                            <p><strong>托管商：</strong>{plan.owner.username if plan.owner else '未知'}</p>
                            <p><strong>申请用户：</strong>{application.user.username}</p>
                            <p><strong>套餐名称：</strong>{plan.name}</p>
                            <p><strong>失败原因：</strong>{message}</p>
                            <p style="margin:20px 0;"><a href="{HostFreePlanService._get_site_url()}/admin/free-plan-applications/{application.id}" style="display:inline-block;padding:12px 40px;background:#F59E0B;color:#fff;text-decoration:none;border-radius:6px;">立即处理</a></p>
                            <p style="color:#666;">请手动为用户创建域名或检查系统配置。</p>
                            """
                            EmailService.send(admin_email, subject, html)
                            logger.info(f"已发送处理通知邮件给管理员: {admin_email}")
                    except Exception as e:
                        logger.error(f"发送管理员处理通知邮件失败: {e}")
                    
                    return True, f'审核通过，但自动开通失败: {message}', {
                        'status': 'approved',
                        'auto_created': False,
                        'error': message
                    }
            
            except Exception as e:
                db.session.rollback()
                logger.error(f"托管商审核申请失败: {str(e)}", exc_info=True)
                return False, '系统错误', {}
    
    @staticmethod
    def get_applications(host_id: int, status: str = 'all', page: int = 1, per_page: int = 20) -> dict:
        """
        获取托管商的免费套餐申请列表
        
        Args:
            host_id: 托管商用户ID
            status: 筛选状态 'all'/'pending'/'approved'/'rejected'
            page: 页码
            per_page: 每页数量
            
        Returns:
            dict: 包含申请列表和分页信息
        """
        # 获取托管商的所有套餐ID
        plan_ids = [p.id for p in Plan.query.filter_by(owner_id=host_id).all()]
        
        if not plan_ids:
            return {
                'applications': [],
                'total': 0,
                'page': page,
                'per_page': per_page,
                'pages': 0
            }
        
        # 构建查询
        query = FreePlanApplication.query.filter(
            FreePlanApplication.plan_id.in_(plan_ids)
        )
        
        # 状态筛选
        if status == 'pending':
            # 待我审核：申请状态为pending且我未审核
            query = query.filter(
                FreePlanApplication.status == FreePlanApplication.STATUS_PENDING,
                FreePlanApplication.host_review_status.is_(None)
            )
        elif status == 'approved':
            # 我已通过
            query = query.filter(
                FreePlanApplication.host_review_status == 'approved'
            )
        elif status == 'rejected':
            # 我已拒绝
            query = query.filter(
                FreePlanApplication.host_review_status == 'rejected'
            )
        
        # 排序：待审核的在前，然后按创建时间倒序
        query = query.order_by(
            FreePlanApplication.host_review_status.is_(None).desc(),
            FreePlanApplication.created_at.desc()
        )
        
        # 分页
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        applications = [app.to_dict(include_user=True, include_plan=True) 
                       for app in pagination.items]
        
        return {
            'applications': applications,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    
    @staticmethod
    def get_statistics(host_id: int) -> dict:
        """
        获取托管商的免费套餐申请统计
        
        Args:
            host_id: 托管商用户ID
            
        Returns:
            dict: 统计数据
        """
        # 获取托管商的所有套餐ID
        plan_ids = [p.id for p in Plan.query.filter_by(owner_id=host_id).all()]
        
        if not plan_ids:
            return {
                'total': 0,
                'pending': 0,
                'approved': 0,
                'rejected': 0,
                'used': 0
            }
        
        # 统计各状态数量
        base_query = FreePlanApplication.query.filter(
            FreePlanApplication.plan_id.in_(plan_ids)
        )
        
        total = base_query.count()
        
        # 待我审核
        pending = base_query.filter(
            FreePlanApplication.status == FreePlanApplication.STATUS_PENDING,
            FreePlanApplication.host_review_status.is_(None)
        ).count()
        
        # 我已通过
        approved = base_query.filter(
            FreePlanApplication.host_review_status == 'approved'
        ).count()
        
        # 我已拒绝
        rejected = base_query.filter(
            FreePlanApplication.host_review_status == 'rejected'
        ).count()
        
        # 已开通
        used = base_query.filter(
            FreePlanApplication.status == FreePlanApplication.STATUS_USED
        ).count()
        
        return {
            'total': total,
            'pending': pending,
            'approved': approved,
            'rejected': rejected,
            'used': used
        }
