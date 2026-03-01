"""
管理员用户管理路由
"""
from decimal import Decimal
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from app import db
from app.models import User, OperationLog
from app.models.point_record import PointRecord
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden
from app.services.phone_binding import PhoneBindingService
from app.utils.ip_utils import get_real_ip


@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_users():
    """获取用户列表"""
    # 检查是否是演示用户，如果是则隐藏敏感信息
    current_user_id = int(get_jwt_identity())
    current_user = User.query.get(current_user_id)
    mask_private = current_user and current_user.role == 'demo'
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '').strip()
    status = request.args.get('status', type=int)
    phone_bound = request.args.get('phone_bound', type=str)  # 手机绑定状态筛选
    
    query = User.query
    
    if search:
        query = query.filter(
            db.or_(
                User.username.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%'),
                User.phone.ilike(f'%{search}%')  # 支持手机号搜索
            )
        )
    
    if status is not None:
        query = query.filter_by(status=status)
    
    # 手机绑定状态筛选
    if phone_bound == '1':
        query = query.filter(User.phone.isnot(None), User.phone != '')
    elif phone_bound == '0':
        query = query.filter(db.or_(User.phone.is_(None), User.phone == ''))
    
    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # 构建用户数据，添加积分和余额
    users_data = []
    for u in pagination.items:
        user_dict = u.to_dict(include_stats=True, mask_private=mask_private)
        user_dict['points'] = u.points or 0
        user_dict['balance'] = float(u.balance) if u.balance else 0
        users_data.append(user_dict)
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'users': users_data,
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        }
    })


@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user(user_id):
    """获取单个用户详情"""
    current_user_id = int(get_jwt_identity())
    current_user = User.query.get(current_user_id)
    mask_private = current_user and current_user.role == 'demo'
    
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {'user': user.to_dict(include_stats=True, mask_private=mask_private)}
    })


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
@demo_forbidden
def update_user(user_id):
    """更新用户信息"""
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    data = request.get_json()
    current_user_id = int(get_jwt_identity())
    
    if user.id == current_user_id and 'role' in data and data['role'] != user.role:
        return jsonify({'code': 400, 'message': '不能修改自己的角色'}), 400
    
    if user.id == current_user_id and 'status' in data and data['status'] == 0:
        return jsonify({'code': 400, 'message': '不能禁用自己的账户'}), 400
    
    if 'status' in data:
        user.status = data['status']
    if 'role' in data and data['role'] in ['user', 'admin', 'demo']:
        user.role = data['role']
    if 'max_domains' in data:
        user.max_domains = data['max_domains']
    if 'username' in data and data['username'].strip():
        existing = User.query.filter(User.username == data['username'], User.id != user_id).first()
        if existing:
            return jsonify({'code': 409, 'message': '用户名已被使用'}), 409
        user.username = data['username'].strip()
    if 'email' in data and data['email'].strip():
        existing = User.query.filter(User.email == data['email'], User.id != user_id).first()
        if existing:
            return jsonify({'code': 409, 'message': '邮箱已被使用'}), 409
        user.email = data['email'].strip()
    if 'password' in data and data['password']:
        user.set_password(data['password'])
    
    # 积分调整
    if 'points_change' in data and data['points_change']:
        points_change = int(data['points_change'])
        if points_change != 0:
            old_points = user.points or 0
            new_points = old_points + points_change
            if new_points < 0:
                return jsonify({'code': 400, 'message': '积分不能为负数'}), 400
            user.points = new_points
            # 记录积分变动
            record = PointRecord(
                user_id=user.id,
                type=PointRecord.TYPE_ADMIN,
                points=points_change,
                balance=new_points,
                description=f'管理员调整 ({"+"+str(points_change) if points_change > 0 else str(points_change)})'
            )
            db.session.add(record)
    
    # 余额调整
    if 'balance_change' in data and data['balance_change']:
        balance_change = Decimal(str(data['balance_change']))
        if balance_change != 0:
            old_balance = user.balance or Decimal('0')
            new_balance = old_balance + balance_change
            if new_balance < 0:
                return jsonify({'code': 400, 'message': '余额不能为负数'}), 400
            user.balance = new_balance
    
    db.session.commit()
    
    admin = User.query.get(current_user_id)
    OperationLog.log(
        user_id=current_user_id,
        username=admin.username if admin else None,
        action=OperationLog.ACTION_UPDATE,
        target_type='user',
        target_id=user_id,
        detail=f'更新用户: {user.username}',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': '用户更新成功',
        'data': {'user': user.to_dict(include_stats=True)}
    })


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
@demo_forbidden
def delete_user(user_id):
    """删除用户"""
    from app.services.user_service import UserService
    
    current_user_id = int(get_jwt_identity())
    success, message = UserService.delete_user_cascade(user_id, current_user_id)
    
    if not success:
        # 根据错误消息确定状态码
        if '不存在' in message:
            code = 404
        else:
            code = 400
        return jsonify({'code': code, 'message': message}), code
    
    return jsonify({'code': 200, 'message': message})


@admin_bp.route('/users/<int:user_id>/oauth/<provider>', methods=['DELETE'])
@admin_required
@demo_forbidden
def unbind_user_oauth(user_id, provider):
    """管理员解绑用户的 OAuth 账号"""
    if provider not in ['github', 'google', 'nodeloc']:
        return jsonify({'code': 400, 'message': '无效的 OAuth 提供商'}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    # 检查是否已绑定
    oauth_field = f'{provider}_id'
    if not getattr(user, oauth_field):
        return jsonify({'code': 400, 'message': f'用户未绑定 {provider.title()} 账号'}), 400
    
    # 管理员解绑不需要检查是否有其他登录方式，因为用户可以通过密码登录
    
    # 解绑
    setattr(user, oauth_field, None)
    db.session.commit()
    
    # 记录操作日志
    current_user_id = int(get_jwt_identity())
    admin = User.query.get(current_user_id)
    OperationLog.log(
        user_id=current_user_id,
        username=admin.username if admin else None,
        action=OperationLog.ACTION_UPDATE,
        target_type='user',
        target_id=user_id,
        detail=f'解绑用户 {user.username} 的 {provider.title()} 账号',
        ip_address=get_real_ip()
    )
    
    return jsonify({'code': 200, 'message': '解绑成功'})
