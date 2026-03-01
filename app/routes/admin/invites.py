"""
管理员邀请记录管理路由
"""
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import or_
from app import db
from app.models import User
from app.models.user_invite import UserInvite
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required


@admin_bp.route('/invites', methods=['GET'])
@admin_required
def get_invites():
    """获取邀请记录列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '')
    
    query = UserInvite.query
    
    # 搜索邀请人或被邀请人
    if search:
        # 先查找匹配的用户ID
        user_ids = db.session.query(User.id).filter(
            or_(
                User.username.like(f'%{search}%'),
                User.email.like(f'%{search}%')
            )
        ).all()
        user_ids = [u[0] for u in user_ids]
        
        if user_ids:
            query = query.filter(
                or_(
                    UserInvite.inviter_id.in_(user_ids),
                    UserInvite.invitee_id.in_(user_ids),
                    UserInvite.invite_code.like(f'%{search.upper()}%')
                )
            )
        else:
            query = query.filter(UserInvite.invite_code.like(f'%{search.upper()}%'))
    
    # 状态筛选
    if status != '':
        query = query.filter(UserInvite.status == int(status))
    
    query = query.order_by(UserInvite.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # 获取用户信息
    records = []
    for invite in pagination.items:
        inviter = User.query.get(invite.inviter_id)
        invitee = User.query.get(invite.invitee_id)
        records.append({
            'id': invite.id,
            'inviter_id': invite.inviter_id,
            'inviter_username': inviter.username if inviter else '已删除',
            'inviter_email': inviter.email if inviter else '',
            'invitee_id': invite.invitee_id,
            'invitee_username': invitee.username if invitee else '已删除',
            'invitee_email': invitee.email if invitee else '',
            'invite_code': invite.invite_code,
            'register_reward': invite.register_reward,
            'recharge_reward': invite.recharge_reward,
            'total_reward': invite.register_reward + invite.recharge_reward,
            'status': invite.status,
            'status_text': '已首充' if invite.status == 1 else '已注册',
            'created_at': invite.created_at.strftime('%Y-%m-%d %H:%M:%S')
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


@admin_bp.route('/invites/stats', methods=['GET'])
@admin_required
def get_invite_stats():
    """获取邀请统计"""
    total_invites = UserInvite.query.count()
    recharged_count = UserInvite.query.filter_by(status=UserInvite.STATUS_RECHARGED).count()
    
    total_register_reward = db.session.query(
        db.func.sum(UserInvite.register_reward)
    ).scalar() or 0
    
    total_recharge_reward = db.session.query(
        db.func.sum(UserInvite.recharge_reward)
    ).scalar() or 0
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'total_invites': total_invites,
            'recharged_count': recharged_count,
            'total_register_reward': total_register_reward,
            'total_recharge_reward': total_recharge_reward,
            'total_reward': total_register_reward + total_recharge_reward
        }
    })
