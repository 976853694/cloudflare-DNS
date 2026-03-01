"""
管理员二级域名管理路由
支持多 DNS 服务商
"""
import json
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload
from app import db
from app.models import User, Subdomain, DnsRecord, Setting, OperationLog
from app.services.dns import DnsApiError
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden
from app.utils.timezone import now as beijing_now
from app.utils.ip_utils import get_real_ip


@admin_bp.route('/subdomains', methods=['GET'])
@admin_required
def get_all_subdomains():
    """获取所有用户的二级域名列表"""
    current_user_id = int(get_jwt_identity())
    current_user = User.query.get(current_user_id)
    mask_private = current_user and current_user.role == 'demo'
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    user_id = request.args.get('user_id', type=int)
    domain_id = request.args.get('domain_id', type=int)
    status = request.args.get('status', type=int)
    search = request.args.get('search', '').strip()
    expired = request.args.get('expired', '').strip()
    
    # 使用 joinedload 预加载关联数据，避免 N+1 查询
    query = Subdomain.query.options(
        joinedload(Subdomain.user),
        joinedload(Subdomain.domain)
    )
    
    if user_id:
        query = query.filter(Subdomain.user_id == user_id)
    if domain_id:
        query = query.filter(Subdomain.domain_id == domain_id)
    if status is not None:
        query = query.filter(Subdomain.status == status)
    if search:
        # 支持按域名、用户名、用户邮箱搜索
        query = query.join(User, Subdomain.user_id == User.id).filter(
            db.or_(
                Subdomain.full_name.ilike(f'%{search}%'),
                Subdomain.name.ilike(f'%{search}%'),
                User.username.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%')
            )
        )
    if expired == '1':
        query = query.filter(Subdomain.expires_at < beijing_now())
    elif expired == '0':
        query = query.filter(
            db.or_(
                Subdomain.expires_at.is_(None),
                Subdomain.expires_at >= beijing_now()
            )
        )
    
    pagination = query.order_by(Subdomain.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    result = []
    for subdomain in pagination.items:
        data = subdomain.to_dict(mask_private=mask_private)
        data['user'] = {
            'id': subdomain.user.id,
            'username': subdomain.user.username,
            'email': '******' if mask_private else subdomain.user.email
        } if subdomain.user else None
        result.append(data)
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'subdomains': result,
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        }
    })


@admin_bp.route('/subdomains/<int:subdomain_id>', methods=['GET'])
@admin_required
def get_subdomain_detail(subdomain_id):
    """获取二级域名详情"""
    current_user_id = int(get_jwt_identity())
    current_user = User.query.get(current_user_id)
    mask_private = current_user and current_user.role == 'demo'
    
    subdomain = Subdomain.query.get(subdomain_id)
    
    if not subdomain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    data = subdomain.to_dict(include_records=True, mask_private=mask_private)
    data['user'] = {
        'id': subdomain.user.id,
        'username': subdomain.user.username,
        'email': '******' if mask_private else subdomain.user.email,
        'balance': float(subdomain.user.balance) if subdomain.user.balance else 0
    } if subdomain.user else None
    
    if subdomain.purchase_record:
        data['purchase_record'] = subdomain.purchase_record.to_dict()
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {'subdomain': data}
    })


@admin_bp.route('/subdomains/<int:subdomain_id>', methods=['PUT'])
@admin_required
@demo_forbidden
def update_subdomain(subdomain_id):
    """更新二级域名信息"""
    subdomain = Subdomain.query.get(subdomain_id)
    
    if not subdomain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    data = request.get_json()
    current_user_id = int(get_jwt_identity())
    
    old_status = subdomain.status
    old_expires = subdomain.expires_at
    
    if 'status' in data:
        subdomain.status = data['status']
    
    if 'expires_at' in data:
        if data['expires_at']:
            subdomain.expires_at = datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00'))
        else:
            subdomain.expires_at = None
    
    if 'extend_days' in data and data['extend_days']:
        extend_days = int(data['extend_days'])
        if extend_days > 0:
            if subdomain.expires_at:
                subdomain.expires_at = subdomain.expires_at + timedelta(days=extend_days)
            else:
                subdomain.expires_at = beijing_now() + timedelta(days=extend_days)
    
    db.session.commit()
    
    admin = User.query.get(current_user_id)
    detail_parts = []
    if old_status != subdomain.status:
        status_map = {0: '禁用', 1: '正常', 2: '待审核'}
        detail_parts.append(f'状态: {status_map.get(old_status, old_status)} -> {status_map.get(subdomain.status, subdomain.status)}')
    if old_expires != subdomain.expires_at:
        old_exp = old_expires.strftime('%Y-%m-%d') if old_expires else '永久'
        new_exp = subdomain.expires_at.strftime('%Y-%m-%d') if subdomain.expires_at else '永久'
        detail_parts.append(f'有效期: {old_exp} -> {new_exp}')
    
    if detail_parts:
        OperationLog.log(
            user_id=current_user_id,
            username=admin.username if admin else None,
            action=OperationLog.ACTION_UPDATE,
            target_type='subdomain',
            target_id=subdomain_id,
            detail=f'修改域名 {subdomain.full_name}: {", ".join(detail_parts)}',
            ip_address=get_real_ip()
        )
    
    return jsonify({
        'code': 200,
        'message': '域名更新成功',
        'data': {'subdomain': subdomain.to_dict()}
    })


@admin_bp.route('/subdomains/<int:subdomain_id>', methods=['DELETE'])
@admin_required
@demo_forbidden
def delete_subdomain(subdomain_id):
    """删除二级域名"""
    subdomain = Subdomain.query.get(subdomain_id)
    
    if not subdomain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    current_user_id = int(get_jwt_identity())
    full_name = subdomain.full_name
    domain = subdomain.domain
    
    # 获取 DNS 服务
    dns_service = domain.get_dns_service() if domain else None
    zone_id = domain.get_zone_id() if domain else None
    
    if dns_service and zone_id:
        for record in subdomain.records:
            try:
                dns_service.delete_record(zone_id, record.cf_record_id)
            except:
                pass
    
    # 删除关联的转移记录（避免外键约束错误）
    from app.models.domain_transfer import DomainTransfer
    DomainTransfer.query.filter_by(subdomain_id=subdomain_id).delete()
    
    db.session.delete(subdomain)
    db.session.commit()
    
    admin = User.query.get(current_user_id)
    OperationLog.log(
        user_id=current_user_id,
        username=admin.username if admin else None,
        action=OperationLog.ACTION_DELETE,
        target_type='subdomain',
        target_id=subdomain_id,
        detail=f'删除域名: {full_name}',
        ip_address=get_real_ip()
    )
    
    return jsonify({'code': 200, 'message': '域名删除成功'})


@admin_bp.route('/subdomains/batch-delete', methods=['POST'])
@admin_bp.route('/subdomains/batch', methods=['DELETE'])  # 新增 RESTful 风格路由
@admin_required
@demo_forbidden
def batch_delete_subdomains():
    """批量删除二级域名"""
    data = request.get_json()
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'code': 400, 'message': '请选择要删除的域名'}), 400
    
    current_user_id = int(get_jwt_identity())
    subdomains = Subdomain.query.filter(Subdomain.id.in_(ids)).all()
    deleted_count = 0
    
    # 先删除所有关联的转移记录（避免外键约束错误）
    from app.models.domain_transfer import DomainTransfer
    DomainTransfer.query.filter(DomainTransfer.subdomain_id.in_(ids)).delete(synchronize_session=False)
    
    for subdomain in subdomains:
        domain = subdomain.domain
        # 获取 DNS 服务
        dns_service = domain.get_dns_service() if domain else None
        zone_id = domain.get_zone_id() if domain else None
        
        if dns_service and zone_id:
            for record in subdomain.records:
                try:
                    dns_service.delete_record(zone_id, record.cf_record_id)
                except:
                    pass
        db.session.delete(subdomain)
        deleted_count += 1
    
    db.session.commit()
    
    admin = User.query.get(current_user_id)
    OperationLog.log(
        user_id=current_user_id,
        username=admin.username if admin else None,
        action=OperationLog.ACTION_DELETE,
        target_type='subdomain',
        detail=f'批量删除域名: {deleted_count}个',
        ip_address=get_real_ip()
    )
    
    return jsonify({'code': 200, 'message': f'成功删除 {deleted_count} 个域名'})


@admin_bp.route('/subdomains/batch-update', methods=['POST'])
@admin_bp.route('/subdomains/batch', methods=['PUT'])  # 新增 RESTful 风格路由
@admin_required
@demo_forbidden
def batch_update_subdomains():
    """批量更新二级域名状态"""
    data = request.get_json()
    ids = data.get('ids', [])
    status = data.get('status')
    extend_days = data.get('extend_days')
    
    if not ids:
        return jsonify({'code': 400, 'message': '请选择要操作的域名'}), 400
    
    current_user_id = int(get_jwt_identity())
    subdomains = Subdomain.query.filter(Subdomain.id.in_(ids)).all()
    updated_count = 0
    
    for subdomain in subdomains:
        if status is not None:
            subdomain.status = status
        if extend_days and extend_days > 0:
            if subdomain.expires_at:
                subdomain.expires_at = subdomain.expires_at + timedelta(days=extend_days)
            else:
                subdomain.expires_at = beijing_now() + timedelta(days=extend_days)
        updated_count += 1
    
    db.session.commit()
    
    admin = User.query.get(current_user_id)
    detail_parts = []
    if status is not None:
        status_map = {0: '禁用', 1: '正常', 2: '待审核'}
        detail_parts.append(f'状态设为{status_map.get(status, status)}')
    if extend_days:
        detail_parts.append(f'延期{extend_days}天')
    
    OperationLog.log(
        user_id=current_user_id,
        username=admin.username if admin else None,
        action=OperationLog.ACTION_UPDATE,
        target_type='subdomain',
        detail=f'批量更新域名({updated_count}个): {", ".join(detail_parts)}',
        ip_address=get_real_ip()
    )
    
    return jsonify({'code': 200, 'message': f'成功更新 {updated_count} 个域名'})


@admin_bp.route('/subdomains/<int:subdomain_id>/records', methods=['GET'])
@admin_required
def get_subdomain_records(subdomain_id):
    """获取二级域名的DNS记录列表"""
    current_user_id = int(get_jwt_identity())
    current_user = User.query.get(current_user_id)
    mask_private = current_user and current_user.role == 'demo'
    
    subdomain = Subdomain.query.get(subdomain_id)
    if not subdomain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    records = []
    for record in subdomain.records:
        record_data = record.to_dict()
        if mask_private:
            record_data['content'] = '******'
            record_data['cf_record_id'] = '******'
        records.append(record_data)
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'records': records,
            'subdomain': {
                'id': subdomain.id,
                'full_name': '******' if mask_private else subdomain.full_name
            }
        }
    })


@admin_bp.route('/subdomains/<int:subdomain_id>/send-expiry-email', methods=['POST'])
@admin_required
@demo_forbidden
def send_subdomain_expiry_email(subdomain_id):
    """发送域名到期提醒邮件"""
    from app.services.email import EmailService
    
    subdomain = Subdomain.query.get(subdomain_id)
    if not subdomain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    user = User.query.get(subdomain.user_id)
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    if not EmailService.is_configured():
        return jsonify({'code': 400, 'message': '邮件服务未配置'}), 400
    
    site_name = Setting.get('site_name', '六趣DNS')
    site_url = Setting.get('site_url', '')
    
    if subdomain.expires_at:
        remaining = (subdomain.expires_at - beijing_now()).days
        if remaining < 0:
            status_text = f'已过期 {abs(remaining)} 天'
        elif remaining == 0:
            status_text = '今天到期'
        else:
            status_text = f'还剩 {remaining} 天'
        expire_date = subdomain.expires_at.strftime('%Y-%m-%d %H:%M')
    else:
        status_text = '永久有效'
        expire_date = '永久'
    
    subject = f'【{site_name}】域名到期提醒'
    html = f'''
    <h2>域名到期提醒</h2>
    <p>您的域名 <strong>{subdomain.full_name}</strong> {status_text}。</p>
    <p>到期时间: {expire_date}</p>
    <p>请及时续费以避免DNS记录被清理。</p>
    <p><a href="{site_url}/user/domains">前往续费</a></p>
    '''
    
    try:
        EmailService.send(user.email, subject, html)
    except Exception as e:
        return jsonify({'code': 500, 'message': f'邮件发送失败: {str(e)}'}), 500
    
    current_user_id = int(get_jwt_identity())
    admin = User.query.get(current_user_id)
    OperationLog.log(
        user_id=current_user_id,
        username=admin.username if admin else None,
        action=OperationLog.ACTION_OTHER,
        target_type='subdomain',
        target_id=subdomain_id,
        detail=f'发送到期提醒邮件: {subdomain.full_name} -> {user.email}',
        ip_address=get_real_ip()
    )
    
    return jsonify({'code': 200, 'message': f'邮件已发送至 {user.email}'})


@admin_bp.route('/subdomains/<int:subdomain_id>/clear-dns', methods=['POST'])
@admin_required
@demo_forbidden
def clear_subdomain_dns(subdomain_id):
    """清理域名的所有DNS记录"""
    subdomain = Subdomain.query.get(subdomain_id)
    if not subdomain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    records = subdomain.records.all()
    if not records:
        return jsonify({'code': 400, 'message': '该域名没有DNS记录'}), 400
    
    deleted_count = 0
    domain = subdomain.domain
    
    # 获取 DNS 服务
    dns_service = domain.get_dns_service() if domain else None
    zone_id = domain.get_zone_id() if domain else None
    
    for record in records:
        try:
            if record.cf_record_id and dns_service and zone_id:
                dns_service.delete_record(zone_id, record.cf_record_id)
        except Exception:
            pass
        
        db.session.delete(record)
        deleted_count += 1
    
    db.session.commit()
    
    current_user_id = int(get_jwt_identity())
    admin = User.query.get(current_user_id)
    OperationLog.log(
        user_id=current_user_id,
        username=admin.username if admin else None,
        action=OperationLog.ACTION_DELETE,
        target_type='dns_record',
        target_id=subdomain_id,
        detail=f'清理域名DNS记录: {subdomain.full_name}, 共 {deleted_count} 条',
        ip_address=get_real_ip()
    )
    
    return jsonify({'code': 200, 'message': f'已删除 {deleted_count} 条DNS记录'})


@admin_bp.route('/subdomains/<int:subdomain_id>/ns', methods=['GET'])
@admin_required
def get_subdomain_ns(subdomain_id):
    """获取二级域名的NS信息"""
    current_user_id = int(get_jwt_identity())
    current_user = User.query.get(current_user_id)
    mask_private = current_user and current_user.role == 'demo'
    
    subdomain = Subdomain.query.get(subdomain_id)
    if not subdomain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    MASKED = '******'
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'subdomain_id': subdomain.id,
            'full_name': MASKED if mask_private else subdomain.full_name,
            'ns_mode': subdomain.ns_mode,
            'ns_servers': [MASKED] if mask_private and subdomain.ns_servers_list else subdomain.ns_servers_list,
            'ns_changed_at': subdomain.ns_changed_at.isoformat() if subdomain.ns_changed_at else None
        }
    })


@admin_bp.route('/subdomains/<int:subdomain_id>/ns', methods=['PUT'])
@admin_required
@demo_forbidden
def update_subdomain_ns(subdomain_id):
    """管理员修改二级域名的NS服务器"""
    subdomain = Subdomain.query.get(subdomain_id)
    if not subdomain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    data = request.get_json()
    ns_servers = data.get('ns_servers', [])
    
    current_user_id = int(get_jwt_identity())
    admin = User.query.get(current_user_id)
    
    if ns_servers:
        if not isinstance(ns_servers, list) or len(ns_servers) > 10:
            return jsonify({'code': 400, 'message': 'NS服务器数量需在1-10个之间'}), 400
        
        # 获取 DNS 服务
        dns_service = subdomain.domain.get_dns_service()
        if not dns_service:
            return jsonify({'code': 400, 'message': '域名未配置DNS服务'}), 400
        
        zone_id = subdomain.domain.get_zone_id()
        
        if subdomain.ns_mode == 0:
            for record in subdomain.records.all():
                try:
                    dns_service.delete_record(zone_id, record.cf_record_id)
                except:
                    pass
            DnsRecord.query.filter_by(subdomain_id=subdomain.id).delete()
        
        ns_created = 0
        
        # 对于 DNSPod/阿里云，需要提取子域名部分（去掉主域名后缀）
        api_record_name = subdomain.full_name
        domain_name = subdomain.domain.name
        if api_record_name.endswith('.' + domain_name):
            api_record_name = api_record_name[:-len('.' + domain_name)]
        elif api_record_name == domain_name:
            api_record_name = '@'
        
        for ns_server in ns_servers:
            try:
                dns_service.create_record(
                    zone_id=zone_id,
                    name=api_record_name,
                    record_type='NS',
                    value=ns_server,
                    ttl=3600,
                    proxied=False
                )
                ns_created += 1
            except:
                pass
        
        subdomain.ns_mode = 1
        subdomain.ns_servers = json.dumps(ns_servers)
        subdomain.ns_changed_at = beijing_now()
        
        OperationLog.log(
            user_id=current_user_id,
            username=admin.username if admin else None,
            action=OperationLog.ACTION_UPDATE,
            target_type='subdomain_ns',
            target_id=subdomain_id,
            detail=f'设置域名NS: {subdomain.full_name} -> {", ".join(ns_servers)}',
            ip_address=get_real_ip()
        )
    else:
        subdomain.ns_mode = 0
        subdomain.ns_servers = None
        subdomain.ns_changed_at = None
        
        OperationLog.log(
            user_id=current_user_id,
            username=admin.username if admin else None,
            action=OperationLog.ACTION_UPDATE,
            target_type='subdomain_ns',
            target_id=subdomain_id,
            detail=f'重置域名NS: {subdomain.full_name}',
            ip_address=get_real_ip()
        )
    
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': 'NS设置已更新',
        'data': {
            'ns_mode': subdomain.ns_mode,
            'ns_servers': subdomain.ns_servers_list,
            'ns_changed_at': subdomain.ns_changed_at.isoformat() if subdomain.ns_changed_at else None
        }
    })


@admin_bp.route('/subdomains/<int:subdomain_id>/ns', methods=['DELETE'])
@admin_required
@demo_forbidden
def reset_subdomain_ns(subdomain_id):
    """管理员重置二级域名的NS为Cloudflare"""
    subdomain = Subdomain.query.get(subdomain_id)
    if not subdomain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    if subdomain.ns_mode == 0:
        return jsonify({'code': 400, 'message': '该域名当前已使用默认NS'}), 400
    
    current_user_id = int(get_jwt_identity())
    admin = User.query.get(current_user_id)
    
    # 获取 DNS 服务
    dns_service = subdomain.domain.get_dns_service()
    if not dns_service:
        return jsonify({'code': 400, 'message': '域名未配置DNS服务'}), 400
    
    zone_id = subdomain.domain.get_zone_id()
    
    ns_deleted = 0
    try:
        result = dns_service.get_records(zone_id, subdomain=subdomain.full_name, type='NS')
        records = result.get('list', [])
        for record in records:
            try:
                dns_service.delete_record(zone_id, record.record_id)
                ns_deleted += 1
            except:
                pass
    except:
        pass
    
    subdomain.ns_mode = 0
    subdomain.ns_servers = None
    subdomain.ns_changed_at = None
    
    db.session.commit()
    
    OperationLog.log(
        user_id=current_user_id,
        username=admin.username if admin else None,
        action=OperationLog.ACTION_UPDATE,
        target_type='subdomain_ns',
        target_id=subdomain_id,
        detail=f'重置域名NS为Cloudflare: {subdomain.full_name}, 删除 {ns_deleted} 条NS记录',
        ip_address=get_real_ip()
    )
    
    return jsonify({'code': 200, 'message': f'NS已重置，已删除 {ns_deleted} 条NS记录'})
