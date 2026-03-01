"""
免费套餐申请路由（用户端）
"""
import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import and_, or_
from datetime import datetime, timedelta

from app import db
from app.models import User, Plan, Domain, FreePlanApplication, Setting
from app.utils.timezone import now as beijing_now
from app.routes.decorators import phone_binding_required
from app.services.email import EmailService
from app.services.email_templates import EmailTemplateService

free_plan_app_bp = Blueprint('free_plan_application', __name__)


@free_plan_app_bp.route('/free-plan-applications', methods=['POST'])
@jwt_required()
@phone_binding_required
def submit_application():
    """提交免费套餐申请"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or not user.is_active:
        return jsonify({'code': 403, 'message': '用户不可用'}), 403
    
    data = request.get_json()
    plan_id = data.get('plan_id')
    domain_id = data.get('domain_id')
    subdomain_name = data.get('subdomain_name', '').strip().lower()
    apply_reason = data.get('apply_reason', '').strip()
    
    # 验证必填字段
    if not plan_id:
        return jsonify({'code': 400, 'message': '请选择套餐'}), 400
    
    if not subdomain_name:
        return jsonify({'code': 400, 'message': '请填写域名前缀'}), 400
    
    if not apply_reason:
        return jsonify({'code': 400, 'message': '请填写申请理由'}), 400
    
    # 验证申请理由长度
    min_reason_length = int(Setting.get('free_plan_min_reason_length', 50))
    if len(apply_reason) < min_reason_length:
        return jsonify({'code': 400, 'message': f'申请理由至少需要{min_reason_length}个字符'}), 400
    
    if len(apply_reason) > 500:
        return jsonify({'code': 400, 'message': '申请理由不能超过500个字符'}), 400
    
    # 验证套餐
    plan = Plan.query.get(plan_id)
    if not plan or not plan.is_active:
        return jsonify({'code': 404, 'message': '套餐不存在或已下架'}), 404
    
    if not plan.is_free:
        return jsonify({'code': 400, 'message': '该套餐不是免费套餐'}), 400
    
    # 验证域名（如果提供）
    domain = None
    if domain_id:
        domain = Domain.query.get(domain_id)
        if not domain:
            return jsonify({'code': 404, 'message': '域名不存在'}), 404
        
        # 检查域名是否在套餐关联的域名列表中
        if domain not in plan.domains:
            return jsonify({'code': 400, 'message': '该域名不在套餐支持的域名列表中'}), 400
    
    # 检查是否已有待审核的申请
    existing_pending = FreePlanApplication.query.filter_by(
        user_id=user_id,
        plan_id=plan_id,
        status=FreePlanApplication.STATUS_PENDING
    ).first()
    
    if existing_pending:
        return jsonify({
            'code': 400, 
            'message': '您已有一个待审核的申请，请等待审核结果'
        }), 400
    
    # 检查是否已有通过的申请（阻止同时有多个有效申请）
    existing_approved = FreePlanApplication.query.filter_by(
        user_id=user_id,
        plan_id=plan_id,
        status=FreePlanApplication.STATUS_APPROVED
    ).first()
    
    if existing_approved:
        return jsonify({
            'code': 400, 
            'message': '您已有一个通过的申请待使用，请先使用后再申请'
        }), 400
    
    # 检查购买次数限制（只统计 used 状态）
    if plan.max_purchase_count > 0:
        used_count = FreePlanApplication.query.filter_by(
            user_id=user_id,
            plan_id=plan_id,
            status=FreePlanApplication.STATUS_USED
        ).count()
        
        if used_count >= plan.max_purchase_count:
            return jsonify({
                'code': 400, 
                'message': f'该套餐您已使用 {used_count} 次，已达到上限（最多 {plan.max_purchase_count} 次）'
            }), 400
    
    # 检查最近是否被拒绝（7天内被拒绝不能重新申请）
    seven_days_ago = beijing_now() - timedelta(days=7)
    recent_rejected = FreePlanApplication.query.filter(
        and_(
            FreePlanApplication.user_id == user_id,
            FreePlanApplication.plan_id == plan_id,
            FreePlanApplication.status == FreePlanApplication.STATUS_REJECTED,
            FreePlanApplication.reviewed_at >= seven_days_ago
        )
    ).first()
    
    if recent_rejected:
        return jsonify({
            'code': 400, 
            'message': '您的申请在7天内被拒绝，请等待后再次申请'
        }), 400
    
    # 获取IP地址
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip_address and ',' in ip_address:
        ip_address = ip_address.split(',')[0].strip()
    
    # 创建用户信息快照
    user_snapshot = {
        'username': user.username,
        'email': user.email,
        'phone': user.phone,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'subdomain_count': user.subdomains.count(),
        'balance': float(user.balance)
    }
    
    try:
        # 创建申请记录
        application = FreePlanApplication(
            user_id=user_id,
            plan_id=plan_id,
            domain_id=domain_id,
            subdomain_name=subdomain_name if subdomain_name else None,
            apply_reason=apply_reason,
            ip_address=ip_address,
            user_info_snapshot=json.dumps(user_snapshot, ensure_ascii=False)
        )
        
        db.session.add(application)
        db.session.commit()
        
        # 发送邮件通知给管理员（同步发送，与注册邮件保持一致）
        try:
            admin_email = Setting.get('admin_email', '')
            if admin_email:
                site_url = request.host_url.rstrip('/')
                subject, html = EmailTemplateService.render_email('free_plan_submitted', {
                    'username': user.username,
                    'plan_name': plan.name,
                    'apply_reason': apply_reason,
                    'admin_url': f"{site_url}/admin/free-plan-applications"
                })
                if subject and html:
                    print(f"[INFO] 准备发送申请通知邮件到管理员: {admin_email}, 主题: {subject}")
                    success, msg = EmailService.send(admin_email, subject, html)
                    if success:
                        print(f"[INFO] 邮件发送成功")
                    else:
                        print(f"[ERROR] 邮件发送失败: {msg}")
                else:
                    print(f"[ERROR] 邮件模板渲染失败")
            else:
                print(f"[WARN] 管理员邮箱未配置，无法发送通知邮件")
        except Exception as e:
            # 邮件发送失败不影响申请提交
            import traceback
            print(f"[ERROR] Failed to send application notification email: {e}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
        
        # 如果是托管商套餐，同时发送邮件通知给托管商
        try:
            if plan.is_host_owned and plan.owner and plan.owner.email:
                host_email = plan.owner.email
                site_url = request.host_url.rstrip('/')
                subject, html = EmailTemplateService.render_email('free_plan_submitted', {
                    'username': user.username,
                    'plan_name': plan.name,
                    'apply_reason': apply_reason,
                    'admin_url': f"{site_url}/host/free-plan-applications"
                })
                if subject and html:
                    print(f"[INFO] 准备发送申请通知邮件到托管商: {host_email}, 主题: {subject}")
                    success, msg = EmailService.send(host_email, subject, html)
                    if success:
                        print(f"[INFO] 托管商邮件发送成功")
                    else:
                        print(f"[ERROR] 托管商邮件发送失败: {msg}")
                else:
                    print(f"[ERROR] 托管商邮件模板渲染失败")
            elif plan.is_host_owned:
                print(f"[WARN] 托管商套餐但托管商邮箱未配置，无法发送通知邮件")
        except Exception as e:
            # 邮件发送失败不影响申请提交
            import traceback
            print(f"[ERROR] Failed to send host notification email: {e}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
        
        return jsonify({
            'code': 201,
            'message': '申请提交成功，请等待审核',
            'data': {'application': application.to_dict()}
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'message': f'提交失败: {str(e)}'}), 500


@free_plan_app_bp.route('/free-plan-applications', methods=['GET'])
@jwt_required()
def get_my_applications():
    """获取我的申请列表"""
    user_id = int(get_jwt_identity())
    
    # 获取筛选参数
    status = request.args.get('status')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # 构建查询
    query = FreePlanApplication.query.filter_by(user_id=user_id)
    
    if status:
        query = query.filter_by(status=status)
    
    # 分页
    pagination = query.order_by(FreePlanApplication.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    applications = [app.to_dict(include_plan=True) for app in pagination.items]
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'applications': applications,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    })


@free_plan_app_bp.route('/free-plan-applications/<int:app_id>', methods=['GET'])
@jwt_required()
def get_application_detail(app_id):
    """获取申请详情"""
    user_id = int(get_jwt_identity())
    
    application = FreePlanApplication.query.get(app_id)
    
    if not application:
        return jsonify({'code': 404, 'message': '申请不存在'}), 404
    
    if application.user_id != user_id:
        return jsonify({'code': 403, 'message': '无权查看此申请'}), 403
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {'application': application.to_dict(include_plan=True, include_user=True)}
    })


@free_plan_app_bp.route('/free-plan-applications/<int:app_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_application(app_id):
    """取消申请"""
    user_id = int(get_jwt_identity())
    
    application = FreePlanApplication.query.get(app_id)
    
    if not application:
        return jsonify({'code': 404, 'message': '申请不存在'}), 404
    
    if application.user_id != user_id:
        return jsonify({'code': 403, 'message': '无权操作此申请'}), 403
    
    if not application.can_cancel:
        return jsonify({'code': 400, 'message': '该申请无法取消'}), 400
    
    try:
        application.status = FreePlanApplication.STATUS_CANCELLED
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'message': '申请已取消',
            'data': {'application': application.to_dict()}
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'message': f'取消失败: {str(e)}'}), 500


@free_plan_app_bp.route('/free-plans', methods=['GET'])
def get_free_plans():
    """获取所有免费套餐列表（公开接口）"""
    # 获取所有启用的免费套餐
    plans = Plan.query.filter_by(is_free=True, status=1).order_by(Plan.sort_order, Plan.id).all()
    
    # 获取免费套餐相关配置
    min_reason_length = int(Setting.get('free_plan_min_reason_length', 50))
    max_reason_length = 500  # 固定最大长度
    
    # 如果用户已登录，附加申请状态
    user_id = None
    try:
        from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if user_id:
            user_id = int(user_id)
    except:
        pass
    
    plans_data = []
    for plan in plans:
        plan_dict = plan.to_dict()
        
        # 如果用户已登录，查询申请状态
        if user_id:
            # 统计已使用的次数（只统计 used 状态）
            used_count = FreePlanApplication.query.filter_by(
                user_id=user_id,
                plan_id=plan.id,
                status=FreePlanApplication.STATUS_USED
            ).count()
            
            # 查询最近的申请状态
            latest_app = FreePlanApplication.query.filter_by(
                user_id=user_id,
                plan_id=plan.id
            ).filter(
                FreePlanApplication.status.in_(['pending', 'approved', 'rejected', 'used'])
            ).order_by(FreePlanApplication.created_at.desc()).first()
            
            # 判断是否可以申请
            can_apply = True
            application_status = None
            application_id = None
            
            if latest_app:
                application_status = latest_app.status
                application_id = latest_app.id
                
                # 有待审核的申请，不能再次申请
                if latest_app.status == 'pending':
                    can_apply = False
                # 有已通过的申请，不能再次申请
                elif latest_app.status == 'approved':
                    can_apply = False
            
            # 检查是否达到购买次数上限
            if plan.max_purchase_count > 0 and used_count >= plan.max_purchase_count:
                can_apply = False
            
            # 计算剩余次数
            remaining_count = None
            if plan.max_purchase_count > 0:
                remaining_count = max(0, plan.max_purchase_count - used_count)
            
            plan_dict['can_apply'] = can_apply
            plan_dict['used_count'] = used_count
            plan_dict['approved_count'] = used_count  # 保持兼容性
            plan_dict['remaining_count'] = remaining_count
            plan_dict['application_status'] = application_status
            plan_dict['application_id'] = application_id
        else:
            plan_dict['application_status'] = None
            plan_dict['application_id'] = None
            plan_dict['can_apply'] = False  # 未登录不能申请
        
        plans_data.append(plan_dict)
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'plans': plans_data,
            'config': {
                'min_reason_length': min_reason_length,
                'max_reason_length': max_reason_length
            }
        }
    })
