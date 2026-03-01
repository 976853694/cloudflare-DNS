"""
托管商路由
处理托管商申请、渠道、域名、套餐和收益管理
"""
from functools import wraps
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import User, DnsChannel, Domain, Plan, Setting
from app.models.host_application import HostApplication
from app.models.host_transaction import HostTransaction
from app.utils.timezone import now as beijing_now

host_bp = Blueprint('host', __name__)


def get_current_user():
    """获取当前登录用户"""
    user_id = get_jwt_identity()
    return User.query.get(user_id)


def host_required(f):
    """要求托管商权限的装饰器"""
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'code': 401, 'message': '用户不存在'}), 401
        if user.host_status != User.HOST_STATUS_APPROVED:
            return jsonify({'code': 403, 'message': '需要托管商权限'}), 403
        g.current_user = user
        return f(*args, **kwargs)
    return decorated


def owner_required(model_class):
    """验证资源所有权的装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            resource_id = kwargs.get('id')
            resource = model_class.query.get(resource_id)
            if not resource:
                return jsonify({'code': 404, 'message': '资源不存在'}), 404
            user = g.current_user
            if resource.owner_id != user.id and not user.is_admin:
                return jsonify({'code': 403, 'message': '无权访问此资源'}), 403
            g.resource = resource
            return f(*args, **kwargs)
        return decorated
    return decorator


# ==================== 托管申请 ====================

@host_bp.route('/apply', methods=['POST'])
@jwt_required()
def apply_host():
    """提交托管商申请"""
    from app.utils.logger import get_logger
    logger = get_logger(__name__)
    
    try:
        user = get_current_user()
        if not user:
            logger.warning(f"申请失败: 用户不存在 (JWT token 无效)")
            return jsonify({'code': 401, 'message': '用户不存在'}), 401
        
        # 检查托管功能是否启用
        if not Setting.get('host_enabled', True):
            logger.info(f"用户 {user.id} 申请被拒绝: 托管功能未启用")
            return jsonify({'code': 403, 'message': '托管功能未启用'}), 403
        
        # 检查是否可以申请
        if not user.can_apply_host:
            logger.info(f"用户 {user.id} 申请被拒绝: 当前状态为 {user.host_status}，无法申请")
            return jsonify({
                'code': 400, 
                'message': f'您已有待审核或已通过的申请（当前状态: {user.host_status}）'
            }), 400
        
        data = request.get_json() or {}
        reason = data.get('reason', '').strip()
        
        # 验证申请理由
        min_length = Setting.get('host_min_apply_reason', 10)
        if not reason:
            logger.info(f"用户 {user.id} 申请被拒绝: 申请理由为空")
            return jsonify({'code': 400, 'message': '申请理由不能为空'}), 400
        
        if len(reason) < min_length:
            logger.info(f"用户 {user.id} 申请被拒绝: 申请理由长度 {len(reason)} < {min_length}")
            return jsonify({'code': 400, 'message': f'申请理由至少需要{min_length}个字符'}), 400
        
        # 创建申请
        application = HostApplication(
            user_id=user.id,
            reason=reason,
            status=HostApplication.STATUS_PENDING
        )
        
        # 更新用户状态
        user.host_status = User.HOST_STATUS_PENDING
        
        db.session.add(application)
        db.session.commit()
        
        logger.info(f"用户 {user.id} 成功提交托管商申请 (申请ID: {application.id})")
        
        # 发送邮件通知管理员
        try:
            admin_email = Setting.get('admin_email', '')
            if admin_email:
                from app.services.email import EmailService
                from app.services.email_templates import EmailTemplateService
                
                site_url = request.host_url.rstrip('/')
                subject, html = EmailTemplateService.render_email('host_application_submitted', {
                    'username': user.username,
                    'email': user.email,
                    'reason': reason,
                    'created_at': application.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'admin_url': f"{site_url}/admin/host/applications/{application.id}",
                    'application_id': application.id
                })
                if subject and html:
                    success, msg = EmailService.send(admin_email, subject, html)
                    if success:
                        logger.info(f"已发送托管商申请通知邮件给管理员: {admin_email}")
                    else:
                        logger.error(f"发送托管商申请通知邮件失败: {msg}")
                else:
                    logger.error(f"邮件模板 host_application_submitted 渲染失败")
        except Exception as e:
            logger.error(f"发送托管商申请通知邮件失败: {e}", exc_info=True)
        
        return jsonify({
            'code': 200,
            'message': '申请已提交，请等待管理员审核',
            'data': application.to_dict()
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"提交托管商申请时发生错误: {str(e)}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': '系统错误，请稍后重试'
        }), 500


@host_bp.route('/status', methods=['GET'])
@jwt_required()
def get_host_status():
    """获取托管状态"""
    from app.utils.logger import get_logger
    logger = get_logger(__name__)
    
    try:
        user = get_current_user()
        if not user:
            logger.warning("获取托管状态失败: 用户不存在")
            return jsonify({'code': 401, 'message': '用户不存在'}), 401
        
        # 获取最新申请
        latest_application = HostApplication.query.filter_by(user_id=user.id)\
            .order_by(HostApplication.created_at.desc()).first()
        
        logger.debug(f"用户 {user.id} 查询托管状态: {user.host_status}")
        
        return jsonify({
            'code': 200,
            'data': {
                'host_status': user.host_status,
                'is_host': user.is_host,
                'can_apply': user.can_apply_host,
                'host_enabled': Setting.get('host_enabled', True),
                'host_suspended_reason': user.host_suspended_reason,
                'latest_application': latest_application.to_dict() if latest_application else None
            }
        })
    
    except Exception as e:
        logger.error(f"获取托管状态时发生错误: {str(e)}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': '系统错误，请稍后重试'
        }), 500


@host_bp.route('/dashboard', methods=['GET'])
@host_required
def get_dashboard():
    """托管商仪表盘"""
    user = g.current_user
    
    # 统计数据
    channels_count = DnsChannel.query.filter_by(owner_id=user.id).count()
    domains_count = Domain.query.filter_by(owner_id=user.id).count()
    plans_count = Plan.query.filter_by(owner_id=user.id).count()
    
    # 收益统计
    total_earnings = db.session.query(db.func.sum(HostTransaction.host_earnings))\
        .filter_by(host_id=user.id).scalar() or 0
    
    # 获取默认抽成比例
    default_commission = Setting.get('host_default_commission', 10)
    effective_rate = user.get_effective_commission_rate(default_commission)
    
    return jsonify({
        'code': 200,
        'data': {
            'host_balance': float(user.host_balance) if user.host_balance else 0,
            'total_earnings': float(total_earnings),
            'commission_rate': effective_rate,
            'channels_count': channels_count,
            'domains_count': domains_count,
            'plans_count': plans_count
        }
    })


# ==================== 渠道管理 ====================

@host_bp.route('/channels/providers', methods=['GET'])
@host_required
def get_providers():
    """获取支持的服务商列表"""
    from app.services.dns import DnsServiceFactory
    providers = DnsServiceFactory.get_providers()
    # 添加凭据字段信息
    for p in providers:
        p['credential_fields'] = DnsServiceFactory.get_credential_fields(p['type'])
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {'providers': providers}
    })


@host_bp.route('/channels', methods=['GET'])
@host_required
def list_channels():
    """获取托管商的渠道列表"""
    user = g.current_user
    channels = DnsChannel.query.filter_by(owner_id=user.id).all()
    return jsonify({
        'code': 200,
        'data': [c.to_dict() for c in channels]
    })


@host_bp.route('/channels', methods=['POST'])
@host_required
def create_channel():
    """添加渠道"""
    user = g.current_user
    data = request.get_json() or {}
    
    name = data.get('name', '').strip()
    provider_type = data.get('provider_type', '').strip()
    credentials = data.get('credentials', {})
    remark = data.get('remark', '').strip()
    
    if not name:
        return jsonify({'code': 400, 'message': '渠道名称不能为空'}), 400
    if not provider_type:
        return jsonify({'code': 400, 'message': '请选择服务商类型'}), 400
    if not credentials:
        return jsonify({'code': 400, 'message': '请填写凭据信息'}), 400
    
    channel = DnsChannel(
        owner_id=user.id,
        name=name,
        provider_type=provider_type,
        remark=remark,
        status=1
    )
    channel.set_credentials(credentials)
    
    # 验证凭据
    try:
        if not channel.verify_credentials():
            return jsonify({'code': 400, 'message': '凭据验证失败，请检查配置'}), 400
    except Exception as e:
        return jsonify({'code': 400, 'message': f'凭据验证失败: {str(e)}'}), 400
    
    db.session.add(channel)
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '渠道添加成功',
        'data': channel.to_dict()
    })


@host_bp.route('/channels/<int:id>', methods=['PUT'])
@host_required
@owner_required(DnsChannel)
def update_channel(id):
    """更新渠道"""
    channel = g.resource
    data = request.get_json() or {}
    
    if 'name' in data:
        channel.name = data['name'].strip()
    if 'remark' in data:
        channel.remark = data['remark'].strip()
    if 'status' in data:
        channel.status = 1 if data['status'] else 0
    if 'credentials' in data and data['credentials']:
        channel.set_credentials(data['credentials'])
        # 验证新凭据
        try:
            if not channel.verify_credentials():
                return jsonify({'code': 400, 'message': '凭据验证失败'}), 400
        except Exception as e:
            return jsonify({'code': 400, 'message': f'凭据验证失败: {str(e)}'}), 400
    
    db.session.commit()
    return jsonify({'code': 200, 'message': '更新成功', 'data': channel.to_dict()})


@host_bp.route('/channels/<int:id>', methods=['DELETE'])
@host_required
@owner_required(DnsChannel)
def delete_channel(id):
    """删除渠道"""
    channel = g.resource
    user = g.current_user
    
    # 检查是否有该托管商的域名在使用此渠道
    host_domains_count = Domain.query.filter_by(dns_channel_id=channel.id, owner_id=user.id).count()
    if host_domains_count > 0:
        return jsonify({'code': 400, 'message': f'该渠道下有{host_domains_count}个域名，请先删除域名'}), 400
    
    db.session.delete(channel)
    db.session.commit()
    return jsonify({'code': 200, 'message': '删除成功'})


@host_bp.route('/channels/<int:id>/verify', methods=['POST'])
@host_required
@owner_required(DnsChannel)
def verify_channel(id):
    """验证渠道凭据"""
    channel = g.resource
    
    try:
        if channel.verify_credentials():
            return jsonify({'code': 200, 'message': '凭据验证成功'})
        else:
            return jsonify({'code': 400, 'message': '凭据验证失败，请检查配置'}), 400
    except Exception as e:
        return jsonify({'code': 400, 'message': f'凭据验证失败: {str(e)}'}), 400


@host_bp.route('/channels/<int:id>/zones', methods=['GET'])
@host_required
@owner_required(DnsChannel)
def get_channel_zones(id):
    """获取渠道的域名列表（Zone）"""
    channel = g.resource
    
    try:
        service = channel.get_service()
        keyword = request.args.get('keyword', '')
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        fetch_all = request.args.get('all', '').lower() in ('1', 'true', 'yes')
        
        if fetch_all:
            # 获取全部域名（循环分页）
            all_zones = []
            current_page = 1
            batch_size = 100
            
            while True:
                result = service.get_zones(keyword=keyword, page=current_page, page_size=batch_size)
                zones_list = result.get('list', [])
                
                if not zones_list:
                    break
                
                all_zones.extend(zones_list)
                total = result.get('total', len(zones_list))
                
                if len(all_zones) >= total:
                    break
                
                current_page += 1
            
            zones = [zone.to_dict() for zone in all_zones]
            
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': {
                    'total': len(zones),
                    'zones': zones
                }
            })
        else:
            # 普通分页获取
            result = service.get_zones(keyword=keyword, page=page, page_size=page_size)
            
            zones = []
            for zone in result['list']:
                zones.append(zone.to_dict())
            
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': {
                    'total': result['total'],
                    'zones': zones
                }
            })
    except Exception as e:
        return jsonify({'code': 500, 'message': f'获取域名列表失败: {str(e)}'}), 500


# ==================== 域名管理 ====================

@host_bp.route('/domains', methods=['GET'])
@host_required
def list_domains():
    """获取托管商的域名列表"""
    user = g.current_user
    domains = Domain.query.filter_by(owner_id=user.id).all()
    return jsonify({
        'code': 200,
        'data': [d.to_admin_dict() for d in domains]
    })


@host_bp.route('/domains', methods=['POST'])
@host_required
def create_domain():
    """添加域名"""
    user = g.current_user
    data = request.get_json() or {}
    
    name = data.get('name', '').strip().lower()
    channel_id = data.get('channel_id')
    zone_id = data.get('zone_id', '').strip()
    description = data.get('description', '').strip()
    
    if not name:
        return jsonify({'code': 400, 'message': '域名不能为空'}), 400
    if not channel_id:
        return jsonify({'code': 400, 'message': '请选择渠道'}), 400
    
    # 验证渠道所有权
    channel = DnsChannel.query.get(channel_id)
    if not channel or channel.owner_id != user.id:
        return jsonify({'code': 400, 'message': '渠道不存在或无权使用'}), 400
    
    # 检查域名是否已存在
    if Domain.query.filter_by(name=name).first():
        return jsonify({'code': 400, 'message': '该域名已存在'}), 400
    
    # 如果没有提供 zone_id，则验证域名在DNS服务商中存在
    if not zone_id:
        try:
            service = channel.get_service()
            result = service.get_zones(keyword=name, page=1, page_size=100)
            zones_list = result.get('list', [])
            zone_found = None
            for z in zones_list:
                if z.name.lower() == name:
                    zone_found = z
                    break
            if not zone_found:
                return jsonify({'code': 400, 'message': '该域名在DNS服务商中不存在'}), 400
            zone_id = zone_found.zone_id
        except Exception as e:
            return jsonify({'code': 400, 'message': f'验证域名失败: {str(e)}'}), 400
    
    domain = Domain(
        owner_id=user.id,
        dns_channel_id=channel_id,
        name=name,
        zone_id=zone_id,
        description=description,
        status=1,
        allow_register=1
    )
    
    db.session.add(domain)
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '域名添加成功',
        'data': domain.to_admin_dict()
    })


@host_bp.route('/domains/<int:id>', methods=['PUT'])
@host_required
@owner_required(Domain)
def update_domain(id):
    """更新域名"""
    domain = g.resource
    data = request.get_json() or {}
    
    if 'description' in data:
        domain.description = data['description'].strip()
    if 'status' in data:
        domain.status = 1 if data['status'] else 0
    if 'allow_register' in data:
        domain.allow_register = 1 if data['allow_register'] else 0
    
    db.session.commit()
    return jsonify({'code': 200, 'message': '更新成功', 'data': domain.to_admin_dict()})


@host_bp.route('/domains/<int:id>', methods=['DELETE'])
@host_required
@owner_required(Domain)
def delete_domain(id):
    """删除域名（级联删除子域名和套餐关联）"""
    domain = g.resource
    user = g.current_user
    
    # 统计将被删除的内容
    subdomains_count = domain.subdomains.count()
    
    # 删除关联此域名的套餐（只删除托管商自己的套餐）
    plans_to_delete = Plan.query.filter(
        Plan.owner_id == user.id,
        Plan.domains.any(Domain.id == domain.id)
    ).all()
    
    for plan in plans_to_delete:
        # 如果套餐只关联这一个域名，删除整个套餐
        if len(plan.domains) == 1:
            db.session.delete(plan)
        else:
            # 如果套餐关联多个域名，只移除此域名的关联
            plan.domains = [d for d in plan.domains if d.id != domain.id]
    
    # 删除所有子域名（会级联删除DNS记录）
    for subdomain in domain.subdomains.all():
        db.session.delete(subdomain)
    
    # 删除域名
    db.session.delete(domain)
    db.session.commit()
    
    return jsonify({
        'code': 200, 
        'message': f'删除成功，已清理 {subdomains_count} 个子域名和 {len(plans_to_delete)} 个套餐关联'
    })


# ==================== 套餐管理 ====================

@host_bp.route('/plans', methods=['GET'])
@host_required
def list_plans():
    """获取托管商的套餐列表"""
    user = g.current_user
    plans = Plan.query.filter_by(owner_id=user.id).all()
    return jsonify({
        'code': 200,
        'data': [p.to_dict() for p in plans]
    })


@host_bp.route('/plans', methods=['POST'])
@host_required
def create_plan():
    """创建套餐"""
    user = g.current_user
    data = request.get_json() or {}
    
    name = data.get('name', '').strip()
    domain_ids = data.get('domain_ids', [])
    price = data.get('price', 0)
    duration_days = data.get('duration_days', 30)
    
    if not name:
        return jsonify({'code': 400, 'message': '套餐名称不能为空'}), 400
    if not domain_ids:
        return jsonify({'code': 400, 'message': '请选择关联域名'}), 400
    if price < 0:
        return jsonify({'code': 400, 'message': '价格不能为负数'}), 400
    if duration_days < -1 or duration_days == 0:
        return jsonify({'code': 400, 'message': '时长无效（-1为永久，正数为天数）'}), 400
    
    # 验证域名所有权
    domains = Domain.query.filter(Domain.id.in_(domain_ids), Domain.owner_id == user.id).all()
    if len(domains) != len(domain_ids):
        return jsonify({'code': 400, 'message': '部分域名不存在或无权使用'}), 400
    
    plan = Plan(
        owner_id=user.id,
        name=name,
        price=price,
        duration_days=duration_days,
        min_length=data.get('min_length', 1),
        max_length=data.get('max_length', 63),
        max_records=data.get('max_records', 10),
        description=data.get('description', ''),
        status=data.get('status', 1),
        sort_order=data.get('sort_order', 0),
        is_free=data.get('is_free', False),
        max_purchase_count=data.get('max_purchase_count', 0),
        renew_before_days=data.get('renew_before_days', 0),
        points_per_day=data.get('points_per_day', 0)
    )
    plan.domains = domains
    
    db.session.add(plan)
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '套餐创建成功',
        'data': plan.to_dict()
    })


@host_bp.route('/plans/<int:id>', methods=['PUT'])
@host_required
@owner_required(Plan)
def update_plan(id):
    """更新套餐"""
    plan = g.resource
    user = g.current_user
    data = request.get_json() or {}
    
    if 'name' in data:
        plan.name = data['name'].strip()
    if 'price' in data:
        if data['price'] < 0:
            return jsonify({'code': 400, 'message': '价格不能为负数'}), 400
        plan.price = data['price']
    if 'duration_days' in data:
        plan.duration_days = data['duration_days']
    if 'min_length' in data:
        plan.min_length = data['min_length']
    if 'max_length' in data:
        plan.max_length = data['max_length']
    if 'max_records' in data:
        plan.max_records = data['max_records']
    if 'description' in data:
        plan.description = data['description']
    if 'status' in data:
        plan.status = 1 if data['status'] else 0
    if 'sort_order' in data:
        plan.sort_order = data['sort_order']
    if 'is_free' in data:
        plan.is_free = data['is_free']
    if 'max_purchase_count' in data:
        plan.max_purchase_count = data['max_purchase_count']
    if 'renew_before_days' in data:
        plan.renew_before_days = data['renew_before_days']
    if 'points_per_day' in data:
        plan.points_per_day = data['points_per_day']
    if 'domain_ids' in data:
        domains = Domain.query.filter(
            Domain.id.in_(data['domain_ids']), 
            Domain.owner_id == user.id
        ).all()
        plan.domains = domains
    
    db.session.commit()
    return jsonify({'code': 200, 'message': '更新成功', 'data': plan.to_dict()})


@host_bp.route('/plans/<int:id>', methods=['DELETE'])
@host_required
@owner_required(Plan)
def delete_plan(id):
    """删除套餐"""
    plan = g.resource
    db.session.delete(plan)
    db.session.commit()
    return jsonify({'code': 200, 'message': '删除成功'})


# ==================== 交易记录 ====================

@host_bp.route('/transactions', methods=['GET'])
@host_required
def list_transactions():
    """获取交易记录"""
    user = g.current_user
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    domain_id = request.args.get('domain_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = HostTransaction.query.filter_by(host_id=user.id)
    
    if domain_id:
        query = query.filter_by(domain_id=domain_id)
    if start_date:
        query = query.filter(HostTransaction.created_at >= start_date)
    if end_date:
        query = query.filter(HostTransaction.created_at <= end_date)
    
    query = query.order_by(HostTransaction.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # 计算总收益
    total_earnings = db.session.query(db.func.sum(HostTransaction.host_earnings))\
        .filter_by(host_id=user.id).scalar() or 0
    
    return jsonify({
        'code': 200,
        'data': {
            'items': [t.to_dict(include_details=True) for t in pagination.items],
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages,
            'total_pages': pagination.pages,
            'total_earnings': float(total_earnings)
        }
    })


# ==================== 提现管理 ====================

@host_bp.route('/withdrawals', methods=['GET'])
@host_required
def list_withdrawals():
    """获取提现记录"""
    from app.models.host_withdrawal import HostWithdrawal
    
    user = g.current_user
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    
    query = HostWithdrawal.query.filter_by(host_id=user.id)
    
    if status:
        query = query.filter_by(status=status)
    
    query = query.order_by(HostWithdrawal.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'code': 200,
        'data': {
            'items': [w.to_dict() for w in pagination.items],
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    })


@host_bp.route('/withdrawals', methods=['POST'])
@host_required
def create_withdrawal():
    """创建提现申请"""
    from app.models.host_withdrawal import HostWithdrawal
    from app.utils.logger import get_logger
    from decimal import Decimal
    
    logger = get_logger(__name__)
    user = g.current_user
    data = request.get_json() or {}
    
    try:
        amount = Decimal(str(data.get('amount', 0)))
    except:
        return jsonify({'code': 400, 'message': '金额格式无效'}), 400
    
    payment_method = data.get('payment_method', '').strip()
    payment_account = data.get('payment_account', '').strip()
    payment_name = data.get('payment_name', '').strip()
    
    # 验证必填字段
    if amount <= 0:
        return jsonify({'code': 400, 'message': '提现金额必须大于0'}), 400
    if not payment_method:
        return jsonify({'code': 400, 'message': '请选择收款方式'}), 400
    if not payment_account:
        return jsonify({'code': 400, 'message': '请填写收款账号'}), 400
    if not payment_name:
        return jsonify({'code': 400, 'message': '请填写收款人姓名'}), 400
    
    # 验证收款方式
    valid_methods = ['alipay', 'wechat', 'bank']
    if payment_method not in valid_methods:
        return jsonify({'code': 400, 'message': '无效的收款方式'}), 400
    
    # 检查余额
    user_balance = Decimal(str(user.host_balance or 0))
    if user_balance < amount:
        return jsonify({'code': 400, 'message': f'余额不足，当前余额: ¥{user_balance}'}), 400
    
    # 检查最小提现金额
    min_amount_setting = Setting.get('host_min_withdraw', 100)
    min_amount = Decimal(str(min_amount_setting))
    if amount < min_amount:
        return jsonify({'code': 400, 'message': f'最小提现金额为 ¥{min_amount}'}), 400
    
    # 检查是否有待处理的提现
    pending = HostWithdrawal.query.filter_by(
        host_id=user.id, 
        status=HostWithdrawal.STATUS_PENDING
    ).first()
    if pending:
        return jsonify({'code': 400, 'message': '您有待处理的提现申请，请等待处理完成'}), 400
    
    try:
        withdrawal = HostWithdrawal(
            host_id=user.id,
            amount=amount,
            payment_method=payment_method,
            payment_account=payment_account,
            payment_name=payment_name,
            status=HostWithdrawal.STATUS_PENDING
        )
        
        # 冻结余额 - 确保类型正确
        user.host_balance = user_balance - amount
        
        db.session.add(withdrawal)
        db.session.commit()
        
        logger.info(f"托管商 {user.id} 创建提现申请: ¥{amount}")
        
        return jsonify({
            'code': 200,
            'message': '提现申请已提交，请等待管理员审核',
            'data': withdrawal.to_dict()
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建提现申请失败: {str(e)}", exc_info=True)
        return jsonify({'code': 500, 'message': '系统错误，请稍后重试'}), 500


@host_bp.route('/withdrawals/<int:id>/cancel', methods=['POST'])
@host_required
def cancel_withdrawal(id):
    """取消提现申请"""
    from app.models.host_withdrawal import HostWithdrawal
    from app.utils.logger import get_logger
    
    logger = get_logger(__name__)
    user = g.current_user
    
    withdrawal = HostWithdrawal.query.get_or_404(id)
    
    # 验证所有权
    if withdrawal.host_id != user.id:
        return jsonify({'code': 403, 'message': '无权操作此提现申请'}), 403
    
    # 只能取消待审核的申请
    if not withdrawal.is_pending:
        return jsonify({'code': 400, 'message': '只能取消待审核的提现申请'}), 400
    
    try:
        # 返还余额
        user.host_balance += withdrawal.amount
        
        # 删除申请
        db.session.delete(withdrawal)
        db.session.commit()
        
        logger.info(f"托管商 {user.id} 取消提现申请 {id}，金额: ¥{withdrawal.amount}")
        
        return jsonify({
            'code': 200,
            'message': '提现申请已取消，金额已返还'
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"取消提现申请失败: {str(e)}", exc_info=True)
        return jsonify({'code': 500, 'message': '系统错误，请稍后重试'}), 500


# ==================== 收益统计 ====================

@host_bp.route('/earnings', methods=['GET'])
@host_required
def get_earnings():
    """获取收益统计"""
    from app.models.host_withdrawal import HostWithdrawal
    from app.services.host_service import HostService
    
    user = g.current_user
    stats = HostService.get_host_statistics(user.id)
    
    # 获取默认抽成比例
    default_commission = Setting.get('host_default_commission', 10)
    effective_rate = user.get_effective_commission_rate(default_commission)
    
    # 获取最低提现金额设置
    min_withdraw = Setting.get('host_min_withdraw', 100)
    
    return jsonify({
        'code': 200,
        'data': {
            'host_balance': float(user.host_balance) if user.host_balance else 0,
            'total_earnings': stats.get('total_earnings', 0),
            'withdrawn': stats.get('withdrawn', 0),
            'pending_withdrawal': stats.get('pending_withdrawal', 0),
            'commission_rate': effective_rate,
            'channels_count': stats.get('channels_count', 0),
            'domains_count': stats.get('domains_count', 0),
            'plans_count': stats.get('plans_count', 0),
            'min_withdraw': float(min_withdraw)
        }
    })


# ==================== 免费套餐申请审核 ====================

@host_bp.route('/free-plan-applications', methods=['GET'])
@host_required
def get_free_plan_applications():
    """获取免费套餐申请列表"""
    from app.services.host_free_plan_service import HostFreePlanService
    
    user = g.current_user
    
    status = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    result = HostFreePlanService.get_applications(
        host_id=user.id,
        status=status,
        page=page,
        per_page=per_page
    )
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': result
    })


@host_bp.route('/free-plan-applications/<int:app_id>', methods=['GET'])
@host_required
def get_free_plan_application_detail(app_id):
    """获取免费套餐申请详情"""
    from app.models import FreePlanApplication
    
    user = g.current_user
    
    application = FreePlanApplication.query.get(app_id)
    
    if not application:
        return jsonify({'code': 404, 'message': '申请不存在'}), 404
    
    # 权限检查：只能查看自己套餐的申请
    plan = application.plan
    if not plan or not plan.is_host_owned or plan.owner_id != user.id:
        return jsonify({'code': 403, 'message': '无权查看此申请'}), 403
    
    # 获取用户的历史申请记录
    user_applications = FreePlanApplication.query.filter_by(
        user_id=application.user_id
    ).order_by(FreePlanApplication.created_at.desc()).limit(10).all()
    
    # 获取用户的域名数量
    applicant = application.user
    subdomain_count = applicant.subdomains.count() if applicant else 0
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'application': application.to_dict(include_user=True, include_plan=True),
            'user_history': [app.to_dict(include_plan=True) for app in user_applications],
            'user_subdomain_count': subdomain_count
        }
    })


@host_bp.route('/free-plan-applications/<int:app_id>/review', methods=['POST'])
@host_required
def review_free_plan_application(app_id):
    """审核免费套餐申请"""
    from app.services.host_free_plan_service import HostFreePlanService
    
    user = g.current_user
    data = request.get_json() or {}
    
    action = data.get('action')  # 'approve' 或 'reject'
    reason = data.get('reason', '').strip()  # 拒绝原因
    note = data.get('note', '').strip()  # 备注
    
    if action not in ['approve', 'reject']:
        return jsonify({'code': 400, 'message': '无效的审核动作'}), 400
    
    if action == 'reject' and not reason:
        return jsonify({'code': 400, 'message': '请填写拒绝原因'}), 400
    
    success, message, result_data = HostFreePlanService.review_application(
        application_id=app_id,
        host_id=user.id,
        action=action,
        reason=reason,
        note=note
    )
    
    if success:
        return jsonify({
            'code': 200,
            'message': message,
            'data': result_data
        })
    else:
        return jsonify({'code': 400, 'message': message}), 400


@host_bp.route('/free-plan-applications/stats', methods=['GET'])
@host_required
def get_free_plan_application_stats():
    """获取免费套餐申请统计"""
    from app.services.host_free_plan_service import HostFreePlanService
    
    user = g.current_user
    
    stats = HostFreePlanService.get_statistics(user.id)
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': stats
    })
