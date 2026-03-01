"""
工单服务
提供工单相关的业务逻辑
"""
import logging
from typing import Dict, Any, Optional
from app import db
from app.models.ticket import Ticket, TicketReply
from app.utils.timezone import now as beijing_now

logger = logging.getLogger(__name__)


class TicketService:
    """工单服务"""
    
    @classmethod
    def create_ticket(cls, user_id: int, subject: str, content: str,
                     to_user_id: int = None) -> Dict[str, Any]:
        """
        创建工单
        
        Args:
            user_id: 发起用户ID
            subject: 工单主题
            content: 工单内容
            to_user_id: 接收用户ID（可选，默认发给管理员）
            
        Returns:
            Dict: 包含 success, ticket_id
        """
        try:
            ticket_no = Ticket.generate_ticket_no()
            ticket_type = Ticket.TYPE_USER_TO_USER if to_user_id else Ticket.TYPE_USER_TO_ADMIN
            
            ticket = Ticket(
                ticket_no=ticket_no,
                type=ticket_type,
                from_user_id=user_id,
                to_user_id=to_user_id,
                subject=subject,
                content=content,
                status=Ticket.STATUS_PENDING
            )
            
            db.session.add(ticket)
            db.session.commit()
            
            logger.info(f"Ticket created: {ticket_no} by user {user_id}")
            
            return {
                'success': True,
                'ticket_id': ticket.id,
                'ticket_no': ticket_no
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Create ticket failed: {e}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def reply_ticket(cls, ticket_id: int, user_id: int, content: str,
                    is_admin: bool = False) -> Dict[str, Any]:
        """
        回复工单
        
        Args:
            ticket_id: 工单ID
            user_id: 回复用户ID
            content: 回复内容
            is_admin: 是否管理员回复
            
        Returns:
            Dict: 包含 success
        """
        try:
            ticket = Ticket.query.get(ticket_id)
            if not ticket:
                return {'success': False, 'error': '工单不存在'}
            
            if ticket.status == Ticket.STATUS_CLOSED:
                return {'success': False, 'error': '工单已关闭'}
            
            # 验证权限
            if not is_admin and ticket.from_user_id != user_id:
                return {'success': False, 'error': '无权回复此工单'}
            
            reply = TicketReply(
                ticket_id=ticket_id,
                user_id=user_id,
                content=content
            )
            
            db.session.add(reply)
            
            # 更新工单状态
            if is_admin:
                ticket.status = Ticket.STATUS_PROCESSING
            
            ticket.updated_at = beijing_now()
            db.session.commit()
            
            logger.info(f"Ticket {ticket_id} replied by user {user_id}")
            
            return {'success': True, 'reply_id': reply.id}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Reply ticket failed: {e}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def close_ticket(cls, ticket_id: int, user_id: int,
                    is_admin: bool = False) -> Dict[str, Any]:
        """
        关闭工单
        
        Args:
            ticket_id: 工单ID
            user_id: 操作用户ID
            is_admin: 是否管理员
            
        Returns:
            Dict: 包含 success
        """
        try:
            ticket = Ticket.query.get(ticket_id)
            if not ticket:
                return {'success': False, 'error': '工单不存在'}
            
            # 验证权限
            if not is_admin and ticket.from_user_id != user_id:
                return {'success': False, 'error': '无权关闭此工单'}
            
            ticket.status = Ticket.STATUS_CLOSED
            ticket.updated_at = beijing_now()
            db.session.commit()
            
            logger.info(f"Ticket {ticket_id} closed by user {user_id}")
            
            return {'success': True}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Close ticket failed: {e}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def get_user_tickets(cls, user_id: int, page: int = 1,
                        per_page: int = 20) -> Dict[str, Any]:
        """
        获取用户工单列表
        
        Args:
            user_id: 用户ID
            page: 页码
            per_page: 每页数量
            
        Returns:
            Dict: 分页的工单列表
        """
        query = Ticket.query.filter_by(from_user_id=user_id)\
            .order_by(Ticket.updated_at.desc())
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return {
            'items': [t.to_dict() for t in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'page': page
        }
