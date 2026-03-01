"""
管理员域名管理路由
"""
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from app import db
from app.models import Domain, CloudflareAccount, DnsChannel, User
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden


@admin_bp.route('/domains', methods=['GET'])
@admin_required
def get_all_domains():
    """获取所有域名"""
    current_user_id = int(get_jwt_identity())
    current_user = User.query.get(current_user_id)
    mask_private = current_user and current_user.role == 'demo'
    
    domains = Domain.query.all()
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {'domains': [d.to_admin_dict(mask_private=mask_private) for d in domains]}
    })


@admin_bp.route('/domains', methods=['POST'])
@admin_required
@demo_forbidden
def create_domain():
    """创建域名"""
    data = request.get_json()
    
    name = data.get('name', '').strip().lower()
    zone_id = data.get('zone_id', '').strip() or data.get('cf_zone_id', '').strip()
    allow_register = data.get('allow_register', True)
    description = data.get('description', '').strip()
    
    if not name or not zone_id:
        return jsonify({'code': 400, 'message': '请填写域名和Zone ID'}), 400
    
    if Domain.query.filter_by(name=name).first():
        return jsonify({'code': 409, 'message': '域名已存在'}), 409
    
    # 支持新的 dns_channel_id 和旧的 cf_account_id
    dns_channel_id = data.get('dns_channel_id')
    cf_account_id = data.get('cf_account_id')
    
    if dns_channel_id:
        channel = DnsChannel.query.get(dns_channel_id)
        if not channel:
            return jsonify({'code': 404, 'message': '渠道不存在'}), 404
    elif cf_account_id:
        cf_account = CloudflareAccount.query.get(cf_account_id)
        if not cf_account:
            return jsonify({'code': 404, 'message': 'Cloudflare账户不存在'}), 404
    
    domain = Domain(
        name=name,
        zone_id=zone_id,
        cf_zone_id=zone_id,  # 兼容旧字段
        dns_channel_id=dns_channel_id,
        cf_account_id=cf_account_id,
        allow_register=1 if allow_register else 0,
        description=description
    )
    
    db.session.add(domain)
    db.session.commit()
    
    return jsonify({
        'code': 201,
        'message': '域名添加成功',
        'data': {'domain': domain.to_admin_dict()}
    }), 201


@admin_bp.route('/domains/<int:domain_id>', methods=['PUT'])
@admin_required
@demo_forbidden
def update_domain(domain_id):
    """更新域名"""
    domain = Domain.query.get(domain_id)
    
    if not domain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    data = request.get_json()
    
    if 'allow_register' in data:
        domain.allow_register = 1 if data['allow_register'] else 0
    if 'status' in data:
        domain.status = data['status']
    if 'description' in data:
        domain.description = data['description']
    
    # 更新 Zone ID（支持新旧字段）
    if 'zone_id' in data:
        domain.zone_id = data['zone_id']
        domain.cf_zone_id = data['zone_id']
    elif 'cf_zone_id' in data:
        domain.cf_zone_id = data['cf_zone_id']
        domain.zone_id = data['cf_zone_id']
    
    # 更新渠道关联
    if 'dns_channel_id' in data:
        if data['dns_channel_id']:
            channel = DnsChannel.query.get(data['dns_channel_id'])
            if not channel:
                return jsonify({'code': 404, 'message': '渠道不存在'}), 404
        domain.dns_channel_id = data['dns_channel_id']
        # 清除旧的 cf_account_id
        if data['dns_channel_id']:
            domain.cf_account_id = None
    
    # 兼容旧的 cf_account_id
    if 'cf_account_id' in data:
        if data['cf_account_id']:
            cf_account = CloudflareAccount.query.get(data['cf_account_id'])
            if not cf_account:
                return jsonify({'code': 404, 'message': 'Cloudflare账户不存在'}), 404
        domain.cf_account_id = data['cf_account_id']
    
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '域名更新成功',
        'data': {'domain': domain.to_admin_dict()}
    })


@admin_bp.route('/domains/<int:domain_id>', methods=['DELETE'])
@admin_required
@demo_forbidden
def delete_domain(domain_id):
    """删除域名"""
    domain = Domain.query.get(domain_id)
    
    if not domain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    db.session.delete(domain)
    db.session.commit()
    
    return jsonify({'code': 200, 'message': '域名删除成功'})


@admin_bp.route('/domains/<int:domain_id>/ns-transfer', methods=['PUT'])
@admin_required
@demo_forbidden
def toggle_domain_ns_transfer(domain_id):
    """切换域名的NS转移状态"""
    domain = Domain.query.get(domain_id)
    
    if not domain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    data = request.get_json()
    allow_ns_transfer = data.get('allow_ns_transfer')
    
    if allow_ns_transfer is None:
        return jsonify({'code': 400, 'message': '请提供NS转移状态'}), 400
    
    domain.allow_ns_transfer = 1 if allow_ns_transfer else 0
    db.session.commit()
    
    status_text = '允许' if domain.allow_ns_transfer else '禁止'
    return jsonify({
        'code': 200,
        'message': f'NS转移已设置为{status_text}',
        'data': {'allow_ns_transfer': domain.allow_ns_transfer == 1}
    })
