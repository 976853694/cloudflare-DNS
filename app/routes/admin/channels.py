"""
管理员渠道管理路由
支持多 DNS 服务商的统一渠道管理
"""
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from app import db
from app.models import DnsChannel, Domain, User
from app.services.dns import DnsServiceFactory
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden


@admin_bp.route('/channels', methods=['GET'])
@admin_required
def get_channels():
    """获取所有渠道"""
    current_user_id = int(get_jwt_identity())
    current_user = User.query.get(current_user_id)
    mask_private = current_user and current_user.role == 'demo'
    
    channels = DnsChannel.query.all()
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'channels': [c.to_dict(include_credentials=True, mask_private=mask_private) for c in channels]
        }
    })


@admin_bp.route('/channels/providers', methods=['GET'])
@admin_required
def get_providers():
    """获取支持的服务商列表"""
    providers = DnsServiceFactory.get_providers()
    # 添加凭据字段信息
    for p in providers:
        p['credential_fields'] = DnsServiceFactory.get_credential_fields(p['type'])
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {'providers': providers}
    })


@admin_bp.route('/channels', methods=['POST'])
@admin_required
@demo_forbidden
def create_channel():
    """创建渠道"""
    data = request.get_json()
    
    name = data.get('name', '').strip()
    provider_type = data.get('provider_type', '').strip()
    credentials = data.get('credentials', {})
    remark = data.get('remark', '').strip()
    config = data.get('config', {})
    
    if not name:
        return jsonify({'code': 400, 'message': '请填写渠道名称'}), 400
    
    if not provider_type:
        return jsonify({'code': 400, 'message': '请选择服务商类型'}), 400
    
    if not DnsServiceFactory.is_registered(provider_type):
        return jsonify({'code': 400, 'message': f'不支持的服务商类型: {provider_type}'}), 400
    
    # 验证凭据
    try:
        service = DnsServiceFactory.create(provider_type, credentials)
        if not service.verify_credentials():
            return jsonify({'code': 400, 'message': '凭据验证失败，请检查配置是否正确'}), 400
    except Exception as e:
        return jsonify({'code': 400, 'message': f'凭据验证失败: {str(e)}'}), 400

    # 创建渠道
    channel = DnsChannel(
        name=name,
        provider_type=provider_type,
        remark=remark
    )
    channel.set_credentials(credentials)
    if config:
        channel.set_config(config)
    
    db.session.add(channel)
    db.session.commit()
    
    return jsonify({
        'code': 201,
        'message': '渠道创建成功',
        'data': {'channel': channel.to_dict()}
    }), 201


@admin_bp.route('/channels/<int:channel_id>', methods=['GET'])
@admin_required
def get_channel(channel_id):
    """获取渠道详情"""
    current_user_id = int(get_jwt_identity())
    current_user = User.query.get(current_user_id)
    mask_private = current_user and current_user.role == 'demo'
    
    channel = DnsChannel.query.get(channel_id)
    if not channel:
        return jsonify({'code': 404, 'message': '渠道不存在'}), 404
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {'channel': channel.to_dict(include_credentials=True, mask_private=mask_private)}
    })


@admin_bp.route('/channels/<int:channel_id>', methods=['PUT'])
@admin_required
@demo_forbidden
def update_channel(channel_id):
    """更新渠道"""
    channel = DnsChannel.query.get(channel_id)
    if not channel:
        return jsonify({'code': 404, 'message': '渠道不存在'}), 404
    
    data = request.get_json()
    
    if 'name' in data:
        channel.name = data['name']
    if 'remark' in data:
        channel.remark = data['remark']
    if 'status' in data:
        channel.status = data['status']
    if 'config' in data:
        channel.set_config(data['config'])
    
    # 更新凭据（如果提供）
    if 'credentials' in data and data['credentials']:
        credentials = data['credentials']
        # 合并现有凭据（只更新提供的字段）
        existing = channel.get_credentials()
        for key, value in credentials.items():
            if value:  # 只更新非空值
                existing[key] = value
        
        # 验证新凭据
        try:
            service = DnsServiceFactory.create(channel.provider_type, existing)
            if not service.verify_credentials():
                return jsonify({'code': 400, 'message': '凭据验证失败'}), 400
            channel.set_credentials(existing)
        except Exception as e:
            return jsonify({'code': 400, 'message': f'凭据验证失败: {str(e)}'}), 400
    
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '渠道更新成功',
        'data': {'channel': channel.to_dict()}
    })


@admin_bp.route('/channels/<int:channel_id>', methods=['DELETE'])
@admin_required
@demo_forbidden
def delete_channel(channel_id):
    """删除渠道"""
    channel = DnsChannel.query.get(channel_id)
    if not channel:
        return jsonify({'code': 404, 'message': '渠道不存在'}), 404
    
    if channel.domains.count() > 0:
        return jsonify({'code': 400, 'message': '该渠道下还有域名，无法删除'}), 400
    
    db.session.delete(channel)
    db.session.commit()
    
    return jsonify({'code': 200, 'message': '渠道删除成功'})


@admin_bp.route('/channels/<int:channel_id>/verify', methods=['POST'])
@admin_required
def verify_channel(channel_id):
    """验证渠道凭据"""
    channel = DnsChannel.query.get(channel_id)
    if not channel:
        return jsonify({'code': 404, 'message': '渠道不存在'}), 404
    
    try:
        valid = channel.verify_credentials()
        return jsonify({
            'code': 200,
            'message': '凭据有效' if valid else '凭据无效',
            'data': {'valid': valid}
        })
    except Exception as e:
        return jsonify({
            'code': 200,
            'message': f'验证失败: {str(e)}',
            'data': {'valid': False}
        })


@admin_bp.route('/channels/<int:channel_id>/zones', methods=['GET'])
@admin_required
def get_channel_zones(channel_id):
    """获取渠道的域名列表（Zone）"""
    current_user_id = int(get_jwt_identity())
    current_user = User.query.get(current_user_id)
    mask_private = current_user and current_user.role == 'demo'
    
    channel = DnsChannel.query.get(channel_id)
    if not channel:
        return jsonify({'code': 404, 'message': '渠道不存在'}), 404
    
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
            
            zones = []
            for zone in all_zones:
                zone_dict = zone.to_dict()
                if mask_private:
                    zone_dict['zone_id'] = '******'
                zones.append(zone_dict)
            
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
                zone_dict = zone.to_dict()
                if mask_private:
                    zone_dict['zone_id'] = '******'
                zones.append(zone_dict)
            
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


@admin_bp.route('/channels/<int:channel_id>/capabilities', methods=['GET'])
@admin_required
def get_channel_capabilities(channel_id):
    """获取渠道能力"""
    channel = DnsChannel.query.get(channel_id)
    if not channel:
        return jsonify({'code': 404, 'message': '渠道不存在'}), 404
    
    try:
        service = channel.get_service()
        capabilities = service.get_capabilities()
        lines = service.get_lines()
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {
                'capabilities': capabilities.to_dict(),
                'lines': [l.to_dict() for l in lines]
            }
        })
    except Exception as e:
        return jsonify({'code': 500, 'message': f'获取能力信息失败: {str(e)}'}), 500


@admin_bp.route('/channels/<int:channel_id>/remote-domains', methods=['GET'])
@admin_required
def get_remote_domains(channel_id):
    """获取六趣DNS渠道的上游可用域名列表（包含套餐）"""
    channel = DnsChannel.query.get(channel_id)
    if not channel:
        return jsonify({'code': 404, 'message': '渠道不存在'}), 404
    
    if channel.provider_type != 'liuqu':
        return jsonify({'code': 400, 'message': '仅六趣DNS渠道支持此功能'}), 400
    
    try:
        service = channel.get_service()
        
        # 获取上游用户信息
        user_info = service.get_user_info()
        
        # 获取上游可用域名（包含套餐）
        domains = service.get_available_domains()
        
        # 获取本地已导入的域名（用于标记）
        imported_domain_ids = set()
        local_domains = Domain.query.filter_by(dns_channel_id=channel_id).all()
        for d in local_domains:
            if d.upstream_domain_id:
                imported_domain_ids.add(d.upstream_domain_id)
        
        # 标记已导入的域名
        for domain in domains:
            domain['imported'] = domain.get('id') in imported_domain_ids
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {
                'user_info': user_info,
                'domains': domains
            }
        })
    except Exception as e:
        return jsonify({'code': 500, 'message': f'获取上游域名失败: {str(e)}'}), 500


@admin_bp.route('/channels/<int:channel_id>/import-domains', methods=['POST'])
@admin_required
@demo_forbidden
def import_remote_domains(channel_id):
    """从六趣DNS渠道导入域名和套餐"""
    from app.models import Plan
    
    channel = DnsChannel.query.get(channel_id)
    if not channel:
        return jsonify({'code': 404, 'message': '渠道不存在'}), 404
    
    if channel.provider_type != 'liuqu':
        return jsonify({'code': 400, 'message': '仅六趣DNS渠道支持此功能'}), 400
    
    data = request.get_json()
    import_items = data.get('items', [])
    
    if not import_items:
        return jsonify({'code': 400, 'message': '请选择要导入的域名和套餐'}), 400
    
    imported_domains = []
    imported_plans = []
    errors = []
    
    for item in import_items:
        upstream_domain_id = item.get('domain_id')
        domain_name = item.get('domain_name')
        plans_to_import = item.get('plans', [])
        
        if not upstream_domain_id or not domain_name:
            errors.append(f'域名数据不完整')
            continue
        
        # 检查域名是否已存在
        existing_domain = Domain.query.filter_by(name=domain_name).first()
        if existing_domain:
            # 如果已存在但不是当前渠道的，跳过
            if existing_domain.dns_channel_id != channel_id:
                errors.append(f'域名 {domain_name} 已被其他渠道使用')
                continue
            domain = existing_domain
        else:
            # 创建新域名
            domain = Domain(
                name=domain_name,
                dns_channel_id=channel_id,
                upstream_domain_id=upstream_domain_id,
                zone_id=str(upstream_domain_id),  # 使用上游域名ID作为zone_id
                status=1,
                allow_register=1
            )
            db.session.add(domain)
            db.session.flush()
            imported_domains.append(domain_name)
        
        # 导入套餐
        for plan_data in plans_to_import:
            upstream_plan_id = plan_data.get('id')
            
            # 检查套餐是否已导入
            existing_plan = Plan.query.filter_by(
                dns_channel_id=channel_id,
                upstream_plan_id=upstream_plan_id
            ).first()
            
            if existing_plan:
                # 更新现有套餐
                existing_plan.name = plan_data.get('name', existing_plan.name)
                existing_plan.upstream_price = plan_data.get('price', 0)
                existing_plan.duration_days = plan_data.get('duration_days', 30)
                existing_plan.min_length = plan_data.get('min_length', 1)
                existing_plan.max_length = plan_data.get('max_length', 63)
                existing_plan.max_records = plan_data.get('max_records', 10)
                # 确保关联域名
                if domain not in existing_plan.domains:
                    existing_plan.domains.append(domain)
            else:
                # 创建新套餐
                # 默认售价 = 上游价格 * 1.2（20%利润）
                upstream_price = float(plan_data.get('price', 0))
                default_price = round(upstream_price * 1.2, 2)
                
                new_plan = Plan(
                    name=f"{plan_data.get('name', '套餐')} ({domain_name})",
                    price=default_price,
                    duration_days=plan_data.get('duration_days', 30),
                    min_length=plan_data.get('min_length', 1),
                    max_length=plan_data.get('max_length', 63),
                    max_records=plan_data.get('max_records', 10),
                    description=f"上游套餐: {plan_data.get('name', '')}",
                    dns_channel_id=channel_id,
                    upstream_plan_id=upstream_plan_id,
                    upstream_price=upstream_price,
                    status=1
                )
                new_plan.domains.append(domain)
                db.session.add(new_plan)
                imported_plans.append(new_plan.name)
    
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': f'导入完成：{len(imported_domains)} 个域名，{len(imported_plans)} 个套餐',
        'data': {
            'imported_domains': imported_domains,
            'imported_plans': imported_plans,
            'errors': errors
        }
    })
