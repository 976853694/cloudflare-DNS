"""管理员工单管理路由"""
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from app.models import User, Ticket, TicketReply
from app import db
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden
from datetime import datetime
import re


@admin_bp.route('/tickets', methods=['GET'])
@admin_required
def get_tickets():
    """获取所有工单列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', type=int)
    ticket_type = request.args.get('type', type=int)
    keyword = request.args.get('keyword', '')
    
    query = Ticket.query
    
    # 筛选条件
    if status is not None:
        query = query.filter(Ticket.status == status)
    if ticket_type is not None:
        query = query.filter(Ticket.type == ticket_type)
    if keyword:
        query = query.filter(
            db.or_(
                Ticket.ticket_no.like(f'%{keyword}%'),
                Ticket.subject.like(f'%{keyword}%')
            )
        )
    
    # 排序：待处理优先，然后按更新时间倒序
    query = query.order_by(Ticket.status.asc(), Ticket.updated_at.desc())
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    tickets = []
    for ticket in pagination.items:
        from_user = User.query.get(ticket.from_user_id)
        to_user = User.query.get(ticket.to_user_id) if ticket.to_user_id else None
        
        # 统计回复数和未读数
        reply_count = TicketReply.query.filter_by(ticket_id=ticket.id).count()
        unread_count = TicketReply.query.filter_by(ticket_id=ticket.id, is_read=0).count()
        
        tickets.append({
            'id': ticket.id,
            'ticket_no': ticket.ticket_no,
            'type': ticket.type,
            'type_text': '用户工单' if ticket.type == 1 else '管理员工单',
            'from_user_id': ticket.from_user_id,
            'from_username': from_user.username if from_user else '未知用户',
            'to_user_id': ticket.to_user_id,
            'to_username': to_user.username if to_user else None,
            'subject': ticket.subject,
            'content': ticket.content[:100] + '...' if len(ticket.content) > 100 else ticket.content,
            'status': ticket.status,
            'status_text': ['待处理', '处理中', '已关闭'][ticket.status],
            'reply_count': reply_count,
            'unread_count': unread_count,
            'created_at': ticket.created_at.strftime('%Y-%m-%d %H:%M'),
            'updated_at': ticket.updated_at.strftime('%Y-%m-%d %H:%M')
        })
    
    return jsonify({
        'code': 200,
        'data': {
            'tickets': tickets,
            'total': pagination.total,
            'pages': pagination.pages,
            'page': page
        }
    })


@admin_bp.route('/tickets/<int:ticket_id>', methods=['GET'])
@admin_required
def get_ticket_detail(ticket_id):
    """获取工单详情"""
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'code': 404, 'message': '工单不存在'}), 404
    
    from_user = User.query.get(ticket.from_user_id)
    to_user = User.query.get(ticket.to_user_id) if ticket.to_user_id else None
    
    # 获取回复列表
    replies = TicketReply.query.filter_by(ticket_id=ticket_id).order_by(TicketReply.created_at.asc()).all()
    reply_list = []
    for reply in replies:
        reply_user = User.query.get(reply.user_id)
        reply_list.append({
            'id': reply.id,
            'user_id': reply.user_id,
            'username': reply_user.username if reply_user else '未知用户',
            'is_admin': reply_user.role in ['admin', 'demo'] if reply_user else False,
            'content': reply.content,
            'is_read': reply.is_read,
            'created_at': reply.created_at.strftime('%Y-%m-%d %H:%M')
        })
    
    # 标记所有回复为已读
    TicketReply.query.filter_by(ticket_id=ticket_id, is_read=0).update({'is_read': 1})
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'data': {
            'ticket': {
                'id': ticket.id,
                'ticket_no': ticket.ticket_no,
                'type': ticket.type,
                'type_text': '用户工单' if ticket.type == 1 else '管理员工单',
                'from_user_id': ticket.from_user_id,
                'from_username': from_user.username if from_user else '未知用户',
                'to_user_id': ticket.to_user_id,
                'to_username': to_user.username if to_user else None,
                'subject': ticket.subject,
                'content': ticket.content,
                'status': ticket.status,
                'status_text': ['待处理', '处理中', '已关闭'][ticket.status],
                'created_at': ticket.created_at.strftime('%Y-%m-%d %H:%M'),
                'updated_at': ticket.updated_at.strftime('%Y-%m-%d %H:%M'),
                'replies': reply_list
            }
        }
    })


@admin_bp.route('/tickets/<int:ticket_id>/reply', methods=['POST'])
@admin_required
@demo_forbidden
def reply_ticket(ticket_id):
    """管理员回复工单"""
    user_id = get_jwt_identity()
    
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'code': 404, 'message': '工单不存在'}), 404
    
    if ticket.status == 2:
        return jsonify({'code': 400, 'message': '工单已关闭，无法回复'}), 400
    
    data = request.get_json()
    content = data.get('content', '').strip()
    
    if not content:
        return jsonify({'code': 400, 'message': '回复内容不能为空'}), 400
    
    # 检查是否包含邮箱
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    if re.search(email_pattern, content):
        return jsonify({'code': 400, 'message': '回复内容不能包含邮箱地址'}), 400
    
    # 创建回复
    reply = TicketReply(
        ticket_id=ticket_id,
        user_id=user_id,
        content=content
    )
    db.session.add(reply)
    
    # 更新工单状态为处理中
    if ticket.status == 0:
        ticket.status = 1
    ticket.updated_at = datetime.now()
    
    db.session.commit()
    
    return jsonify({'code': 200, 'message': '回复成功'})


@admin_bp.route('/tickets/<int:ticket_id>/close', methods=['PUT'])
@admin_required
@demo_forbidden
def close_ticket(ticket_id):
    """管理员关闭工单"""
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'code': 404, 'message': '工单不存在'}), 404
    
    if ticket.status == 2:
        return jsonify({'code': 400, 'message': '工单已关闭'}), 400
    
    ticket.status = 2
    ticket.updated_at = datetime.now()
    db.session.commit()
    
    return jsonify({'code': 200, 'message': '工单已关闭'})


@admin_bp.route('/tickets/stats', methods=['GET'])
@admin_required
def get_ticket_stats():
    """获取工单统计"""
    total = Ticket.query.count()
    pending = Ticket.query.filter_by(status=0).count()
    processing = Ticket.query.filter_by(status=1).count()
    closed = Ticket.query.filter_by(status=2).count()
    
    return jsonify({
        'code': 200,
        'data': {
            'total': total,
            'pending': pending,
            'processing': processing,
            'closed': closed
        }
    })


@admin_bp.route('/tickets/<int:ticket_id>', methods=['DELETE'])
@admin_required
@demo_forbidden
def delete_ticket(ticket_id):
    """删除工单"""
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'code': 404, 'message': '工单不存在'}), 404
    
    # 删除工单的所有回复
    TicketReply.query.filter_by(ticket_id=ticket_id).delete()
    
    # 删除工单
    db.session.delete(ticket)
    db.session.commit()
    
    return jsonify({'code': 200, 'message': '工单已删除'})


@admin_bp.route('/tickets/batch', methods=['DELETE'])
@admin_required
@demo_forbidden
def batch_delete_tickets():
    """批量删除工单"""
    data = request.get_json()
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'code': 400, 'message': '请选择要删除的工单'}), 400
    
    # 删除工单的所有回复
    TicketReply.query.filter(TicketReply.ticket_id.in_(ids)).delete(synchronize_session=False)
    
    # 删除工单
    deleted = Ticket.query.filter(Ticket.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    
    return jsonify({'code': 200, 'message': f'已删除 {deleted} 个工单'})
