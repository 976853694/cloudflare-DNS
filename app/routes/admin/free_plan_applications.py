"""
免费套餐申请管理路由（管理员端）
"""
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import and_, or_, func

from app import db
from app.models import User, Plan, FreePlanApplication, Setting
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden
from app.utils.timezone import now as beijing_now
from app.services.email import EmailService
from app.services.email_templates import EmailTemplateService


@admin_bp.route('/free-plan-applications', methods=['GET'])
@admin_required
def get_applications():
    """获取申请列表"""
    # 获取筛选参数
    status = request.args.get('status')
    plan_id = request.args.get('plan_id', type=int)
    plan_type = request.args.get('plan_type')  # 新增：platform/host
    host_id = request.args.get('host_id', type=int)  # 新增：托管商ID
    host_review_status = request.args.get('host_review_status')  # 新增：托管商审核状态
    user_id = request.args.get('user_id', type=int)
    keyword = request.args.get('keyword', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # 构建查询
    query = FreePlanApplication.query
    
    if status:
        query = query.filter_by(status=status)
    
    if plan_id:
        query = query.filter_by(plan_id=plan_id)
    
    # 套餐类型筛选
    if plan_type:
        query = query.join(Plan)
        if plan_type == 'platform':
            query = query.filter(Plan.owner_id.is_(None))
        elif plan_type == 'host':
            query = query.filter(Plan.owner_id.isnot(None))
    
    # 托管商筛选
    if host_id:
        query = query.join(Plan).filter(Plan.owner_id == host_id)
    
    # 托管商审核状态筛选
    if host_review_status:
        if host_review_status == 'pending':
            query = query.filter(FreePlanApplication.host_review_status.is_(None))
        else:
            query = query.filter_by(host_review_status=host_review_status)
    
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    if keyword:
        # 搜索用户名或申请理由
        query = query.join(User).filter(
            or_(
                User.username.like(f'%{keyword}%'),
                FreePlanApplication.apply_reason.like(f'%{keyword}%')
            )
        )
    
    # 分页
    pagination = query.order_by(
        # 待审核的排在前面
        func.if_(FreePlanApplication.status == FreePlanApplication.STATUS_PENDING, 0, 1),
        FreePlanApplication.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    applications = [app.to_dict(include_user=True, include_plan=True) for app in pagination.items]
    
    # 统计数据
    stats = {
        'total': FreePlanApplication.query.count(),
        'pending': FreePlanApplication.query.filter_by(status=FreePlanApplication.STATUS_PENDING).count(),
        'approved': FreePlanApplication.query.filter_by(status=FreePlanApplication.STATUS_APPROVED).count(),
        'rejected': FreePlanApplication.query.filter_by(status=FreePlanApplication.STATUS_REJECTED).count(),
        'used': FreePlanApplication.query.filter_by(status=FreePlanApplication.STATUS_USED).count(),
        # 新增：托管商审核统计
        'host_pending': FreePlanApplication.query.join(Plan).filter(
            Plan.owner_id.isnot(None),
            FreePlanApplication.host_review_status.is_(None),
            FreePlanApplication.status == FreePlanApplication.STATUS_PENDING
        ).count(),
        'host_approved': FreePlanApplication.query.filter(
            FreePlanApplication.host_review_status == 'approved'
        ).count(),
        'host_rejected': FreePlanApplication.query.filter(
            FreePlanApplication.host_review_status == 'rejected'
        ).count()
    }
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'applications': applications,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages,
            'stats': stats
        }
    })


@admin_bp.route('/free-plan-applications/<int:app_id>', methods=['GET'])
@admin_required
def get_application_detail(app_id):
    """获取申请详情"""
    application = FreePlanApplication.query.get(app_id)
    
    if not application:
        return jsonify({'code': 404, 'message': '申请不存在'}), 404
    
    # 获取用户的历史申请记录
    user_applications = FreePlanApplication.query.filter_by(
        user_id=application.user_id
    ).order_by(FreePlanApplication.created_at.desc()).limit(10).all()
    
    # 获取用户的域名数量
    user = application.user
    subdomain_count = user.subdomains.count() if user else 0
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'application': application.to_dict(include_user=True, include_plan=True),
            'user_history': [app.to_dict(include_plan=True) for app in user_applications],
            'user_subdomain_count': subdomain_count
        }
    })


@admin_bp.route('/free-plan-applications/<int:app_id>/approve', methods=['POST'])
@admin_required
@demo_forbidden
def approve_application(app_id):
    """通过申请"""
    admin_id = int(get_jwt_identity())
    
    application = FreePlanApplication.query.get(app_id)
    
    if not application:
        return jsonify({'code': 404, 'message': '申请不存在'}), 404
    
    if not application.is_pending:
        return jsonify({'code': 400, 'message': '该申请已被处理'}), 400
    
    # 检查管理员是否已审核
    if application.is_admin_reviewed:
        return jsonify({'code': 400, 'message': '您已审核过此申请'}), 400
    
    data = request.get_json() or {}
    admin_note = data.get('admin_note', '').strip()
    auto_create = data.get('auto_create', True)  # 默认自动开通
    
    try:
        # 更新管理员审核记录
        application.reviewed_by = admin_id
        application.reviewed_at = beijing_now()
        if admin_note:
            application.admin_note = admin_note
        
        # 更新申请状态为已通过
        application.status = FreePlanApplication.STATUS_APPROVED
        
        db.session.commit()
        
        # 立即尝试自动开通
        from app.services.free_plan_provision_service import FreePlanProvisionService
        provision_success, provision_message, provision_data = FreePlanProvisionService.auto_provision(
            app_id, auto_create=auto_create
        )
        
        # 发送邮件通知给用户（同步发送，与注册邮件保持一致）
        try:
            user = application.user
            if user and user.email:
                site_url = request.host_url.rstrip('/')
                
                if provision_success and provision_data.get('auto_created'):
                    # 自动开通成功
                    subdomain = provision_data.get('subdomain', {})
                    subject, html = EmailTemplateService.render_email('free_plan_auto_provisioned', {
                        'username': user.username,
                        'subdomain_name': subdomain.get('full_name', ''),
                        'plan_name': application.plan.name,
                        'dns_url': f"{site_url}/user/domains",
                        'domain_url': f"{site_url}/user/domains"
                    })
                else:
                    # 未自动开通或自动开通失败
                    # 构建管理员备注HTML
                    admin_note_html = ''
                    if admin_note:
                        admin_note_html = f'''<tr><td style="padding:10px 20px;">
<span style="color:#999;">管理员备注：</span>
<p style="color:#333;margin:10px 0 0 0;white-space:pre-wrap;">{admin_note}</p>
</td></tr>'''
                    
                    # 构建开通失败提示HTML
                    provision_error_html = ''
                    if not provision_success:
                        error_msg = provision_data.get('error', provision_message)
                        provision_error_html = f'''<tr><td style="padding:10px 20px;background:#FEF3C7;border-left:4px solid #F59E0B;">
<span style="color:#92400E;font-weight:bold;">⚠️ 自动开通失败</span>
<p style="color:#92400E;margin:10px 0 0 0;font-size:13px;">{error_msg}</p>
<p style="color:#92400E;margin:10px 0 0 0;font-size:13px;">请手动创建域名。</p>
</td></tr>'''
                    
                    subject, html = EmailTemplateService.render_email('free_plan_approved', {
                        'username': user.username,
                        'plan_name': application.plan.name,
                        'domain_url': f"{site_url}/user/domain/new",
                        'admin_note_html': admin_note_html,
                        'provision_error_html': provision_error_html
                    })
                
                if subject and html:
                    print(f"[INFO] 准备发送邮件到: {user.email}, 主题: {subject}")
                    success, msg = EmailService.send(user.email, subject, html)
                    if success:
                        print(f"[INFO] 邮件发送成功")
                    else:
                        print(f"[ERROR] 邮件发送失败: {msg}")
                else:
                    print(f"[ERROR] 邮件模板渲染失败")
            else:
                print(f"[WARN] 用户邮箱不存在或为空: user_id={application.user_id}")
        except Exception as e:
            # 邮件发送失败不影响审核操作
            import traceback
            print(f"[ERROR] Failed to send approval notification email: {e}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
        
        # 如果是托管商套餐，通知托管商（备案性质）
        try:
            plan = application.plan
            if plan and plan.is_host_owned and plan.owner and plan.owner.email:
                host_email = plan.owner.email
                site_url = request.host_url.rstrip('/')
                
                if provision_success and provision_data.get('auto_created'):
                    # 自动开通成功
                    subdomain = provision_data.get('subdomain', {})
                    subject = f"【管理员审核】免费套餐已自动开通 - {user.username}"
                    html = f"""
                    <h2 style="color:#10B981;">管理员已审核通过并自动开通</h2>
                    <p><strong>申请用户：</strong>{user.username}</p>
                    <p><strong>套餐名称：</strong>{plan.name}</p>
                    <p><strong>开通域名：</strong>{subdomain.get('full_name', '未知')}</p>
                    <p style="margin:20px 0;"><a href="{site_url}/host/free-plan-applications/{application.id}" style="display:inline-block;padding:12px 40px;background:#10B981;color:#fff;text-decoration:none;border-radius:6px;">查看详情</a></p>
                    <p style="color:#999;font-size:12px;">此邮件为备案通知，无需处理。</p>
                    """
                else:
                    # 未自动开通或自动开通失败
                    subject = f"【管理员审核】免费套餐申请已通过 - {user.username}"
                    error_info = ''
                    if not provision_success:
                        error_info = f"<p style='color:#F59E0B;'><strong>⚠️ 自动开通失败：</strong>{provision_message}</p>"
                    html = f"""
                    <h2 style="color:#10B981;">管理员已审核通过</h2>
                    <p><strong>申请用户：</strong>{user.username}</p>
                    <p><strong>套餐名称：</strong>{plan.name}</p>
                    {error_info}
                    <p style="margin:20px 0;"><a href="{site_url}/host/free-plan-applications/{application.id}" style="display:inline-block;padding:12px 40px;background:#10B981;color:#fff;text-decoration:none;border-radius:6px;">查看详情</a></p>
                    <p style="color:#999;font-size:12px;">此邮件为备案通知，无需处理。</p>
                    """
                
                EmailService.send(host_email, subject, html)
                print(f"[INFO] 已发送备案邮件给托管商: {host_email}")
        except Exception as e:
            print(f"[ERROR] 发送托管商备案邮件失败: {e}")
        
        # 准备返回数据
        response_data = {
            'application': application.to_dict(include_user=True, include_plan=True),
            'auto_provision': {
                'attempted': auto_create,
                'success': provision_success,
                'message': provision_message,
                'data': provision_data
            }
        }
        
        return jsonify({
            'code': 200,
            'message': '申请已通过' + (f'，{provision_message}' if auto_create else ''),
            'data': response_data
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'message': f'操作失败: {str(e)}'}), 500


@admin_bp.route('/free-plan-applications/<int:app_id>/reject', methods=['POST'])
@admin_required
@demo_forbidden
def reject_application(app_id):
    """拒绝申请"""
    admin_id = int(get_jwt_identity())
    
    application = FreePlanApplication.query.get(app_id)
    
    if not application:
        return jsonify({'code': 404, 'message': '申请不存在'}), 404
    
    if not application.is_pending:
        return jsonify({'code': 400, 'message': '该申请已被处理'}), 400
    
    # 检查管理员是否已审核
    if application.is_admin_reviewed:
        return jsonify({'code': 400, 'message': '您已审核过此申请'}), 400
    
    data = request.get_json()
    rejection_reason = data.get('rejection_reason', '').strip()
    admin_note = data.get('admin_note', '').strip()
    
    if not rejection_reason:
        return jsonify({'code': 400, 'message': '请填写拒绝原因'}), 400
    
    try:
        application.status = FreePlanApplication.STATUS_REJECTED
        application.rejection_reason = rejection_reason
        application.reviewed_by = admin_id
        application.reviewed_at = beijing_now()
        if admin_note:
            application.admin_note = admin_note
        
        db.session.commit()
        
        # 发送邮件通知给用户（同步发送，与注册邮件保持一致）
        try:
            user = application.user
            if user and user.email:
                site_url = request.host_url.rstrip('/')
                subject, html = EmailTemplateService.render_email('free_plan_rejected', {
                    'username': user.username,
                    'plan_name': application.plan.name,
                    'rejection_reason': rejection_reason,
                    'applications_url': f"{site_url}/user/free-plan-applications"
                })
                if subject and html:
                    print(f"[INFO] 准备发送拒绝邮件到: {user.email}, 主题: {subject}")
                    success, msg = EmailService.send(user.email, subject, html)
                    if success:
                        print(f"[INFO] 邮件发送成功")
                    else:
                        print(f"[ERROR] 邮件发送失败: {msg}")
                else:
                    print(f"[ERROR] 邮件模板渲染失败")
            else:
                print(f"[WARN] 用户邮箱不存在或为空: user_id={application.user_id}")
        except Exception as e:
            # 邮件发送失败不影响审核操作
            import traceback
            print(f"[ERROR] Failed to send rejection notification email: {e}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
        
        # 如果是托管商套餐，通知托管商（备案性质）
        try:
            plan = application.plan
            if plan and plan.is_host_owned and plan.owner and plan.owner.email:
                host_email = plan.owner.email
                site_url = request.host_url.rstrip('/')
                subject = f"【管理员审核】免费套餐申请已被拒绝 - {user.username}"
                html = f"""
                <h2 style="color:#EF4444;">管理员已拒绝申请</h2>
                <p><strong>申请用户：</strong>{user.username}</p>
                <p><strong>套餐名称：</strong>{plan.name}</p>
                <p><strong>拒绝原因：</strong>{rejection_reason}</p>
                <p style="margin:20px 0;"><a href="{site_url}/host/free-plan-applications/{application.id}" style="display:inline-block;padding:12px 40px;background:#4F46E5;color:#fff;text-decoration:none;border-radius:6px;">查看详情</a></p>
                <p style="color:#999;font-size:12px;">此邮件为备案通知，无需处理。</p>
                """
                EmailService.send(host_email, subject, html)
                print(f"[INFO] 已发送拒绝备案邮件给托管商: {host_email}")
        except Exception as e:
            print(f"[ERROR] 发送托管商备案邮件失败: {e}")
        
        return jsonify({
            'code': 200,
            'message': '申请已拒绝',
            'data': {'application': application.to_dict(include_user=True, include_plan=True)}
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'message': f'操作失败: {str(e)}'}), 500


@admin_bp.route('/free-plan-applications/stats', methods=['GET'])
@admin_required
def get_application_stats():
    """获取申请统计数据"""
    from datetime import timedelta
    from sqlalchemy import func, extract
    
    now = beijing_now()
    today = now.date()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # 基础统计
    total = FreePlanApplication.query.count()
    pending = FreePlanApplication.query.filter_by(status=FreePlanApplication.STATUS_PENDING).count()
    approved = FreePlanApplication.query.filter_by(status=FreePlanApplication.STATUS_APPROVED).count()
    rejected = FreePlanApplication.query.filter_by(status=FreePlanApplication.STATUS_REJECTED).count()
    used = FreePlanApplication.query.filter_by(status=FreePlanApplication.STATUS_USED).count()
    
    # 今日申请
    today_count = FreePlanApplication.query.filter(
        func.date(FreePlanApplication.created_at) == today
    ).count()
    
    # 本周申请
    week_count = FreePlanApplication.query.filter(
        FreePlanApplication.created_at >= week_ago
    ).count()
    
    # 本月申请
    month_count = FreePlanApplication.query.filter(
        FreePlanApplication.created_at >= month_ago
    ).count()
    
    # 通过率
    approval_rate = round((approved / total * 100), 2) if total > 0 else 0
    
    # 各套餐申请数量
    plan_stats = db.session.query(
        Plan.id,
        Plan.name,
        func.count(FreePlanApplication.id).label('count')
    ).join(
        FreePlanApplication, FreePlanApplication.plan_id == Plan.id
    ).group_by(Plan.id, Plan.name).order_by(func.count(FreePlanApplication.id).desc()).limit(10).all()
    
    plan_stats_data = [
        {'plan_id': stat[0], 'plan_name': stat[1], 'count': stat[2]}
        for stat in plan_stats
    ]
    
    # 最近7天每日申请趋势
    daily_stats = db.session.query(
        func.date(FreePlanApplication.created_at).label('date'),
        func.count(FreePlanApplication.id).label('count')
    ).filter(
        FreePlanApplication.created_at >= week_ago
    ).group_by(func.date(FreePlanApplication.created_at)).all()
    
    daily_stats_data = [
        {'date': stat[0].isoformat(), 'count': stat[1]}
        for stat in daily_stats
    ]
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'total': total,
            'pending': pending,
            'approved': approved,
            'rejected': rejected,
            'used': used,
            'today_count': today_count,
            'week_count': week_count,
            'month_count': month_count,
            'approval_rate': approval_rate,
            'plan_stats': plan_stats_data,
            'daily_stats': daily_stats_data
        }
    })
