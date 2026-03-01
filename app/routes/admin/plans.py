"""
管理员套餐管理路由
"""
from flask import request, jsonify
from app import db
from app.models import Domain, Plan
from app.models.plan import plan_domains
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden


@admin_bp.route('/plans', methods=['GET'])
@admin_required
def get_plans():
    """获取所有套餐"""
    domain_id = request.args.get('domain_id', type=int)
    
    query = Plan.query
    if domain_id:
        # 筛选包含指定域名的套餐
        query = query.filter(Plan.domains.any(id=domain_id))
    
    plans = query.order_by(Plan.sort_order, Plan.id).all()
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {'plans': [p.to_dict() for p in plans]}
    })


@admin_bp.route('/plans', methods=['POST'])
@admin_required
@demo_forbidden
def create_plan():
    """创建套餐（支持多域名）"""
    try:
        data = request.get_json()
        
        # 支持 domain_ids 数组或单个 domain_id
        domain_ids = data.get('domain_ids', [])
        if not domain_ids:
            # 兼容旧版单个 domain_id
            single_id = data.get('domain_id')
            if single_id:
                domain_ids = [single_id]
        
        name = data.get('name', '').strip()
        
        if not domain_ids or not name:
            return jsonify({'code': 400, 'message': '请填写域名和套餐名称'}), 400
        
        # 验证所有域名是否存在
        domains = Domain.query.filter(Domain.id.in_(domain_ids)).all()
        if len(domains) != len(domain_ids):
            return jsonify({'code': 404, 'message': '部分域名不存在'}), 404
        
        plan = Plan(
            name=name,
            price=data.get('price', 0),
            duration_days=data.get('duration_days', 30),
            min_length=data.get('min_length', 1),
            max_length=data.get('max_length', 63),
            max_records=data.get('max_records', 10),
            description=data.get('description', ''),
            sort_order=data.get('sort_order', 0),
            # 免费套餐相关
            is_free=data.get('is_free', False),
            max_purchase_count=data.get('max_purchase_count', 0),
            renew_before_days=data.get('renew_before_days', 0),
            points_per_day=data.get('points_per_day', 0)
        )
        
        # 关联多个域名
        plan.domains = domains
        
        db.session.add(plan)
        db.session.commit()
        
        return jsonify({
            'code': 201,
            'message': '套餐创建成功',
            'data': {'plan': plan.to_dict()}
        }), 201
    except Exception as e:
        db.session.rollback()
        import traceback
        from flask import current_app
        current_app.logger.error(f"创建套餐失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'code': 500, 'message': f'创建套餐失败: {str(e)}'}), 500


@admin_bp.route('/plans/<int:plan_id>', methods=['PUT'])
@admin_required
@demo_forbidden
def update_plan(plan_id):
    """更新套餐（支持多域名）"""
    plan = Plan.query.get(plan_id)
    
    if not plan:
        return jsonify({'code': 404, 'message': '套餐不存在'}), 404
    
    data = request.get_json()
    
    # 更新域名关联
    if 'domain_ids' in data:
        domain_ids = data['domain_ids']
        if domain_ids:
            domains = Domain.query.filter(Domain.id.in_(domain_ids)).all()
            if len(domains) != len(domain_ids):
                return jsonify({'code': 404, 'message': '部分域名不存在'}), 404
            plan.domains = domains
    elif 'domain_id' in data:
        # 兼容旧版单个 domain_id
        domain = Domain.query.get(data['domain_id'])
        if domain:
            plan.domains = [domain]
    
    if 'name' in data:
        plan.name = data['name']
    if 'price' in data:
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
        plan.status = data['status']
    if 'sort_order' in data:
        plan.sort_order = data['sort_order']
    # 免费套餐相关字段
    if 'is_free' in data:
        plan.is_free = data['is_free']
    if 'max_purchase_count' in data:
        plan.max_purchase_count = data['max_purchase_count']
    if 'renew_before_days' in data:
        plan.renew_before_days = data['renew_before_days']
    if 'points_per_day' in data:
        plan.points_per_day = data['points_per_day']
    
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '套餐更新成功',
        'data': {'plan': plan.to_dict()}
    })


@admin_bp.route('/plans/<int:plan_id>', methods=['DELETE'])
@admin_required
@demo_forbidden
def delete_plan(plan_id):
    """删除套餐"""
    plan = Plan.query.get(plan_id)
    
    if not plan:
        return jsonify({'code': 404, 'message': '套餐不存在'}), 404
    
    db.session.delete(plan)
    db.session.commit()
    
    return jsonify({'code': 200, 'message': '套餐删除成功'})
