"""
用户域名管理路由
支持多 DNS 服务商
"""
import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload
from app import db
from app.models import User, Domain, Subdomain, Plan, RedeemCode, PurchaseRecord, Announcement, AnnouncementRead, DnsRecord, OperationLog, CouponUsage
from app.services.dns import DnsApiError
from app.utils.validators import validate_subdomain_name
from app.utils.timezone import now as beijing_now
from app.routes.admin.decorators import demo_forbidden
from app.routes.decorators import phone_binding_required
from app.utils.ip_utils import get_real_ip

domain_bp = Blueprint('domain', __name__)


@domain_bp.route('/domains', methods=['GET'])
def get_domains():
    domains = Domain.query.filter_by(status=1, allow_register=1).all()
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'domains': [d.to_dict(include_stats=True) for d in domains]
        }
    })


@domain_bp.route('/domains/<int:domain_id>/check', methods=['GET'])
def check_subdomain_available(domain_id):
    """检查域名前缀是否可用（同时检查本地和上游）"""
    name = request.args.get('name', '').strip().lower()
    # 兼容 prefix 参数
    if not name:
        name = request.args.get('prefix', '').strip().lower()
    
    if not name:
        return jsonify({'code': 400, 'message': '请输入域名前缀'}), 400
    
    domain = Domain.query.get(domain_id)
    if not domain or not domain.is_active:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    # 1. 检查本地是否已被注册
    existing = Subdomain.query.filter_by(domain_id=domain_id, name=name).first()
    
    if existing:
        return jsonify({
            'code': 200,
            'data': {
                'available': False,
                'name': name,
                'full_name': f'{name}.{domain.name}',
                'message': '该域名前缀已被注册'
            }
        })
    
    # 2. 检查敏感词
    from app.services.sensitive_filter import SensitiveFilter
    if SensitiveFilter.contains_sensitive(name):
        return jsonify({
            'code': 200,
            'data': {
                'available': False,
                'name': name,
                'full_name': f'{name}.{domain.name}',
                'message': '该域名前缀包含敏感词'
            }
        })
    
    # 3. 如果有上游域名，检查上游是否可用
    if domain.upstream_domain_id and domain.dns_channel:
        if domain.dns_channel.provider_type == 'liuqu':
            try:
                service = domain.dns_channel.get_service()
                upstream_result = service.check_subdomain_available(domain.upstream_domain_id, name)
                if not upstream_result.get('available', False):
                    return jsonify({
                        'code': 200,
                        'data': {
                            'available': False,
                            'name': name,
                            'full_name': f'{name}.{domain.name}',
                            'message': upstream_result.get('message', '上游域名已被占用')
                        }
                    })
            except Exception as e:
                # 上游检查失败，记录日志但不阻止
                import logging
                logging.warning(f'上游域名检查失败: {str(e)}')
    
    return jsonify({
        'code': 200,
        'data': {
            'available': True,
            'name': name,
            'full_name': f'{name}.{domain.name}',
            'message': '该域名前缀可以注册'
        }
    })


@domain_bp.route('/subdomains', methods=['GET'])
@jwt_required()
def get_user_subdomains():
    user_id = int(get_jwt_identity())
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    domain_id = request.args.get('domain_id', type=int)
    
    # 使用 joinedload 预加载关联数据，避免 N+1 查询
    query = Subdomain.query.options(
        joinedload(Subdomain.domain),
        joinedload(Subdomain.plan)
    ).filter(Subdomain.user_id == user_id)
    
    if domain_id:
        query = query.filter(Subdomain.domain_id == domain_id)
    
    pagination = query.order_by(Subdomain.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'subdomains': [s.to_dict() for s in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        }
    })


@domain_bp.route('/subdomains', methods=['POST'])
@jwt_required()
def create_subdomain():
    """
    直接创建子域名 - 已废弃，请使用卡密兑换
    保留此接口仅供管理员或特殊情况使用
    """
    return jsonify({
        'code': 400, 
        'message': '请使用卡密兑换域名，前往"卡密兑换"页面'
    }), 400


@domain_bp.route('/subdomains/<int:subdomain_id>', methods=['GET'])
@jwt_required()
def get_subdomain(subdomain_id):
    user_id = int(get_jwt_identity())
    
    subdomain = Subdomain.query.filter_by(id=subdomain_id, user_id=user_id).first()
    
    if not subdomain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {'subdomain': subdomain.to_dict(include_records=True)}
    })


@domain_bp.route('/subdomains/<int:subdomain_id>', methods=['DELETE'])
@jwt_required()
@demo_forbidden
def delete_subdomain(subdomain_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    # 2FA验证（如果启用）
    if user and user.totp_enabled and user.totp_secret:
        totp_code = request.args.get('totp_code', '') or request.headers.get('X-TOTP-Code', '')
        if not totp_code:
            return jsonify({'code': 403, 'message': '此操作需要双因素认证验证码', 'require_2fa': True}), 403
        from app.services.totp_service import TOTPService
        if not TOTPService.verify(user.totp_secret, totp_code):
            if not user.use_backup_code(totp_code):
                return jsonify({'code': 401, 'message': '双因素认证验证码错误', 'require_2fa': True}), 401
    
    subdomain = Subdomain.query.filter_by(id=subdomain_id, user_id=user_id).first()
    
    if not subdomain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    # 获取 DNS 服务
    dns_service = subdomain.domain.get_dns_service()
    if dns_service:
        zone_id = subdomain.domain.get_zone_id()
        for record in subdomain.records.all():
            try:
                dns_service.delete_record(zone_id, record.cf_record_id)
            except Exception:
                pass
    
    # 删除关联的转移记录（避免外键约束错误）
    from app.models.domain_transfer import DomainTransfer
    DomainTransfer.query.filter_by(subdomain_id=subdomain_id).delete()
    
    db.session.delete(subdomain)
    db.session.commit()
    
    return jsonify({'code': 200, 'message': '域名删除成功'})


# ==================== 套餐和卡密相关 ====================

@domain_bp.route('/domains/<int:domain_id>/plans', methods=['GET'])
def get_domain_plans(domain_id):
    """获取域名下的可用套餐（支持多域名套餐）- 只返回付费套餐"""
    domain = Domain.query.get(domain_id)
    if not domain or not domain.is_active:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    # 查询关联了该域名的所有启用套餐（排除免费套餐）
    plans = Plan.query.filter(
        Plan.domains.any(id=domain_id),
        Plan.status == 1,
        Plan.is_free == False  # 只返回付费套餐
    ).order_by(Plan.sort_order, Plan.id).all()
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {'plans': [p.to_dict() for p in plans]}
    })


@domain_bp.route('/redeem', methods=['POST'])
@jwt_required()
@demo_forbidden
def redeem_code():
    """使用卡密充值余额"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or not user.is_active:
        return jsonify({'code': 403, 'message': '用户不可用'}), 403
    
    data = request.get_json()
    code_str = data.get('code', '').strip().upper()
    
    if not code_str:
        return jsonify({'code': 400, 'message': '请输入卡密'}), 400
    
    # 查找卡密
    redeem_code = RedeemCode.query.filter_by(code=code_str).first()
    
    if not redeem_code:
        return jsonify({'code': 404, 'message': '卡密不存在'}), 404
    
    if not redeem_code.is_valid:
        if redeem_code.status == RedeemCode.STATUS_USED:
            return jsonify({'code': 400, 'message': '卡密已被使用'}), 400
        elif redeem_code.status == RedeemCode.STATUS_DISABLED:
            return jsonify({'code': 400, 'message': '卡密已被禁用'}), 400
        else:
            return jsonify({'code': 400, 'message': '卡密已过期'}), 400
    
    amount = float(redeem_code.amount)
    
    # 充值余额
    if amount == -1:
        # 无限余额卡
        user.balance = -1
        amount_text = '无限'
    else:
        if user.balance == -1:
            # 已经是无限余额，不需要充值
            return jsonify({'code': 400, 'message': '您已拥有无限余额'}), 400
        user.balance = user.balance + redeem_code.amount
        amount_text = f'¥{amount}'
    
    # 更新卡密状态
    redeem_code.status = RedeemCode.STATUS_USED
    redeem_code.used_by = user_id
    redeem_code.used_at = beijing_now()
    
    # 记录操作日志
    OperationLog.log(
        user_id=user_id,
        username=user.username,
        action=OperationLog.ACTION_OTHER,
        target_type='redeem_code',
        detail=f'使用卡密充值: {amount_text}',
        ip_address=get_real_ip()
    )
    
    db.session.commit()
    
    # 记录余额充值活动
    from app.services.activity_tracker import ActivityTracker
    ActivityTracker.log(user_id, 'balance_recharge', {
        'amount': amount,
        'amount_text': amount_text,
        'code': code_str
    })
    
    return jsonify({
        'code': 200,
        'message': f'充值成功，到账 {amount_text}',
        'data': {
            'amount': amount,
            'balance': float(user.balance),
            'balance_text': user.balance_text
        }
    })


@domain_bp.route('/redeem/verify', methods=['POST'])
@jwt_required()
def verify_redeem_code():
    """验证卡密（不使用）"""
    data = request.get_json()
    code_str = data.get('code', '').strip().upper()
    
    if not code_str:
        return jsonify({'code': 400, 'message': '请输入卡密'}), 400
    
    redeem_code = RedeemCode.query.filter_by(code=code_str).first()
    
    if not redeem_code:
        return jsonify({'code': 404, 'message': '卡密不存在'}), 404
    
    if not redeem_code.is_valid:
        if redeem_code.status == RedeemCode.STATUS_USED:
            return jsonify({'code': 400, 'message': '卡密已被使用'}), 400
        elif redeem_code.status == RedeemCode.STATUS_DISABLED:
            return jsonify({'code': 400, 'message': '卡密已被禁用'}), 400
        else:
            return jsonify({'code': 400, 'message': '卡密已过期'}), 400
    
    return jsonify({
        'code': 200,
        'message': '卡密有效',
        'data': {
            'amount': float(redeem_code.amount),
            'amount_text': redeem_code.amount_text
        }
    })


@domain_bp.route('/purchase', methods=['POST'])
@jwt_required()
@phone_binding_required
@demo_forbidden
def purchase_subdomain():
    """使用余额购买套餐创建域名"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or not user.is_active:
        return jsonify({'code': 403, 'message': '用户不可用'}), 403
    
    # 检查用户域名数量限制
    current_count = user.subdomains.count()
    if user.max_domains != -1 and current_count >= user.max_domains:
        return jsonify({
            'code': 403, 
            'message': f'已达到域名数量上限（当前 {current_count}/{user.max_domains} 个）'
        }), 403
    
    data = request.get_json()
    plan_id = data.get('plan_id')
    subdomain_name = data.get('name', '').strip().lower()
    coupon_code = data.get('coupon_code', '').strip().upper()
    
    if not plan_id:
        return jsonify({'code': 400, 'message': '请选择套餐'}), 400
    
    if not subdomain_name:
        return jsonify({'code': 400, 'message': '请输入域名前缀'}), 400
    
    plan = Plan.query.get(plan_id)
    if not plan or not plan.is_active:
        return jsonify({'code': 404, 'message': '套餐不存在或已下架'}), 404
    
    # 检查购买次数限制
    from app.services.plan_service import PlanService
    can_buy, buy_error, buy_data = PlanService.can_purchase(user_id, plan_id)
    if not can_buy:
        error_msg = buy_error.split('|')[1] if '|' in buy_error else buy_error
        return jsonify({'code': 400, 'message': error_msg, 'data': buy_data}), 400
    
    # 套餐现在可以关联多个域名，需要从请求中获取用户选择的域名
    domain_id = data.get('domain_id')
    if not domain_id:
        # 如果没有指定域名，使用套餐关联的第一个域名（兼容旧版）
        if plan.domains:
            domain = plan.domains[0]
        else:
            return jsonify({'code': 400, 'message': '套餐未关联任何域名'}), 400
    else:
        # 验证指定的域名是否在套餐关联的域名列表中
        domain = Domain.query.get(domain_id)
        if not domain or domain not in plan.domains:
            return jsonify({'code': 400, 'message': '套餐与域名不匹配'}), 400
    
    if not domain.is_active:
        return jsonify({'code': 400, 'message': '域名不可用'}), 400
    
    # 处理优惠券 - 使用统一验证器修复安全漏洞
    from decimal import Decimal
    from app.services.coupon_validator import CouponValidator
    
    coupon = None
    discount = Decimal('0')
    final_price = Decimal(str(plan.price))
    
    if coupon_code:
        # 使用统一验证器进行完整验证，包括域名排除检查
        validation_result = CouponValidator.validate_coupon_for_purchase(
            coupon_code=coupon_code,
            user_id=user_id,
            original_price=plan.price,
            product_type='domain',
            plan_id=plan_id,
            domain_id=domain.id  # 关键修复：添加域名ID验证
        )
        
        # 记录验证尝试
        CouponValidator.log_validation_attempt(
            user_id=user_id,
            coupon_code=coupon_code,
            domain_id=domain.id,
            result=validation_result,
            context="domain_purchase",
            ip_address=get_real_ip()
        )
        
        if validation_result.is_valid:
            coupon = validation_result.coupon
            discount = validation_result.discount
            final_price = validation_result.final_price
        else:
            # 优惠码验证失败，返回错误
            return jsonify({
                'code': 400, 
                'message': validation_result.error_message
            }), 400
    
    # 检查余额
    if not user.can_afford(float(final_price)):
        return jsonify({'code': 400, 'message': f'余额不足，当前余额 {user.balance_text}，需要 ¥{final_price}'}), 400
    
    # 验证域名前缀
    name_len = len(subdomain_name)
    if name_len < plan.min_length or name_len > plan.max_length:
        return jsonify({'code': 400, 'message': f'域名前缀长度需在 {plan.min_length}-{plan.max_length} 个字符之间'}), 400
    
    if not validate_subdomain_name(subdomain_name, min_len=plan.min_length, max_len=plan.max_length):
        return jsonify({'code': 400, 'message': '域名前缀格式不正确，只能包含字母、数字和连字符，且不能以连字符开头或结尾'}), 400
    
    # 检查域名是否已存在
    if Subdomain.query.filter_by(domain_id=domain.id, name=subdomain_name).first():
        return jsonify({'code': 409, 'message': '该域名前缀已被占用'}), 409
    
    full_name = f"{subdomain_name}.{domain.name}"
    # -1 表示永久有效
    expires_at = None if plan.duration_days == -1 else beijing_now() + timedelta(days=plan.duration_days)
    
    # ========== 六趣DNS上游购买 ==========
    upstream_subdomain_id = None
    if plan.upstream_plan_id and domain.upstream_domain_id and domain.dns_channel:
        if domain.dns_channel.provider_type == 'liuqu':
            try:
                service = domain.dns_channel.get_service()
                
                # 先检查上游是否可用
                check_result = service.check_subdomain_available(domain.upstream_domain_id, subdomain_name)
                if not check_result.get('available', False):
                    return jsonify({'code': 409, 'message': f'上游域名不可用: {check_result.get("message", "已被占用")}'}), 409
                
                # 调用上游购买
                upstream_result = service.purchase_subdomain(
                    domain_id=domain.upstream_domain_id,
                    prefix=subdomain_name,
                    plan_id=plan.upstream_plan_id
                )
                upstream_subdomain_id = upstream_result.get('subdomain', {}).get('id')
                
                # 使用上游返回的过期时间
                upstream_expires = upstream_result.get('subdomain', {}).get('expires_at')
                if upstream_expires:
                    from datetime import datetime as dt
                    try:
                        expires_at = dt.fromisoformat(upstream_expires.replace('Z', '+00:00'))
                    except:
                        pass
                        
            except DnsApiError as e:
                return jsonify({'code': 500, 'message': f'上游购买失败: {str(e)}'}), 500
            except Exception as e:
                return jsonify({'code': 500, 'message': f'上游购买异常: {str(e)}'}), 500
    
    # 扣除余额（使用优惠后的价格）
    user.deduct_balance(float(final_price))
    
    # 创建子域名
    subdomain = Subdomain(
        user_id=user_id,
        domain_id=domain.id,
        plan_id=plan.id,
        name=subdomain_name,
        full_name=full_name,
        expires_at=expires_at,
        upstream_subdomain_id=upstream_subdomain_id
    )
    db.session.add(subdomain)
    db.session.flush()  # 获取subdomain.id
    
    # 创建购买记录
    purchase_record = PurchaseRecord(
        user_id=user_id,
        subdomain_id=subdomain.id,
        plan_id=plan.id,
        plan_name=plan.name,
        domain_name=domain.name,
        subdomain_name=full_name,
        price=float(final_price),
        duration_days=plan.duration_days,
        payment_method='balance'
    )
    db.session.add(purchase_record)
    db.session.flush()  # 获取 purchase_record.id
    
    # ========== 托管商收益分成 ==========
    if domain.is_host_owned and domain.owner_id:
        from app.models import Setting
        from app.models.host_transaction import HostTransaction
        
        host = User.query.get(domain.owner_id)
        if host and host.is_host:
            # 获取抽成比例
            default_commission = Setting.get('host_default_commission', 10)
            commission_rate = host.get_effective_commission_rate(default_commission)
            
            # 创建交易记录并计算收益
            transaction = HostTransaction.create_transaction(
                host_id=host.id,
                purchase_record_id=purchase_record.id,
                domain_id=domain.id,
                total_amount=float(final_price),
                commission_rate=commission_rate
            )
            db.session.add(transaction)
            
            # 增加托管商余额
            host.add_host_balance(transaction.host_earnings)
    
    # 记录优惠券使用
    if coupon and discount > 0:
        coupon_usage = CouponUsage(
            coupon_id=coupon.id,
            user_id=user_id,
            original_price=plan.price,
            discount_amount=float(discount),
            final_price=float(final_price)
        )
        db.session.add(coupon_usage)
        coupon.used_count += 1
    
    # 记录操作日志
    detail_text = f'购买域名: {full_name}, 套餐: {plan.name}, 金额: ¥{final_price}'
    if coupon and discount > 0:
        detail_text += f' (优惠: ¥{discount}, 优惠码: {coupon.code})'
    if upstream_subdomain_id:
        detail_text += f' (上游ID: {upstream_subdomain_id})'
    
    OperationLog.log(
        user_id=user_id,
        username=user.username,
        action=OperationLog.ACTION_CREATE,
        target_type='subdomain',
        target_id=subdomain.id,
        target_name=full_name,
        detail=detail_text,
        ip_address=get_real_ip()
    )
    
    db.session.commit()
    
    # 记录域名创建活动
    from app.services.activity_tracker import ActivityTracker
    ActivityTracker.log(user_id, 'domain_create', {
        'subdomain_id': subdomain.id,
        'full_name': full_name,
        'plan_name': plan.name,
        'price': float(final_price)
    })
    
    return jsonify({
        'code': 200,
        'message': '购买成功',
        'data': {
            'subdomain': subdomain.to_dict(),
            'plan': plan.to_dict(),
            'balance': float(user.balance),
            'balance_text': user.balance_text
        }
    })


@domain_bp.route('/subdomains/<int:subdomain_id>/renew', methods=['POST'])
@jwt_required()
@phone_binding_required
@demo_forbidden
def renew_subdomain(subdomain_id):
    """续费域名"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or not user.is_active:
        return jsonify({'code': 403, 'message': '用户不可用'}), 403
    
    subdomain = Subdomain.query.filter_by(id=subdomain_id, user_id=user_id).first()
    if not subdomain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    # 永久域名不需要续费
    if subdomain.expires_at is None:
        return jsonify({'code': 400, 'message': '该域名为永久有效，无需续费'}), 400
    
    data = request.get_json()
    plan_id = data.get('plan_id')
    
    if not plan_id:
        return jsonify({'code': 400, 'message': '请选择续费套餐'}), 400
    
    plan = Plan.query.get(plan_id)
    if not plan or not plan.is_active:
        return jsonify({'code': 404, 'message': '套餐不存在或已下架'}), 404
    
    # 确保套餐关联了该主域名
    if subdomain.domain_id not in [d.id for d in plan.domains]:
        return jsonify({'code': 400, 'message': '套餐与域名不匹配'}), 400
    
    # 永久套餐不能用于续费
    if plan.duration_days == -1:
        return jsonify({'code': 400, 'message': '永久套餐不支持续费'}), 400
    
    # 检查续费时间窗口和购买次数限制
    from app.services.plan_service import PlanService
    can_renew, renew_error, renew_data = PlanService.can_renew(subdomain_id, plan_id)
    if not can_renew:
        error_msg = renew_error.split('|')[1] if '|' in renew_error else renew_error
        return jsonify({'code': 400, 'message': error_msg, 'data': renew_data}), 400
    
    # ========== 免费套餐和收费套餐分流处理 ==========
    is_free_plan = plan.is_free or float(plan.price) == 0
    
    # 收费套餐：检查余额
    if not is_free_plan:
        if not user.can_afford(plan.price):
            return jsonify({'code': 400, 'message': f'余额不足，当前余额 {user.balance_text}，需要 ¥{plan.price}'}), 400
    
    # ========== 六趣DNS上游续费 ==========
    domain = subdomain.domain
    if (subdomain.upstream_subdomain_id and plan.upstream_plan_id and 
        domain.dns_channel and domain.dns_channel.provider_type == 'liuqu'):
        try:
            service = domain.dns_channel.get_service()
            
            # 调用上游续费
            upstream_result = service.renew_subdomain(
                subdomain_id=subdomain.upstream_subdomain_id,
                plan_id=plan.upstream_plan_id
            )
            
            # 使用上游返回的过期时间
            upstream_expires = upstream_result.get('expires_at')
            if upstream_expires:
                from datetime import datetime as dt
                try:
                    subdomain.expires_at = dt.fromisoformat(upstream_expires.replace('Z', '+00:00'))
                except:
                    # 如果解析失败，使用本地计算
                    base_time = subdomain.expires_at if subdomain.expires_at > beijing_now() else beijing_now()
                    subdomain.expires_at = base_time + timedelta(days=plan.duration_days)
            else:
                base_time = subdomain.expires_at if subdomain.expires_at > beijing_now() else beijing_now()
                subdomain.expires_at = base_time + timedelta(days=plan.duration_days)
                
        except DnsApiError as e:
            return jsonify({'code': 500, 'message': f'上游续费失败: {str(e)}'}), 500
        except Exception as e:
            return jsonify({'code': 500, 'message': f'上游续费异常: {str(e)}'}), 500
    else:
        # 非上游域名，本地计算到期时间
        base_time = subdomain.expires_at if subdomain.expires_at > beijing_now() else beijing_now()
        subdomain.expires_at = base_time + timedelta(days=plan.duration_days)
    
    # 扣除余额（仅收费套餐）
    if not is_free_plan:
        user.deduct_balance(plan.price)
    
    subdomain.plan_id = plan.id
    
    # 如果域名已停用，恢复启用状态
    if subdomain.status == 0:
        subdomain.status = 1
        # 恢复DNS记录状态
        from app.models import DnsRecord
        DnsRecord.query.filter_by(subdomain_id=subdomain.id).update({'status': 1})
    
    # 创建续费购买记录
    purchase_record = PurchaseRecord(
        user_id=user_id,
        subdomain_id=subdomain.id,
        plan_id=plan.id,
        plan_name=f'{plan.name}({"免费续费" if is_free_plan else "续费"})',
        domain_name=subdomain.domain.name,
        subdomain_name=subdomain.full_name,
        price=plan.price,
        duration_days=plan.duration_days,
        payment_method='free' if is_free_plan else 'balance'
    )
    db.session.add(purchase_record)
    db.session.flush()  # 获取 purchase_record.id
    
    # ========== 托管商收益分成（续费，仅收费套餐） ==========
    domain = subdomain.domain
    if not is_free_plan and domain.is_host_owned and domain.owner_id:
        from app.models import Setting
        from app.models.host_transaction import HostTransaction
        
        host = User.query.get(domain.owner_id)
        if host and host.is_host:
            # 获取抽成比例
            default_commission = Setting.get('host_default_commission', 10)
            commission_rate = host.get_effective_commission_rate(default_commission)
            
            # 创建交易记录并计算收益
            transaction = HostTransaction.create_transaction(
                host_id=host.id,
                purchase_record_id=purchase_record.id,
                domain_id=domain.id,
                total_amount=float(plan.price),
                commission_rate=commission_rate
            )
            db.session.add(transaction)
            
            # 增加托管商余额
            host.add_host_balance(transaction.host_earnings)
    
    # 记录操作日志
    if is_free_plan:
        detail_text = f'免费续费域名: {subdomain.full_name}, 套餐: {plan.name}, 延长{plan.duration_days}天'
    else:
        detail_text = f'续费域名: {subdomain.full_name}, 套餐: {plan.name}, 金额: ¥{plan.price}, 延长{plan.duration_days}天'
    if subdomain.upstream_subdomain_id:
        detail_text += f' (上游ID: {subdomain.upstream_subdomain_id})'
    
    OperationLog.log(
        user_id=user_id,
        username=user.username,
        action=OperationLog.ACTION_UPDATE,
        target_type='subdomain',
        target_id=subdomain.id,
        target_name=subdomain.full_name,
        detail=detail_text,
        ip_address=get_real_ip()
    )
    
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '免费续费成功' if is_free_plan else '续费成功',
        'data': {
            'subdomain': subdomain.to_dict(),
            'expires_at': subdomain.expires_at.isoformat() if subdomain.expires_at else None,
            'balance': float(user.balance),
            'balance_text': user.balance_text,
            'is_free_renew': is_free_plan
        }
    })


@domain_bp.route('/subdomains/<int:subdomain_id>/renew-plans', methods=['GET'])
@jwt_required()
def get_renew_plans(subdomain_id):
    """获取可用的续费套餐"""
    user_id = int(get_jwt_identity())
    
    subdomain = Subdomain.query.filter_by(id=subdomain_id, user_id=user_id).first()
    if not subdomain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    # 永久域名不需要续费
    if subdomain.expires_at is None:
        return jsonify({'code': 400, 'message': '该域名为永久有效，无需续费'}), 400
    
    # 获取关联该主域名的非永久套餐
    plans = Plan.query.filter(
        Plan.domains.any(id=subdomain.domain_id),
        Plan.status == 1,
        Plan.duration_days != -1
    ).order_by(Plan.sort_order, Plan.id).all()
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'plans': [p.to_dict() for p in plans],
            'subdomain': subdomain.to_dict()
        }
    })


@domain_bp.route('/subdomains/<int:subdomain_id>/auto-renew', methods=['PUT'])
@jwt_required()
@demo_forbidden
def toggle_auto_renew(subdomain_id):
    """开启/关闭自动续费"""
    user_id = int(get_jwt_identity())
    
    subdomain = Subdomain.query.filter_by(id=subdomain_id, user_id=user_id).first()
    if not subdomain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    # 永久域名不需要自动续费
    if subdomain.expires_at is None:
        return jsonify({'code': 400, 'message': '该域名为永久有效，无需设置自动续费'}), 400
    
    data = request.get_json()
    auto_renew = data.get('auto_renew', 0)
    
    subdomain.auto_renew = 1 if auto_renew else 0
    db.session.commit()
    
    status_text = '开启' if subdomain.auto_renew else '关闭'
    return jsonify({
        'code': 200,
        'message': f'自动续费已{status_text}',
        'data': {
            'auto_renew': subdomain.auto_renew
        }
    })


@domain_bp.route('/purchase-records', methods=['GET'])
@jwt_required()
def get_user_purchase_records():
    """获取当前用户的购买记录"""
    user_id = int(get_jwt_identity())
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = PurchaseRecord.query.filter_by(user_id=user_id)
    
    pagination = query.order_by(PurchaseRecord.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'records': [r.to_dict() for r in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        }
    })


@domain_bp.route('/announcements', methods=['GET'])
@jwt_required(optional=True)
def get_public_announcements():
    """获取已发布的公告列表"""
    identity = get_jwt_identity()
    user_id = int(identity) if identity else None
    announcements = Announcement.query.filter_by(status=1).order_by(
        Announcement.is_pinned.desc(), Announcement.created_at.desc()
    ).limit(20).all()
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {'announcements': [a.to_dict(user_id=user_id) for a in announcements]}
    })


@domain_bp.route('/announcements/unread', methods=['GET'])
@jwt_required()
def get_unread_announcements():
    """获取未读公告（用于弹窗和角标）"""
    user_id = int(get_jwt_identity())
    
    # 获取用户已读的公告ID列表
    read_ids = [r.announcement_id for r in AnnouncementRead.query.filter_by(user_id=user_id).all()]
    
    # 获取未读的已发布公告
    query = Announcement.query.filter_by(status=1)
    if read_ids:
        query = query.filter(~Announcement.id.in_(read_ids))
    
    announcements = query.order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc()).all()
    
    # 分离弹窗公告和普通公告
    popup_announcements = [a.to_dict(user_id=user_id) for a in announcements if a.is_popup]
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'unread_count': len(announcements),
            'popup_announcements': popup_announcements,
            'announcements': [a.to_dict(user_id=user_id) for a in announcements]
        }
    })


@domain_bp.route('/announcements/<int:ann_id>/read', methods=['POST'])
@jwt_required()
def mark_announcement_read(ann_id):
    """标记公告为已读"""
    user_id = int(get_jwt_identity())
    
    announcement = Announcement.query.get(ann_id)
    if not announcement:
        return jsonify({'code': 404, 'message': '公告不存在'}), 404
    
    # 检查是否已读
    existing = AnnouncementRead.query.filter_by(user_id=user_id, announcement_id=ann_id).first()
    if not existing:
        read_record = AnnouncementRead(user_id=user_id, announcement_id=ann_id)
        db.session.add(read_record)
        db.session.commit()
    
    return jsonify({'code': 200, 'message': '已标记为已读'})


# ==================== NS 修改相关 ====================

@domain_bp.route('/subdomains/<int:subdomain_id>/ns', methods=['PUT'])
@jwt_required()
@demo_forbidden
def update_subdomain_ns(subdomain_id):
    """修改二级域名的NS服务器，同时删除所有DNS记录"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    data = request.get_json()
    
    subdomain = Subdomain.query.filter_by(id=subdomain_id, user_id=user_id).first()
    if not subdomain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    if not subdomain.is_active:
        return jsonify({'code': 400, 'message': '域名已停用'}), 400
    
    if subdomain.is_expired:
        return jsonify({'code': 400, 'message': '域名已过期'}), 400
    
    # 检查域名是否允许NS转移
    if not subdomain.domain.allow_ns_transfer:
        return jsonify({'code': 403, 'message': '该域名不允许NS转移'}), 403
    ns_servers = data.get('ns_servers', [])
    
    if not ns_servers or not isinstance(ns_servers, list):
        return jsonify({'code': 400, 'message': '请提供NS服务器列表'}), 400
    
    if len(ns_servers) < 1 or len(ns_servers) > 10:
        return jsonify({'code': 400, 'message': 'NS服务器数量需在1-10个之间'}), 400
    
    # 验证NS服务器格式
    for ns in ns_servers:
        if not ns or not isinstance(ns, str) or len(ns) > 255:
            return jsonify({'code': 400, 'message': 'NS服务器格式不正确'}), 400
    
    # 获取 DNS 服务
    dns_service = subdomain.domain.get_dns_service()
    if not dns_service:
        return jsonify({'code': 400, 'message': '域名未配置DNS服务'}), 400
    
    zone_id = subdomain.domain.get_zone_id()
    
    # 删除 DNS 服务商上的所有DNS记录
    deleted_count = 0
    failed_records = []
    
    for record in subdomain.records.all():
        try:
            dns_service.delete_record(zone_id, record.cf_record_id)
            deleted_count += 1
        except Exception as e:
            failed_records.append({
                'id': record.id,
                'name': record.name,
                'error': str(e)
            })
    
    # 删除本地数据库中的DNS记录
    DnsRecord.query.filter_by(subdomain_id=subdomain.id).delete()
    
    # 在 DNS 服务商上添加NS记录
    ns_created = 0
    ns_failed = []
    
    # 对于 DNSPod/阿里云，需要提取子域名部分（去掉主域名后缀）
    api_record_name = subdomain.full_name
    domain_name = subdomain.domain.name
    if api_record_name.endswith('.' + domain_name):
        api_record_name = api_record_name[:-len('.' + domain_name)]
    elif api_record_name == domain_name:
        api_record_name = '@'
    
    for ns_server in ns_servers:
        try:
            result = dns_service.create_record(
                zone_id=zone_id,
                name=api_record_name,
                record_type='NS',
                value=ns_server,
                ttl=3600,
                proxied=False
            )
            ns_created += 1
        except Exception as e:
            ns_failed.append({'ns': ns_server, 'error': str(e)})
    
    # 更新NS状态
    subdomain.ns_mode = 1
    subdomain.ns_servers = json.dumps(ns_servers)
    subdomain.ns_changed_at = beijing_now()
    
    db.session.commit()
    
    result_msg = f'NS修改成功，已删除 {deleted_count} 条DNS记录，已添加 {ns_created} 条NS记录'
    if failed_records:
        result_msg += f'，{len(failed_records)} 条记录删除失败'
    if ns_failed:
        result_msg += f'，{len(ns_failed)} 条NS记录添加失败'
    
    return jsonify({
        'code': 200,
        'message': result_msg,
        'data': {
            'subdomain': subdomain.to_dict(),
            'deleted_count': deleted_count,
            'ns_created': ns_created,
            'failed_records': failed_records,
            'ns_failed': ns_failed
        }
    })


@domain_bp.route('/subdomains/<int:subdomain_id>/ns/reset', methods=['POST'])
@jwt_required()
@demo_forbidden
def reset_subdomain_ns(subdomain_id):
    """重置NS为Cloudflare（恢复管理权）"""
    user_id = int(get_jwt_identity())
    
    subdomain = Subdomain.query.filter_by(id=subdomain_id, user_id=user_id).first()
    if not subdomain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    if subdomain.ns_mode == 0:
        return jsonify({'code': 400, 'message': '该域名当前使用默认NS，无需重置'}), 400
    
    # 获取 DNS 服务
    dns_service = subdomain.domain.get_dns_service()
    if not dns_service:
        return jsonify({'code': 400, 'message': '域名未配置DNS服务'}), 400
    
    zone_id = subdomain.domain.get_zone_id()
    
    # 对于 DNSPod/阿里云，需要提取子域名部分（去掉主域名后缀）
    api_record_name = subdomain.full_name
    domain_name = subdomain.domain.name
    if api_record_name.endswith('.' + domain_name):
        api_record_name = api_record_name[:-len('.' + domain_name)]
    elif api_record_name == domain_name:
        api_record_name = '@'
    
    # 删除 DNS 服务商上的NS记录
    ns_deleted = 0
    try:
        # 获取该二级域名的所有NS记录
        result = dns_service.get_records(zone_id, subdomain=api_record_name, type='NS')
        records = result.get('list', [])
        for record in records:
            try:
                dns_service.delete_record(zone_id, record.record_id)
                ns_deleted += 1
            except:
                pass
    except:
        pass
    
    # 重置NS状态
    subdomain.ns_mode = 0
    subdomain.ns_servers = None
    subdomain.ns_changed_at = None
    
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': f'NS已重置，已删除 {ns_deleted} 条NS记录，您可以重新添加DNS记录',
        'data': {'subdomain': subdomain.to_dict()}
    })


# ==================== 续费信息 ====================

@domain_bp.route('/subdomains/<int:subdomain_id>/renewal-info', methods=['GET'])
@jwt_required()
def get_renewal_info(subdomain_id):
    """获取续费信息（包括购买次数、续费窗口等）"""
    user_id = int(get_jwt_identity())
    
    from app.services.plan_service import PlanService
    
    success, error, data = PlanService.get_renewal_info(subdomain_id, user_id)
    
    if not success:
        error_code = error.split('|')[0] if '|' in error else 'ERROR'
        error_msg = error.split('|')[1] if '|' in error else error
        return jsonify({'code': 400, 'message': error_msg, 'error_code': error_code}), 400
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': data
    })



# ==================== 公开统计 API ====================

@domain_bp.route('/stats/public', methods=['GET'])
def get_public_stats():
    """获取公开统计数据（首页展示用）"""
    try:
        # 统计注册用户数
        users_count = User.query.filter(User.status == 1).count()
        
        # 统计域名数量（已注册的子域名）
        domains_count = Subdomain.query.filter(Subdomain.status == 1).count()
        
        # 统计解析记录数
        records_count = DnsRecord.query.count()
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {
                'users': users_count,
                'domains': domains_count,
                'records': records_count
            }
        })
    except Exception as e:
        # 出错时返回默认值
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {
                'users': 0,
                'domains': 0,
                'records': 0
            }
        })
