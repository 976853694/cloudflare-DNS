"""
管理员操作日志路由
"""
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from app import db
from app.models import OperationLog, User
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden


@admin_bp.route('/logs', methods=['GET'])
@admin_required
def get_logs():
    """获取操作日志"""
    current_user_id = int(get_jwt_identity())
    current_user = User.query.get(current_user_id)
    mask_private = current_user and current_user.role == 'demo'
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # 搜索条件
    username = request.args.get('username', '').strip()
    action = request.args.get('action', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    
    query = OperationLog.query
    
    # 按用户名筛选
    if username:
        query = query.filter(OperationLog.username.like(f'%{username}%'))
    
    # 按操作类型筛选
    if action:
        query = query.filter_by(action=action)
    
    # 按时间区间筛选
    if start_date:
        from datetime import datetime
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(OperationLog.created_at >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        from datetime import datetime, timedelta
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            # 包含结束日期的整天
            end_dt = end_dt + timedelta(days=1)
            query = query.filter(OperationLog.created_at < end_dt)
        except ValueError:
            pass
    
    pagination = query.order_by(OperationLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'logs': [log.to_dict(mask_private=mask_private) for log in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        }
    })


@admin_bp.route('/logs/<int:log_id>', methods=['DELETE'])
@admin_required
@demo_forbidden
def delete_log(log_id):
    """删除单条日志"""
    log = OperationLog.query.get(log_id)
    if not log:
        return jsonify({'code': 404, 'message': '日志不存在'}), 404
    
    db.session.delete(log)
    db.session.commit()
    return jsonify({'code': 200, 'message': '日志删除成功'})


@admin_bp.route('/logs/batch-delete', methods=['POST'])
@admin_required
@demo_forbidden
def batch_delete_logs():
    """批量删除日志"""
    data = request.get_json()
    ids = data.get('ids', [])
    clear_all = data.get('clear_all', False)
    
    if clear_all:
        deleted = OperationLog.query.delete()
        db.session.commit()
        return jsonify({'code': 200, 'message': f'已清空所有日志，共删除 {deleted} 条'})
    
    if not ids:
        return jsonify({'code': 400, 'message': '请提供日志ID列表'}), 400
    
    deleted = 0
    for log_id in ids:
        log = OperationLog.query.get(log_id)
        if log:
            db.session.delete(log)
            deleted += 1
    
    db.session.commit()
    return jsonify({'code': 200, 'message': f'成功删除 {deleted} 条日志'})
