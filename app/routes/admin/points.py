"""
管理员积分记录管理路由
"""
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import or_
from app import db
from app.models import User
from app.models.point_record import PointRecord
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required


@admin_bp.route('/points', methods=['GET'])
@admin_required
def get_point_records():
    """获取积分记录列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '').strip()
    record_type = request.args.get('type', '')
    
    query = PointRecord.query
    
    # 搜索用户
    if search:
        user_ids = db.session.query(User.id).filter(
            or_(
                User.username.like(f'%{search}%'),
                User.email.like(f'%{search}%')
            )
        ).all()
        user_ids = [u[0] for u in user_ids]
        
        if user_ids:
            query = query.filter(PointRecord.user_id.in_(user_ids))
        else:
            query = query.filter(PointRecord.id == -1)  # 无结果
    
    # 类型筛选
    if record_type:
        query = query.filter(PointRecord.type == record_type)
    
    query = query.order_by(PointRecord.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # 获取用户信息
    records = []
    for record in pagination.items:
        user = User.query.get(record.user_id)
        records.append({
            'id': record.id,
            'user_id': record.user_id,
            'username': user.username if user else '已删除',
            'email': user.email if user else '',
            'type': record.type,
            'type_text': record.type_text,
            'points': record.points,
            'balance': record.balance,
            'description': record.description,
            'created_at': record.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'records': records,
            'total': pagination.total,
            'pages': pagination.pages,
            'page': page,
            'per_page': per_page
        }
    })


@admin_bp.route('/points/stats', methods=['GET'])
@admin_required
def get_point_stats():
    """获取积分统计"""
    # 总发放积分（正数）
    total_issued = db.session.query(
        db.func.sum(PointRecord.points)
    ).filter(PointRecord.points > 0).scalar() or 0
    
    # 总消耗积分（负数的绝对值）
    total_consumed = abs(db.session.query(
        db.func.sum(PointRecord.points)
    ).filter(PointRecord.points < 0).scalar() or 0)
    
    # 签到发放
    signin_issued = db.session.query(
        db.func.sum(PointRecord.points)
    ).filter(PointRecord.type.in_([PointRecord.TYPE_SIGNIN, PointRecord.TYPE_SIGNIN_BONUS])).scalar() or 0
    
    # 邀请发放
    invite_issued = db.session.query(
        db.func.sum(PointRecord.points)
    ).filter(PointRecord.type.in_([PointRecord.TYPE_INVITE, PointRecord.TYPE_INVITE_RECHARGE])).scalar() or 0
    
    # 兑换消耗
    exchange_consumed = abs(db.session.query(
        db.func.sum(PointRecord.points)
    ).filter(PointRecord.type == PointRecord.TYPE_EXCHANGE).scalar() or 0)
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'total_issued': total_issued,
            'total_consumed': total_consumed,
            'signin_issued': signin_issued,
            'invite_issued': invite_issued,
            'exchange_consumed': exchange_consumed
        }
    })
