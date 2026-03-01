"""
工单路由
"""
import re
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import User, Setting
from app.models.ticket import Ticket, TicketReply

ticket_bp = Blueprint('ticket', __name__)

# 邮箱正则
EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'


def contains_email(text):
    """检测文本中是否包含邮箱"""
    return bool(re.search(EMAIL_PATTERN, text))


def send_ticket_email(email_type, ticket, reply_content=None, reply_user=None, notify_admin=False, notify_user_id=None):
    """
    发送工单邮件通知
    
    Args:
        email_type: 邮件类型 (new/reply/closed)
        ticket: 工单对象
        reply_content: 回复内容（仅回复时需要）
        reply_user: 回复人用户名（仅回复时需要）
        notify_admin: 是否通知管理员
        notify_user_id: 指定通知的用户ID（用户对用户工单）
    """
    try:
        from app.services.email import EmailService
        from app.services.email_templates import EmailTemplateService
        
        if not EmailService.is_configured():
            return
        
        site_url = Setting.get('site_url', request.host_url.rstrip('/'))
        
        if email_type == 'new':
            if ticket.type == Ticket.TYPE_USER_TO_ADMIN:
                # 用户对管理员工单，通知管理员
                admin_email = Setting.get('support_email')
                if admin_email:
                    from_user = User.query.get(ticket.from_user_id)
                    subject, html = EmailTemplateService.render_email('ticket_new', {
                        'ticket_no': ticket.ticket_no,
                        'subject': ticket.subject,
                        'content': ticket.content,
                        'from_user': from_user.username if from_user else '未知用户',
                        'ticket_url': f"{site_url}/admin/tickets"
                    })
                    if subject and html:
                        EmailService.send(admin_email, subject, html)
            elif ticket.type == Ticket.TYPE_USER_TO_USER:
                # 用户对用户工单，通知接收用户
                to_user = User.query.get(ticket.to_user_id)
                if to_user and to_user.email:
                    from_user = User.query.get(ticket.from_user_id)
                    subject, html = EmailTemplateService.render_email('ticket_new', {
                        'ticket_no': ticket.ticket_no,
                        'subject': ticket.subject,
                        'content': ticket.content,
                        'from_user': from_user.username if from_user else '未知用户',
                        'ticket_url': f"{site_url}/tickets"
                    })
                    if subject and html:
                        EmailService.send(to_user.email, subject, html)
                
        elif email_type == 'reply':
            if notify_user_id:
                # 通知指定用户（用户对用户工单）
                target_user = User.query.get(notify_user_id)
                if target_user and target_user.email:
                    subject, html = EmailTemplateService.render_email('ticket_reply', {
                        'ticket_no': ticket.ticket_no,
                        'subject': ticket.subject,
                        'reply_content': reply_content,
                        'reply_user': reply_user,
                        'ticket_url': f"{site_url}/tickets"
                    })
                    if subject and html:
                        EmailService.send(target_user.email, subject, html)
            elif notify_admin:
                # 用户回复，通知管理员
                admin_email = Setting.get('support_email')
                if admin_email:
                    subject, html = EmailTemplateService.render_email('ticket_reply', {
                        'ticket_no': ticket.ticket_no,
                        'subject': ticket.subject,
                        'reply_content': reply_content,
                        'reply_user': reply_user,
                        'ticket_url': f"{site_url}/admin/tickets"
                    })
                    if subject and html:
                        EmailService.send(admin_email, subject, html)
            else:
                # 管理员回复，通知用户
                from_user = User.query.get(ticket.from_user_id)
                if from_user and from_user.email:
                    subject, html = EmailTemplateService.render_email('ticket_reply', {
                        'ticket_no': ticket.ticket_no,
                        'subject': ticket.subject,
                        'reply_content': reply_content,
                        'reply_user': reply_user,
                        'ticket_url': f"{site_url}/tickets"
                    })
                    if subject and html:
                        EmailService.send(from_user.email, subject, html)
                    
        elif email_type == 'closed':
            # 工单关闭通知
            from_user = User.query.get(ticket.from_user_id)
            if from_user and from_user.email:
                subject, html = EmailTemplateService.render_email('ticket_closed', {
                    'ticket_no': ticket.ticket_no,
                    'subject': ticket.subject,
                    'ticket_url': f"{site_url}/tickets"
                })
                if subject and html:
                    EmailService.send(from_user.email, subject, html)
                
    except Exception as e:
        current_app.logger.error(f'发送工单邮件失败: {e}')


@ticket_bp.route('/api/tickets', methods=['GET'])
@jwt_required()
def get_tickets():
    """获取工单列表"""
    user_id = int(get_jwt_identity())
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status', type=int)
    ticket_type = request.args.get('type', type=int)
    
    # 查询用户相关的工单（发起的或接收的）
    # 只显示：1. 用户发起的工单  2. 用户接收的工单（to_user_id 必须等于当前用户）
    # 注意：to_user_id 为 None 的工单（用户对管理员）只有发起人能看到
    query = Ticket.query.filter(
        db.or_(
            Ticket.from_user_id == user_id,
            db.and_(
                Ticket.to_user_id.isnot(None),
                Ticket.to_user_id == user_id
            )
        )
    )
    
    if status is not None:
        query = query.filter(Ticket.status == status)
    if ticket_type is not None:
        query = query.filter(Ticket.type == ticket_type)
    
    pagination = query.order_by(Ticket.updated_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'code': 200,
        'data': {
            'tickets': [t.to_dict() for t in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'page': page
        }
    })


@ticket_bp.route('/api/tickets', methods=['POST'])
@jwt_required()
def create_ticket():
    """创建工单"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    subject = data.get('subject', '').strip()
    content = data.get('content', '').strip()
    ticket_type = int(data.get('type', Ticket.TYPE_USER_TO_ADMIN))
    to_username = data.get('to_username', '').strip()
    to_user_id_param = data.get('to_user_id')  # 支持直接传用户ID（从WHOIS页面跳转）
    
    if not subject:
        return jsonify({'code': 400, 'message': '请输入工单标题'}), 400
    if not content:
        return jsonify({'code': 400, 'message': '请输入工单内容'}), 400
    if len(subject) > 200:
        return jsonify({'code': 400, 'message': '标题不能超过200字'}), 400
    
    # 检查邮箱
    if contains_email(subject) or contains_email(content):
        return jsonify({'code': 400, 'message': '工单内容不能包含邮箱地址'}), 400
    
    to_user_id = None
    if ticket_type == Ticket.TYPE_USER_TO_USER:
        # 优先使用 to_user_id 参数
        if to_user_id_param:
            to_user = User.query.get(int(to_user_id_param))
            if not to_user:
                return jsonify({'code': 400, 'message': '接收用户不存在'}), 400
            if to_user.id == user_id:
                return jsonify({'code': 400, 'message': '不能给自己发送工单'}), 400
            to_user_id = to_user.id
        elif to_username:
            to_user = User.query.filter_by(username=to_username).first()
            if not to_user:
                return jsonify({'code': 400, 'message': '接收用户不存在'}), 400
            if to_user.id == user_id:
                return jsonify({'code': 400, 'message': '不能给自己发送工单'}), 400
            to_user_id = to_user.id
        else:
            return jsonify({'code': 400, 'message': '请选择接收用户'}), 400
    
    ticket = Ticket(
        ticket_no=Ticket.generate_ticket_no(),
        type=ticket_type,
        from_user_id=user_id,
        to_user_id=to_user_id,
        subject=subject,
        content=content
    )
    db.session.add(ticket)
    db.session.commit()
    
    # 发送邮件通知
    send_ticket_email('new', ticket)
    
    return jsonify({
        'code': 200,
        'message': '工单创建成功',
        'data': {'ticket': ticket.to_dict()}
    })


@ticket_bp.route('/api/tickets/<int:ticket_id>', methods=['GET'])
@jwt_required()
def get_ticket(ticket_id):
    """获取工单详情"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'code': 404, 'message': '工单不存在'}), 404
    
    # 权限检查：发起人、接收人、管理员可查看
    is_admin = user and user.role == 'admin'
    if ticket.from_user_id != user_id and ticket.to_user_id != user_id and not is_admin:
        if not (ticket.type == Ticket.TYPE_USER_TO_ADMIN and is_admin):
            return jsonify({'code': 403, 'message': '无权查看此工单'}), 403
    
    # 标记回复为已读
    TicketReply.query.filter(
        TicketReply.ticket_id == ticket_id,
        TicketReply.user_id != user_id,
        TicketReply.is_read == 0
    ).update({'is_read': 1})
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'data': {'ticket': ticket.to_dict(include_replies=True)}
    })


@ticket_bp.route('/api/tickets/<int:ticket_id>/reply', methods=['POST'])
@jwt_required()
def reply_ticket(ticket_id):
    """回复工单"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    data = request.get_json()
    
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'code': 400, 'message': '请输入回复内容'}), 400
    
    # 检查邮箱
    if contains_email(content):
        return jsonify({'code': 400, 'message': '回复内容不能包含邮箱地址'}), 400
    
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'code': 404, 'message': '工单不存在'}), 404
    
    if ticket.status == Ticket.STATUS_CLOSED:
        return jsonify({'code': 400, 'message': '工单已关闭，无法回复'}), 400
    
    # 权限检查
    is_admin = user and user.role == 'admin'
    if ticket.from_user_id != user_id and ticket.to_user_id != user_id and not is_admin:
        if not (ticket.type == Ticket.TYPE_USER_TO_ADMIN and is_admin):
            return jsonify({'code': 403, 'message': '无权回复此工单'}), 403
    
    reply = TicketReply(
        ticket_id=ticket_id,
        user_id=user_id,
        content=content
    )
    db.session.add(reply)
    
    # 更新工单状态为处理中
    if ticket.status == Ticket.STATUS_PENDING:
        ticket.status = Ticket.STATUS_PROCESSING
    
    db.session.commit()
    
    # 发送邮件通知
    if ticket.type == Ticket.TYPE_USER_TO_ADMIN:
        if is_admin:
            # 管理员回复，通知用户
            send_ticket_email('reply', ticket, content, user.username, notify_admin=False)
        else:
            # 用户回复，通知管理员
            send_ticket_email('reply', ticket, content, user.username, notify_admin=True)
    elif ticket.type == Ticket.TYPE_USER_TO_USER:
        # 用户对用户工单，通知对方
        if user_id == ticket.from_user_id:
            # 发起人回复，通知接收人
            send_ticket_email('reply', ticket, content, user.username, notify_user_id=ticket.to_user_id)
        else:
            # 接收人回复，通知发起人
            send_ticket_email('reply', ticket, content, user.username, notify_user_id=ticket.from_user_id)
    
    return jsonify({
        'code': 200,
        'message': '回复成功',
        'data': {'reply': reply.to_dict()}
    })


@ticket_bp.route('/api/tickets/<int:ticket_id>/close', methods=['PUT'])
@jwt_required()
def close_ticket(ticket_id):
    """关闭工单"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'code': 404, 'message': '工单不存在'}), 404
    
    # 权限检查：发起人、接收人、管理员可关闭
    is_admin = user and user.role == 'admin'
    if ticket.from_user_id != user_id and ticket.to_user_id != user_id and not is_admin:
        return jsonify({'code': 403, 'message': '无权关闭此工单'}), 403
    
    ticket.status = Ticket.STATUS_CLOSED
    db.session.commit()
    
    # 管理员关闭工单时通知用户
    if is_admin and ticket.type == Ticket.TYPE_USER_TO_ADMIN:
        send_ticket_email('closed', ticket)
    
    return jsonify({
        'code': 200,
        'message': '工单已关闭'
    })


@ticket_bp.route('/api/users/search', methods=['GET'])
@jwt_required()
def search_users():
    """搜索用户（用于选择接收人）"""
    user_id = int(get_jwt_identity())
    q = request.args.get('q', '').strip()
    
    if not q or len(q) < 2:
        return jsonify({'code': 200, 'data': {'users': []}})
    
    users = User.query.filter(
        User.username.ilike(f'%{q}%'),
        User.id != user_id,
        User.status == 1
    ).limit(10).all()
    
    return jsonify({
        'code': 200,
        'data': {
            'users': [{'id': u.id, 'username': u.username} for u in users]
        }
    })


@ticket_bp.route('/api/tickets/unread', methods=['GET'])
@jwt_required()
def get_unread_tickets():
    """获取未读工单信息"""
    user_id = int(get_jwt_identity())
    
    # 查询用户相关的工单中有未读回复的
    # 只查询：1. 用户发起的工单  2. 用户接收的工单（to_user_id 必须等于当前用户）
    tickets_with_unread = db.session.query(Ticket).join(
        TicketReply, Ticket.id == TicketReply.ticket_id
    ).filter(
        db.or_(
            Ticket.from_user_id == user_id,
            db.and_(
                Ticket.to_user_id.isnot(None),
                Ticket.to_user_id == user_id
            )
        ),
        TicketReply.user_id != user_id,
        TicketReply.is_read == 0
    ).distinct().all()
    
    # 统计未读数量
    unread_count = db.session.query(db.func.count(TicketReply.id)).join(
        Ticket, Ticket.id == TicketReply.ticket_id
    ).filter(
        db.or_(
            Ticket.from_user_id == user_id,
            db.and_(
                Ticket.to_user_id.isnot(None),
                Ticket.to_user_id == user_id
            )
        ),
        TicketReply.user_id != user_id,
        TicketReply.is_read == 0
    ).scalar() or 0
    
    # 获取最新的未读工单（用于弹窗显示）
    popup_tickets = []
    for ticket in tickets_with_unread[:3]:  # 最多显示3个
        # 获取该工单的未读回复数
        ticket_unread = TicketReply.query.filter(
            TicketReply.ticket_id == ticket.id,
            TicketReply.user_id != user_id,
            TicketReply.is_read == 0
        ).count()
        
        # 获取最新的未读回复
        latest_reply = TicketReply.query.filter(
            TicketReply.ticket_id == ticket.id,
            TicketReply.user_id != user_id,
            TicketReply.is_read == 0
        ).order_by(TicketReply.created_at.desc()).first()
        
        if latest_reply:
            popup_tickets.append({
                'id': ticket.id,
                'ticket_no': ticket.ticket_no,
                'subject': ticket.subject,
                'unread_count': ticket_unread,
                'latest_reply': latest_reply.content[:100] + ('...' if len(latest_reply.content) > 100 else ''),
                'reply_time': latest_reply.created_at.strftime('%Y-%m-%d %H:%M')
            })
    
    return jsonify({
        'code': 200,
        'data': {
            'unread_count': unread_count,
            'popup_tickets': popup_tickets
        }
    })
