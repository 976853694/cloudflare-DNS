"""
用户 DNS 记录管理路由
支持多 DNS 服务商
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import Subdomain, DnsRecord
from app.services.dns import DnsApiError, is_record_not_found_error
from app.utils.validators import validate_record_content
from app.routes.admin.decorators import demo_forbidden

record_bp = Blueprint('record', __name__)


@record_bp.route('/subdomains/<int:subdomain_id>/records', methods=['GET'])
@jwt_required()
def get_records(subdomain_id):
    """获取子域名的 DNS 记录"""
    user_id = int(get_jwt_identity())
    
    subdomain = Subdomain.query.filter_by(id=subdomain_id, user_id=user_id).first()
    
    if not subdomain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    records = subdomain.records.all()
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {'records': [r.to_dict() for r in records]}
    })


@record_bp.route('/subdomains/<int:subdomain_id>/records', methods=['POST'])
@jwt_required()
@demo_forbidden
def create_record(subdomain_id):
    """创建 DNS 记录"""
    user_id = int(get_jwt_identity())
    
    subdomain = Subdomain.query.filter_by(id=subdomain_id, user_id=user_id).first()
    
    if not subdomain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    # 检查套餐是否到期
    if subdomain.is_expired:
        return jsonify({'code': 403, 'message': '套餐已到期，无法添加DNS记录，请续费后再试'}), 403
    
    data = request.get_json()
    record_type = data.get('type', '').upper()
    name_prefix = data.get('name', '').strip().lower()
    content = data.get('content', '').strip()
    ttl = data.get('ttl', 300)
    proxied = data.get('proxied', False)
    priority = data.get('priority')
    line = data.get('line')
    weight = data.get('weight')
    
    # 获取 DNS 服务
    dns_service = subdomain.domain.get_dns_service()
    if not dns_service:
        return jsonify({'code': 400, 'message': '域名未配置DNS服务'}), 400
    
    # 验证记录类型
    if not dns_service.validate_record_type(record_type):
        caps = dns_service.get_capabilities()
        return jsonify({
            'code': 400, 
            'message': f'不支持的记录类型: {record_type}，支持: {", ".join(caps.supported_types)}'
        }), 400
    
    if not validate_record_content(record_type, content):
        return jsonify({'code': 400, 'message': '记录值格式不正确'}), 400
    
    # 构建完整记录名称
    if name_prefix and name_prefix != '@':
        record_name = f"{name_prefix}.{subdomain.full_name}"
    else:
        record_name = subdomain.full_name
    
    # 对于 DNSPod/阿里云，需要提取子域名部分（去掉主域名后缀）
    # 例如：test.sub.example.com -> test.sub
    api_record_name = record_name
    domain_name = subdomain.domain.name
    if api_record_name.endswith('.' + domain_name):
        api_record_name = api_record_name[:-len('.' + domain_name)]
    elif api_record_name == domain_name:
        api_record_name = '@'
    
    try:
        zone_id = subdomain.domain.get_zone_id()
        record_id = dns_service.create_record(
            zone_id=zone_id,
            name=api_record_name,
            record_type=record_type,
            value=content,
            ttl=ttl,
            proxied=proxied,
            priority=priority,
            line=line,
            weight=weight
        )
    except DnsApiError as e:
        return jsonify({'code': 500, 'message': f'DNS API错误: {e.message}'}), 500
    except Exception as e:
        return jsonify({'code': 500, 'message': f'DNS API错误: {str(e)}'}), 500
    
    record = DnsRecord(
        subdomain_id=subdomain_id,
        type=record_type,
        name=record_name,
        content=content,
        ttl=ttl,
        proxied=1 if proxied else 0,
        priority=priority,
        cf_record_id=record_id
    )
    
    db.session.add(record)
    
    # 更新域名的记录活动时间
    from app.utils.timezone import now as beijing_now
    if not subdomain.first_record_at:
        subdomain.first_record_at = beijing_now()
    subdomain.last_record_activity_at = beijing_now()
    
    db.session.commit()
    
    # 记录DNS记录修改活动
    from app.services.activity_tracker import ActivityTracker
    ActivityTracker.log(user_id, 'record_update', {
        'subdomain_id': subdomain_id,
        'record_type': record_type,
        'record_name': record_name,
        'action': 'create'
    })
    
    return jsonify({
        'code': 201,
        'message': 'DNS记录添加成功',
        'data': {'record': record.to_dict()}
    }), 201


@record_bp.route('/records/<int:record_id>', methods=['PUT'])
@jwt_required()
@demo_forbidden
def update_record(record_id):
    """更新 DNS 记录
    
    当 DNS 服务商上的记录已被删除时，会返回特殊错误提示，
    建议用户删除本地记录后重新创建。
    """
    user_id = int(get_jwt_identity())
    
    record = DnsRecord.query.join(Subdomain).filter(
        DnsRecord.id == record_id,
        Subdomain.user_id == user_id
    ).first()
    
    if not record:
        return jsonify({'code': 404, 'message': '记录不存在'}), 404
    
    # 检查 DNS 记录 ID 是否有效
    if not record.cf_record_id:
        return jsonify({'code': 400, 'message': '记录ID无效，请删除后重新创建'}), 400
    
    # 检查套餐是否到期
    if record.subdomain.is_expired:
        return jsonify({'code': 403, 'message': '套餐已到期，无法修改DNS记录，请续费后再试'}), 403
    
    data = request.get_json()
    content = data.get('content', record.content).strip()
    ttl = data.get('ttl', record.ttl)
    proxied = data.get('proxied', record.proxied == 1)
    line = data.get('line')
    weight = data.get('weight')
    
    if not validate_record_content(record.type, content):
        return jsonify({'code': 400, 'message': '记录值格式不正确'}), 400
    
    # 获取 DNS 服务
    dns_service = record.subdomain.domain.get_dns_service()
    if not dns_service:
        return jsonify({'code': 400, 'message': '域名未配置DNS服务'}), 400
    
    try:
        zone_id = record.subdomain.domain.get_zone_id()
        
        # 对于 DNSPod/阿里云，需要提取子域名部分（去掉主域名后缀）
        # 例如：test.sub.example.com -> test.sub
        record_name = record.name
        domain_name = record.subdomain.domain.name
        if record_name.endswith('.' + domain_name):
            record_name = record_name[:-len('.' + domain_name)]
        elif record_name == domain_name:
            record_name = '@'
        
        dns_service.update_record(
            zone_id=zone_id,
            record_id=record.cf_record_id,
            name=record_name,
            record_type=record.type,
            value=content,
            ttl=ttl,
            proxied=proxied,
            line=line,
            weight=weight
        )
    except DnsApiError as e:
        # 如果是"记录不存在"错误，返回特殊提示
        if is_record_not_found_error(e):
            return jsonify({
                'code': 404,
                'message': 'DNS记录在服务商处已不存在，请删除本地记录后重新创建',
                'error_type': 'RECORD_NOT_FOUND_ON_PROVIDER'
            }), 404
        return jsonify({'code': 500, 'message': f'DNS API错误: {e.message}'}), 500
    except Exception as e:
        return jsonify({'code': 500, 'message': f'DNS API错误: {str(e)}'}), 500
    
    record.content = content
    record.ttl = ttl
    record.proxied = 1 if proxied else 0
    
    # 更新域名的记录活动时间
    from app.utils.timezone import now as beijing_now
    record.subdomain.last_record_activity_at = beijing_now()
    
    db.session.commit()
    
    # 记录DNS记录修改活动
    from app.services.activity_tracker import ActivityTracker
    ActivityTracker.log(user_id, 'record_update', {
        'subdomain_id': record.subdomain_id,
        'record_type': record.type,
        'record_name': record.name,
        'action': 'update'
    })
    
    return jsonify({
        'code': 200,
        'message': 'DNS记录更新成功',
        'data': {'record': record.to_dict()}
    })


@record_bp.route('/records/<int:record_id>', methods=['DELETE'])
@jwt_required()
@demo_forbidden
def delete_record(record_id):
    """删除 DNS 记录
    
    支持强制删除模式：当 DNS 服务商上的记录已被删除时，
    可以通过 ?force=true 参数强制删除本地记录。
    
    Query Parameters:
        force: 是否强制删除（跳过 DNS API 调用）
    """
    user_id = int(get_jwt_identity())
    
    record = DnsRecord.query.join(Subdomain).filter(
        DnsRecord.id == record_id,
        Subdomain.user_id == user_id
    ).first()
    
    if not record:
        return jsonify({'code': 404, 'message': '记录不存在'}), 404
    
    # 检查是否强制删除
    force = request.args.get('force', 'false').lower() == 'true'
    
    # 获取 DNS 服务
    dns_service = record.subdomain.domain.get_dns_service()
    if not dns_service:
        return jsonify({'code': 400, 'message': '域名未配置DNS服务'}), 400
    
    # 如果不是强制删除，尝试调用 DNS API
    if not force:
        try:
            zone_id = record.subdomain.domain.get_zone_id()
            dns_service.delete_record(zone_id, record.cf_record_id)
        except DnsApiError as e:
            # 如果是"记录不存在"错误，视为成功，继续删除本地记录
            if not is_record_not_found_error(e):
                return jsonify({'code': 500, 'message': f'DNS API错误: {e.message}'}), 500
            # 记录不存在，继续删除本地记录
        except Exception as e:
            return jsonify({'code': 500, 'message': f'DNS API错误: {str(e)}'}), 500
    
    # 记录删除操作日志
    from app.services.activity_tracker import ActivityTracker
    ActivityTracker.log(user_id, 'record_update', {
        'subdomain_id': record.subdomain_id,
        'record_type': record.type,
        'record_name': record.name,
        'action': 'force_delete' if force else 'delete'
    })
    
    # 删除本地记录
    db.session.delete(record)
    db.session.commit()
    
    message = '本地记录已强制删除' if force else 'DNS记录删除成功'
    return jsonify({'code': 200, 'message': message})


@record_bp.route('/subdomains/<int:subdomain_id>/capabilities', methods=['GET'])
@jwt_required()
def get_subdomain_capabilities(subdomain_id):
    """获取子域名的 DNS 服务能力"""
    user_id = int(get_jwt_identity())
    
    subdomain = Subdomain.query.filter_by(id=subdomain_id, user_id=user_id).first()
    
    if not subdomain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    dns_service = subdomain.domain.get_dns_service()
    if not dns_service:
        return jsonify({'code': 400, 'message': '域名未配置DNS服务'}), 400
    
    try:
        capabilities = dns_service.get_capabilities()
        lines = dns_service.get_lines()
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {
                'provider_type': dns_service.provider_type,
                'provider_name': dns_service.provider_name,
                'capabilities': capabilities.to_dict(),
                'lines': [l.to_dict() for l in lines]
            }
        })
    except Exception as e:
        return jsonify({'code': 500, 'message': f'获取能力信息失败: {str(e)}'}), 500
