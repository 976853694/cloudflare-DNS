"""
开放API路由 - 提供给外部系统调用
"""
from functools import wraps
from flask import Blueprint, request, jsonify, g
from app import db
from app.models import User, Domain, Subdomain, DnsRecord, Plan
from app.utils.ip_utils import get_real_ip

open_api_bp = Blueprint('open_api', __name__)


def api_auth_required(f):
    """API认证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # 获取认证头
        api_key = request.headers.get('X-Api-Key')
        timestamp = request.headers.get('X-Timestamp')
        signature = request.headers.get('X-Signature')
        
        if not all([api_key, timestamp, signature]):
            return jsonify({'code': 401, 'message': '缺少认证参数'}), 401
        
        # 查找用户
        user = User.query.filter_by(api_key=api_key).first()
        if not user:
            return jsonify({'code': 401, 'message': 'API Key无效'}), 401
        
        # 检查API是否启用
        if not user.api_enabled:
            return jsonify({'code': 403, 'message': 'API未启用'}), 403
        
        # 检查用户状态
        if user.is_banned:
            # 记录被拒绝的API访问
            from app.models import OperationLog
            OperationLog.log(
                user_id=user.id,
                action='login_rejected',
                target_type='user',
                target_id=user.id,
                detail=f'用户 {user.username} API认证被拒绝：账户已封禁',
                ip_address=get_real_ip()
            )
            return jsonify({'code': 403, 'message': '账户已被禁用'}), 403
        
        if user.is_sleeping:
            # 记录被拒绝的API访问
            from app.models import OperationLog
            OperationLog.log(
                user_id=user.id,
                action='login_rejected',
                target_type='user',
                target_id=user.id,
                detail=f'用户 {user.username} API认证被拒绝：账户未激活',
                ip_address=get_real_ip()
            )
            return jsonify({'code': 403, 'message': '账户未激活，请先验证邮箱'}), 403
        
        # 检查IP白名单
        client_ip = get_real_ip()
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        if not user.is_api_ip_allowed(client_ip):
            return jsonify({'code': 403, 'message': 'IP不在白名单中'}), 403
        
        # 验证签名
        body = request.get_data(as_text=True) or ''
        valid, error = user.verify_api_signature(
            timestamp, request.method, request.path, body, signature
        )
        if not valid:
            return jsonify({'code': 401, 'message': error}), 401
        
        # 将用户存入g对象
        g.api_user = user
        return f(*args, **kwargs)
    
    return decorated


# ========== 用户信息 ==========

@open_api_bp.route('/user/info', methods=['GET'])
@api_auth_required
def get_user_info():
    """获取用户信息"""
    user = g.api_user
    return jsonify({
        'code': 200,
        'data': {
            'username': user.username,
            'email': user.email,
            'balance': float(user.balance) if user.balance != -1 else -1,
            'balance_text': user.balance_text,
            'subdomain_count': user.subdomains.count(),
            'max_domains': user.max_domains
        }
    })


# ========== 域名列表 ==========

@open_api_bp.route('/domains', methods=['GET'])
@api_auth_required
def get_domains():
    """获取可购买的域名列表"""
    domains = Domain.query.filter_by(status=1).all()
    
    result = []
    for domain in domains:
        # 获取该域名关联的套餐（排除免费套餐）
        plans = Plan.query.filter(
            Plan.status == 1,
            Plan.is_free == False,  # 只返回付费套餐
            Plan.domains.any(id=domain.id)
        ).all()
        
        if plans:
            result.append({
                'id': domain.id,
                'name': domain.name,
                'description': domain.description,
                'plans': [{
                    'id': p.id,
                    'name': p.name,
                    'price': float(p.price),
                    'duration_days': p.duration_days,
                    'max_records': p.max_records,
                    'description': p.description
                } for p in plans]
            })
    
    return jsonify({
        'code': 200,
        'data': {'domains': result}
    })


@open_api_bp.route('/domains/<int:domain_id>/check', methods=['GET'])
@api_auth_required
def check_subdomain(domain_id):
    """检查子域名前缀是否可用"""
    name = request.args.get('name', '').strip().lower()
    if not name:
        name = request.args.get('prefix', '').strip().lower()
    
    if not name:
        return jsonify({'code': 400, 'message': '请提供子域名前缀'}), 400
    
    domain = Domain.query.get(domain_id)
    if not domain or domain.status != 1:
        return jsonify({'code': 404, 'message': '域名不存在或已禁用'}), 404
    
    # 检查是否已存在
    exists = Subdomain.query.filter_by(
        domain_id=domain_id,
        name=name
    ).first() is not None
    
    # 检查敏感词
    from app.services.sensitive_filter import SensitiveFilter
    if SensitiveFilter.contains_sensitive(name):
        return jsonify({
            'code': 200,
            'data': {
                'available': False,
                'name': name,
                'full_name': f"{name}.{domain.name}",
                'message': '该域名前缀包含敏感词'
            }
        })
    
    return jsonify({
        'code': 200,
        'data': {
            'available': not exists,
            'name': name,
            'full_name': f"{name}.{domain.name}",
            'message': '可以注册' if not exists else '已被占用'
        }
    })


@open_api_bp.route('/domains/<int:domain_id>/plans', methods=['GET'])
@api_auth_required
def get_domain_plans(domain_id):
    """获取指定域名的套餐列表（只返回付费套餐）"""
    domain = Domain.query.get(domain_id)
    if not domain or domain.status != 1:
        return jsonify({'code': 404, 'message': '域名不存在或已禁用'}), 404
    
    plans = Plan.query.filter(
        Plan.status == 1,
        Plan.is_free == False,  # 只返回付费套餐
        Plan.domains.any(id=domain_id)
    ).order_by(Plan.sort_order, Plan.id).all()
    
    return jsonify({
        'code': 200,
        'data': {
            'plans': [{
                'id': p.id,
                'name': p.name,
                'price': float(p.price),
                'duration_days': p.duration_days,
                'duration_text': '永久' if p.duration_days == -1 else f'{p.duration_days}天',
                'min_length': p.min_length,
                'max_length': p.max_length,
                'max_records': p.max_records,
                'description': p.description
            } for p in plans]
        }
    })


# ========== 子域名管理 ==========

@open_api_bp.route('/subdomains', methods=['GET'])
@api_auth_required
def get_subdomains():
    """获取用户的子域名列表"""
    user = g.api_user
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    pagination = user.subdomains.order_by(Subdomain.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'code': 200,
        'data': {
            'subdomains': [{
                'id': s.id,
                'name': s.name,
                'domain_name': s.domain.name if s.domain else None,
                'full_name': s.full_name,
                'status': s.status,
                'expires_at': s.expires_at.isoformat() if s.expires_at else None,
                'created_at': s.created_at.isoformat() if s.created_at else None
            } for s in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        }
    })


@open_api_bp.route('/subdomains', methods=['POST'])
@api_auth_required
def create_subdomain():
    """购买子域名（已废弃，请使用 /purchase）"""
    return jsonify({'code': 400, 'message': '请使用 /api/open/purchase 接口购买域名'}), 400


@open_api_bp.route('/purchase', methods=['POST'])
@api_auth_required
def purchase_subdomain():
    """购买子域名"""
    user = g.api_user
    data = request.get_json()
    
    domain_id = data.get('domain_id')
    name = data.get('name', '').strip().lower()
    plan_id = data.get('plan_id')
    coupon_code = data.get('coupon_code')
    
    if not all([domain_id, name, plan_id]):
        return jsonify({'code': 400, 'message': '缺少必要参数'}), 400
    
    # 验证域名
    domain = Domain.query.get(domain_id)
    if not domain or domain.status != 1:
        return jsonify({'code': 404, 'message': '域名不存在或已禁用'}), 404
    
    # 验证套餐
    plan = Plan.query.get(plan_id)
    if not plan or plan.status != 1:
        return jsonify({'code': 404, 'message': '套餐不存在或已禁用'}), 404
    
    # 检查套餐是否适用于该域名
    if domain not in plan.domains:
        return jsonify({'code': 400, 'message': '该套餐不适用于此域名'}), 400
    
    # 验证域名前缀长度
    name_len = len(name)
    if name_len < plan.min_length or name_len > plan.max_length:
        return jsonify({'code': 400, 'message': f'域名前缀长度需在 {plan.min_length}-{plan.max_length} 个字符之间'}), 400
    
    # 验证域名前缀格式
    from app.utils.validators import validate_subdomain_name
    if not validate_subdomain_name(name, min_len=plan.min_length, max_len=plan.max_length):
        return jsonify({'code': 400, 'message': '域名前缀格式不正确'}), 400
    
    # 检查敏感词
    from app.services.sensitive_filter import SensitiveFilter
    if SensitiveFilter.contains_sensitive(name):
        return jsonify({'code': 400, 'message': '域名前缀包含敏感词'}), 400
    
    # 检查子域名是否已存在
    if Subdomain.query.filter_by(domain_id=domain_id, name=name).first():
        return jsonify({'code': 409, 'message': '子域名已被使用'}), 409
    
    # 检查用户域名数量限制
    if user.subdomains.count() >= user.max_domains:
        return jsonify({'code': 403, 'message': '已达到域名数量上限'}), 403
    
    # 计算价格
    from decimal import Decimal
    price = Decimal(str(plan.price))
    discount = Decimal('0')
    
    # 处理优惠券
    if coupon_code:
        from app.models.coupon import Coupon, CouponUsage
        coupon = Coupon.query.filter_by(code=coupon_code.upper()).first()
        if coupon and coupon.is_valid:
            user_usage = CouponUsage.get_user_usage_count(coupon.id, user.id)
            if user_usage < coupon.per_user_limit:
                if coupon.can_use_for_plan(plan_id):
                    if plan.price >= float(coupon.min_amount):
                        discount = coupon.calculate_discount(plan.price)
                        price = coupon.get_final_price(plan.price)
    
    # 检查余额
    if not user.can_afford(float(price)):
        return jsonify({'code': 402, 'message': '余额不足'}), 402
    
    # 创建子域名
    from app.utils.timezone import now as beijing_now
    from datetime import timedelta
    
    full_name = f"{name}.{domain.name}"
    expires_at = None if plan.duration_days == -1 else beijing_now() + timedelta(days=plan.duration_days)
    
    subdomain = Subdomain(
        user_id=user.id,
        domain_id=domain_id,
        plan_id=plan_id,
        name=name,
        full_name=full_name,
        status=1,
        expires_at=expires_at
    )
    
    # 扣除余额
    user.deduct_balance(float(price))
    
    db.session.add(subdomain)
    db.session.commit()
    
    return jsonify({
        'code': 201,
        'message': '购买成功',
        'data': {
            'subdomain': {
                'id': subdomain.id,
                'name': subdomain.name,
                'full_name': subdomain.full_name,
                'expires_at': subdomain.expires_at.isoformat() if subdomain.expires_at else None
            },
            'cost': float(price),
            'discount': float(discount),
            'balance': float(user.balance) if user.balance != -1 else -1,
            'balance_text': user.balance_text
        }
    }), 201


@open_api_bp.route('/subdomains/<int:subdomain_id>', methods=['GET'])
@api_auth_required
def get_subdomain_detail(subdomain_id):
    """获取子域名详情"""
    user = g.api_user
    subdomain = Subdomain.query.filter_by(id=subdomain_id, user_id=user.id).first()
    
    if not subdomain:
        return jsonify({'code': 404, 'message': '子域名不存在'}), 404
    
    return jsonify({
        'code': 200,
        'data': {
            'subdomain': {
                'id': subdomain.id,
                'name': subdomain.name,
                'domain_name': subdomain.domain.name if subdomain.domain else None,
                'full_name': subdomain.full_name,
                'status': subdomain.status,
                'plan_id': subdomain.plan_id,
                'expires_at': subdomain.expires_at.isoformat() if subdomain.expires_at else None,
                'created_at': subdomain.created_at.isoformat() if subdomain.created_at else None
            }
        }
    })


@open_api_bp.route('/subdomains/<int:subdomain_id>', methods=['DELETE'])
@api_auth_required
def delete_subdomain(subdomain_id):
    """删除子域名"""
    user = g.api_user
    subdomain = Subdomain.query.filter_by(id=subdomain_id, user_id=user.id).first()
    
    if not subdomain:
        return jsonify({'code': 404, 'message': '子域名不存在'}), 404
    
    # 删除关联的DNS记录
    DnsRecord.query.filter_by(subdomain_id=subdomain_id).delete()
    
    # 删除关联的转移记录（避免外键约束错误）
    from app.models.domain_transfer import DomainTransfer
    DomainTransfer.query.filter_by(subdomain_id=subdomain_id).delete()
    
    db.session.delete(subdomain)
    db.session.commit()
    
    return jsonify({'code': 200, 'message': '删除成功'})


@open_api_bp.route('/subdomains/<int:subdomain_id>/renew', methods=['POST'])
@api_auth_required
def renew_subdomain(subdomain_id):
    """续费子域名"""
    user = g.api_user
    subdomain = Subdomain.query.filter_by(id=subdomain_id, user_id=user.id).first()
    
    if not subdomain:
        return jsonify({'code': 404, 'message': '子域名不存在'}), 404
    
    data = request.get_json() or {}
    plan_id = data.get('plan_id', subdomain.plan_id)
    
    plan = Plan.query.get(plan_id)
    if not plan or plan.status != 1:
        return jsonify({'code': 404, 'message': '套餐不存在或已禁用'}), 404
    
    price = float(plan.price)
    
    # 检查余额
    if not user.can_afford(price):
        return jsonify({'code': 402, 'message': '余额不足'}), 402
    
    # 续费
    from app.utils.timezone import now as beijing_now
    from datetime import timedelta
    
    if subdomain.expires_at and subdomain.expires_at > beijing_now():
        subdomain.expires_at = subdomain.expires_at + timedelta(days=plan.duration_days)
    else:
        subdomain.expires_at = beijing_now() + timedelta(days=plan.duration_days)
    
    user.deduct_balance(price)
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '续费成功',
        'data': {
            'expires_at': subdomain.expires_at.isoformat(),
            'cost': price,
            'balance': float(user.balance) if user.balance != -1 else -1
        }
    })


# ========== DNS记录管理 ==========

@open_api_bp.route('/subdomains/<int:subdomain_id>/records', methods=['GET'])
@api_auth_required
def get_dns_records(subdomain_id):
    """获取DNS记录列表"""
    user = g.api_user
    subdomain = Subdomain.query.filter_by(id=subdomain_id, user_id=user.id).first()
    
    if not subdomain:
        return jsonify({'code': 404, 'message': '子域名不存在'}), 404
    
    records = DnsRecord.query.filter_by(subdomain_id=subdomain_id).all()
    
    return jsonify({
        'code': 200,
        'data': {
            'records': [{
                'id': r.cf_record_id or str(r.id),
                'type': r.type,
                'name': r.name,
                'content': r.content,
                'ttl': r.ttl,
                'proxied': r.proxied,
                'created_at': r.created_at.isoformat() if r.created_at else None
            } for r in records]
        }
    })


@open_api_bp.route('/subdomains/<int:subdomain_id>/records', methods=['POST'])
@api_auth_required
def create_dns_record(subdomain_id):
    """创建DNS记录"""
    user = g.api_user
    subdomain = Subdomain.query.filter_by(id=subdomain_id, user_id=user.id).first()
    
    if not subdomain:
        return jsonify({'code': 404, 'message': '子域名不存在'}), 404
    
    if subdomain.status != 1:
        return jsonify({'code': 403, 'message': '子域名已禁用'}), 403
    
    data = request.get_json()
    record_type = data.get('type', 'A').upper()
    name = data.get('name', '@')
    content = data.get('content', '').strip()
    ttl = data.get('ttl', 600)
    proxied = data.get('proxied', False)
    
    if not content:
        return jsonify({'code': 400, 'message': '记录值不能为空'}), 400
    
    # 检查记录数量限制
    plan = subdomain.plan
    if plan and plan.max_records > 0:
        current_count = DnsRecord.query.filter_by(subdomain_id=subdomain_id).count()
        if current_count >= plan.max_records:
            return jsonify({'code': 403, 'message': f'已达到记录数量上限({plan.max_records})'}), 403
    
    # 调用DNS服务商API创建记录
    try:
        from app.services.dns_service import DNSService
        dns_service = DNSService()
        
        result = dns_service.create_record(
            subdomain=subdomain,
            record_type=record_type,
            name=name,
            content=content,
            ttl=ttl,
            proxied=proxied
        )
        
        return jsonify({
            'code': 201,
            'message': '创建成功',
            'data': {'record': result}
        }), 201
    except Exception as e:
        return jsonify({'code': 500, 'message': f'创建失败: {str(e)}'}), 500


@open_api_bp.route('/dns-records/<record_id>', methods=['PUT'])
@api_auth_required
def update_dns_record(record_id):
    """更新DNS记录"""
    user = g.api_user
    data = request.get_json()
    
    # 查找记录
    record = DnsRecord.query.filter_by(cf_record_id=record_id).first()
    if not record:
        record = DnsRecord.query.get(record_id)
    
    if not record:
        return jsonify({'code': 404, 'message': '记录不存在'}), 404
    
    # 验证所有权
    subdomain = record.subdomain
    if not subdomain or subdomain.user_id != user.id:
        return jsonify({'code': 403, 'message': '无权操作此记录'}), 403
    
    # 更新记录
    try:
        from app.services.dns_service import DNSService
        dns_service = DNSService()
        
        result = dns_service.update_record(
            subdomain=subdomain,
            record_id=record.cf_record_id or str(record.id),
            content=data.get('content', record.content),
            ttl=data.get('ttl', record.ttl),
            proxied=data.get('proxied', record.proxied)
        )
        
        return jsonify({
            'code': 200,
            'message': '更新成功',
            'data': {'record': result}
        })
    except Exception as e:
        return jsonify({'code': 500, 'message': f'更新失败: {str(e)}'}), 500


@open_api_bp.route('/dns-records/<record_id>', methods=['DELETE'])
@api_auth_required
def delete_dns_record(record_id):
    """删除DNS记录"""
    user = g.api_user
    
    # 查找记录
    record = DnsRecord.query.filter_by(cf_record_id=record_id).first()
    if not record:
        record = DnsRecord.query.get(record_id)
    
    if not record:
        return jsonify({'code': 404, 'message': '记录不存在'}), 404
    
    # 验证所有权
    subdomain = record.subdomain
    if not subdomain or subdomain.user_id != user.id:
        return jsonify({'code': 403, 'message': '无权操作此记录'}), 403
    
    # 删除记录
    try:
        from app.services.dns_service import DNSService
        dns_service = DNSService()
        
        dns_service.delete_record(
            subdomain=subdomain,
            record_id=record.cf_record_id or str(record.id)
        )
        
        return jsonify({'code': 200, 'message': '删除成功'})
    except Exception as e:
        return jsonify({'code': 500, 'message': f'删除失败: {str(e)}'}), 500
