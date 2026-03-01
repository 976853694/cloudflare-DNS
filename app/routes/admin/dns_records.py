"""
管理员DNS记录管理路由
支持多 DNS 服务商
"""
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from app import db
from app.models import Domain, DnsRecord, User
from app.services.dns import DnsApiError, is_record_not_found_error
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden


@admin_bp.route('/dns-records', methods=['GET'])
@admin_required
def get_all_dns_records():
    """获取所有DNS记录"""
    current_user_id = int(get_jwt_identity())
    current_user = User.query.get(current_user_id)
    mask_private = current_user and current_user.role == 'demo'
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    domain_id = request.args.get('domain_id', type=int)
    record_type = request.args.get('type', '').strip()
    source = request.args.get('source', '').strip()
    search = request.args.get('search', '').strip()
    
    if domain_id:
        domains = Domain.query.filter_by(id=domain_id).all()
    else:
        domains = Domain.query.all()
    
    all_records = []
    
    for domain in domains:
        # 获取 DNS 服务（支持新旧两种方式）
        dns_service = domain.get_dns_service()
        if not dns_service:
            continue
        
        try:
            zone_id = domain.get_zone_id()
            result = dns_service.get_records(zone_id)
            dns_records = result.get('list', [])
            
            # 获取系统记录映射
            system_records = {}
            for subdomain in domain.subdomains:
                for record in subdomain.records:
                    system_records[record.cf_record_id] = {
                        'username': subdomain.user.username if subdomain.user else '未知用户',
                        'subdomain_id': subdomain.id
                    }
            
            # 获取服务商能力
            capabilities = dns_service.get_capabilities()
            
            for dns_record in dns_records:
                record_data = {
                    'cf_record_id': '******' if mask_private else dns_record.record_id,
                    'record_id': '******' if mask_private else dns_record.record_id,
                    'domain_id': domain.id,
                    'domain_name': '******' if mask_private else domain.name,
                    'name': '******' if mask_private else dns_record.name,
                    'full_name': '******' if mask_private else dns_record.full_name,
                    'type': dns_record.type,
                    'content': '******' if mask_private else dns_record.value,
                    'value': '******' if mask_private else dns_record.value,
                    'ttl': dns_record.ttl,
                    'proxied': dns_record.proxied,
                    'line': dns_record.line,
                    'line_name': dns_record.line_name,
                    'weight': dns_record.weight,
                    'status': dns_record.status,
                    'source': 'system' if dns_record.record_id in system_records else 'provider',
                    'username': '******' if mask_private else system_records.get(dns_record.record_id, {}).get('username'),
                    'subdomain_id': system_records.get(dns_record.record_id, {}).get('subdomain_id'),
                    'provider_type': dns_service.provider_type,
                    'provider_name': dns_service.provider_name,
                    'capabilities': capabilities.to_dict()
                }
                
                if record_type and record_data['type'] != record_type:
                    continue
                if source and record_data['source'] != source:
                    continue
                if search and search.lower() not in record_data['name'].lower():
                    continue
                
                all_records.append(record_data)
        except Exception:
            continue
    
    total = len(all_records)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_records = all_records[start:end]
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'records': paginated_records,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page if total > 0 else 1
            }
        }
    })


@admin_bp.route('/dns-records/<string:record_id>', methods=['PUT'])
@admin_required
@demo_forbidden
def update_dns_record(record_id):
    """更新DNS记录
    
    当 DNS 服务商上的记录已被删除时，会返回特殊错误提示。
    """
    data = request.get_json()
    domain_id = data.get('domain_id')
    
    domain = Domain.query.get(domain_id)
    if not domain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    dns_service = domain.get_dns_service()
    if not dns_service:
        return jsonify({'code': 400, 'message': '域名未配置DNS服务'}), 400
    
    try:
        zone_id = domain.get_zone_id()
        
        # 获取原记录信息
        original = dns_service.get_record(zone_id, record_id)
        if not original:
            return jsonify({'code': 404, 'message': '记录不存在'}), 404
        
        # 更新记录
        dns_service.update_record(
            zone_id=zone_id,
            record_id=record_id,
            name=data.get('name', original.name),
            record_type=data.get('type', original.type),
            value=data.get('content', data.get('value', original.value)),
            ttl=data.get('ttl', original.ttl),
            proxied=data.get('proxied', original.proxied),
            line=data.get('line', original.line),
            weight=data.get('weight', original.weight),
            priority=data.get('priority', original.priority)
        )
        
        # 更新数据库记录
        db_record = DnsRecord.query.filter_by(cf_record_id=record_id).first()
        if db_record:
            if 'content' in data or 'value' in data:
                db_record.content = data.get('content', data.get('value'))
            if 'ttl' in data:
                db_record.ttl = data['ttl']
            if 'proxied' in data:
                db_record.proxied = data['proxied']
            db.session.commit()
        
        return jsonify({'code': 200, 'message': '更新成功'})
    except DnsApiError as e:
        # 如果是"记录不存在"错误，返回特殊提示
        if is_record_not_found_error(e):
            return jsonify({
                'code': 404,
                'message': 'DNS记录在服务商处已不存在，请删除本地记录后重新创建',
                'error_type': 'RECORD_NOT_FOUND_ON_PROVIDER'
            }), 404
        return jsonify({'code': 500, 'message': f'更新失败: {e.message}'}), 500
    except Exception as e:
        return jsonify({'code': 500, 'message': f'更新失败: {str(e)}'}), 500


@admin_bp.route('/dns-records/<string:record_id>', methods=['DELETE'])
@admin_required
@demo_forbidden
def delete_dns_record(record_id):
    """删除DNS记录
    
    支持强制删除模式：当 DNS 服务商上的记录已被删除时，
    可以通过 ?force=true 参数强制删除本地记录。
    """
    domain_id = request.args.get('domain_id', type=int)
    force = request.args.get('force', 'false').lower() == 'true'
    
    domain = Domain.query.get(domain_id)
    if not domain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    dns_service = domain.get_dns_service()
    if not dns_service:
        return jsonify({'code': 400, 'message': '域名未配置DNS服务'}), 400
    
    # 如果不是强制删除，尝试调用 DNS API
    if not force:
        try:
            zone_id = domain.get_zone_id()
            dns_service.delete_record(zone_id, record_id)
        except DnsApiError as e:
            # 如果是"记录不存在"错误，视为成功，继续删除本地记录
            if not is_record_not_found_error(e):
                return jsonify({'code': 500, 'message': f'删除失败: {e.message}'}), 500
            # 记录不存在，继续删除本地记录
        except Exception as e:
            return jsonify({'code': 500, 'message': f'删除失败: {str(e)}'}), 500
    
    # 删除数据库记录
    db_record = DnsRecord.query.filter_by(cf_record_id=record_id).first()
    if db_record:
        db.session.delete(db_record)
        db.session.commit()
    
    message = '本地记录已强制删除' if force else '删除成功'
    return jsonify({'code': 200, 'message': message})


@admin_bp.route('/dns-records', methods=['POST'])
@admin_required
@demo_forbidden
def create_dns_record():
    """创建DNS记录"""
    data = request.get_json()
    domain_id = data.get('domain_id')
    
    domain = Domain.query.get(domain_id)
    if not domain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    dns_service = domain.get_dns_service()
    if not dns_service:
        return jsonify({'code': 400, 'message': '域名未配置DNS服务'}), 400
    
    # 验证记录类型
    record_type = data.get('type', '').upper()
    if not dns_service.validate_record_type(record_type):
        caps = dns_service.get_capabilities()
        return jsonify({
            'code': 400, 
            'message': f'不支持的记录类型: {record_type}，支持: {", ".join(caps.supported_types)}'
        }), 400
    
    try:
        zone_id = domain.get_zone_id()
        record_id = dns_service.create_record(
            zone_id=zone_id,
            name=data.get('name', '@'),
            record_type=record_type,
            value=data.get('content', data.get('value', '')),
            ttl=data.get('ttl', 600),
            proxied=data.get('proxied', False),
            line=data.get('line'),
            weight=data.get('weight'),
            priority=data.get('priority')
        )
        
        return jsonify({
            'code': 201, 
            'message': '创建成功',
            'data': {'record_id': record_id}
        }), 201
    except DnsApiError as e:
        return jsonify({'code': 500, 'message': f'创建失败: {e.message}'}), 500
    except Exception as e:
        return jsonify({'code': 500, 'message': f'创建失败: {str(e)}'}), 500


@admin_bp.route('/domains/<int:domain_id>/capabilities', methods=['GET'])
@admin_required
def get_domain_capabilities(domain_id):
    """获取域名的DNS服务能力"""
    domain = Domain.query.get(domain_id)
    if not domain:
        return jsonify({'code': 404, 'message': '域名不存在'}), 404
    
    dns_service = domain.get_dns_service()
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
