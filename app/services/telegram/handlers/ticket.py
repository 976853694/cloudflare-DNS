"""
工单系统处理器

处理工单相关的所有交互：
- 工单菜单
- 创建工单
- 工单列表
- 工单详情
- 回复工单
"""

from typing import Dict, Any
from .base import BaseHandler
from ..utils.session import SessionManager


class TicketHandler(BaseHandler):
    """工单系统处理器"""
    
    PAGE_SIZE = 5
    
    def handle_callback(self, chat_id: int, message_id: int,
                       telegram_id: int, user_info: Dict, data: str):
        """
        处理回调
        
        Args:
            chat_id: 聊天 ID
            message_id: 消息 ID
            telegram_id: Telegram 用户 ID
            user_info: 用户信息
            data: 回调数据
        """
        # 检查绑定
        if not self.require_bind(chat_id, telegram_id, message_id):
            return
        
        # 解析回调数据
        parts = data.split(':')
        action = parts[1] if len(parts) > 1 else ''
        
        try:
            if action == 'menu':
                self.show_ticket_menu(chat_id, message_id, telegram_id)
            
            elif action == 'create':
                self.start_create_ticket(chat_id, message_id, telegram_id)
            
            elif action == 'list':
                page = int(parts[2]) if len(parts) > 2 else 1
                self.show_ticket_list(chat_id, message_id, telegram_id, page)
            
            elif action == 'detail':
                ticket_id = int(parts[2]) if len(parts) > 2 else 0
                self.show_ticket_detail(chat_id, message_id, telegram_id, ticket_id)
            
            elif action == 'reply':
                ticket_id = int(parts[2]) if len(parts) > 2 else 0
                self.start_reply_ticket(chat_id, message_id, telegram_id, ticket_id)
            
            elif action == 'close':
                ticket_id = int(parts[2]) if len(parts) > 2 else 0
                self.close_ticket(chat_id, message_id, telegram_id, ticket_id)
            
            else:
                self._show_error(chat_id, message_id, telegram_id, '未知操作')
                
        except Exception as e:
            print(f'[TicketHandler] Callback error: {e}')
            import traceback
            traceback.print_exc()
            self._show_error(chat_id, message_id, telegram_id, str(e))
    
    def handle_text_input(self, chat_id: int, telegram_id: int,
                         text: str, session: Dict) -> bool:
        """
        处理文本输入
        
        Args:
            chat_id: 聊天 ID
            telegram_id: Telegram 用户 ID
            text: 输入文本
            session: 会话数据
            
        Returns:
            是否已处理
        """
        state = session.get('state', '')
        data = session.get('data', {})
        
        if state == SessionManager.TICKET_INPUT_SUBJECT:
            return self._handle_subject_input(chat_id, telegram_id, text, data)
        
        elif state == SessionManager.TICKET_INPUT_CONTENT:
            return self._handle_content_input(chat_id, telegram_id, text, data)
        
        elif state == SessionManager.TICKET_INPUT_REPLY:
            return self._handle_reply_input(chat_id, telegram_id, text, data)
        
        return False
    
    def show_ticket_menu(self, chat_id: int, message_id: int, telegram_id: int):
        """显示工单菜单"""
        text = self.get_text('ticket.title', telegram_id)
        
        buttons = [
            [{'text': self.get_text('ticket.btn_create', telegram_id),
              'callback_data': 'ticket:create'}],
            [{'text': self.get_text('ticket.btn_list', telegram_id),
              'callback_data': 'ticket:list:1'}],
            [{'text': self.get_text('common.main_menu', telegram_id),
              'callback_data': 'menu:main'}]
        ]
        
        self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
    
    def start_create_ticket(self, chat_id: int, message_id: int, telegram_id: int):
        """开始创建工单流程"""
        # 设置会话状态
        self.set_session_state(chat_id, SessionManager.TICKET_INPUT_SUBJECT, {})
        
        text = self.get_text('ticket.input_subject', telegram_id)
        
        buttons = [[{'text': self.get_text('common.cancel', telegram_id),
                    'callback_data': 'ticket:menu'}]]
        
        self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
    
    def _handle_subject_input(self, chat_id: int, telegram_id: int,
                             text: str, data: Dict) -> bool:
        """处理工单主题输入"""
        subject = text.strip()
        
        if len(subject) < 2:
            msg = "❌ 主题太短，请输入至少2个字符"
            buttons = [[{'text': self.get_text('common.cancel', telegram_id),
                        'callback_data': 'ticket:menu'}]]
            self.send_message(chat_id, msg, self.make_keyboard(buttons))
            return True
        
        if len(subject) > 100:
            msg = "❌ 主题太长，请控制在100个字符以内"
            buttons = [[{'text': self.get_text('common.cancel', telegram_id),
                        'callback_data': 'ticket:menu'}]]
            self.send_message(chat_id, msg, self.make_keyboard(buttons))
            return True
        
        # 更新会话状态
        self.set_session_state(chat_id, SessionManager.TICKET_INPUT_CONTENT, {
            'subject': subject
        })
        
        text = self.get_text('ticket.input_content', telegram_id)
        buttons = [[{'text': self.get_text('common.cancel', telegram_id),
                    'callback_data': 'ticket:menu'}]]
        
        self.send_message(chat_id, text, self.make_keyboard(buttons))
        return True
    
    def _handle_content_input(self, chat_id: int, telegram_id: int,
                             text: str, data: Dict) -> bool:
        """处理工单内容输入"""
        content = text.strip()
        subject = data.get('subject', '')
        
        if len(content) < 10:
            msg = "❌ 内容太短，请详细描述您的问题（至少10个字符）"
            buttons = [[{'text': self.get_text('common.cancel', telegram_id),
                        'callback_data': 'ticket:menu'}]]
            self.send_message(chat_id, msg, self.make_keyboard(buttons))
            return True
        
        user = self.get_user(telegram_id)
        if not user:
            return True
        
        # 清除会话
        self.clear_session_state(chat_id)
        
        try:
            from app.services.ticket_service import TicketService
            
            result = TicketService.create_ticket(
                user_id=user.id,
                subject=subject,
                content=content
            )
            
            if result.get('success'):
                ticket_id = result.get('ticket_id')
                text = self.get_text('ticket.create_success', telegram_id,
                    ticket_id=ticket_id, subject=subject)
            else:
                text = self.get_text('ticket.create_error', telegram_id)
            
            buttons = [
                [{'text': '📋 我的工单', 'callback_data': 'ticket:list:1'}],
                [{'text': self.get_text('common.main_menu', telegram_id),
                  'callback_data': 'menu:main'}]
            ]
            
            self.send_message(chat_id, text, self.make_keyboard(buttons))
            return True
            
        except Exception as e:
            print(f'[TicketHandler] Create ticket error: {e}')
            self.send_message(chat_id, '❌ 创建工单失败，请稍后重试')
            return True

    def show_ticket_list(self, chat_id: int, message_id: int,
                        telegram_id: int, page: int = 1):
        """显示工单列表"""
        user = self.get_user(telegram_id)
        if not user:
            return
        
        try:
            from app.models.ticket import Ticket
            
            query = Ticket.query.filter_by(from_user_id=user.id)\
                .order_by(Ticket.updated_at.desc())
            
            total = query.count()
            total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            page = max(1, min(page, total_pages))
            
            tickets = query.offset((page - 1) * self.PAGE_SIZE).limit(self.PAGE_SIZE).all()
            
            text = self.get_text('ticket.list_title', telegram_id) + "\n\n"
            
            if not tickets:
                text += self.get_text('ticket.no_tickets', telegram_id)
            else:
                status_map = {
                    Ticket.STATUS_PENDING: self.get_text('ticket.status_pending', telegram_id),
                    Ticket.STATUS_PROCESSING: self.get_text('ticket.status_processing', telegram_id),
                    Ticket.STATUS_CLOSED: self.get_text('ticket.status_closed', telegram_id)
                }
                
                for ticket in tickets:
                    status = status_map.get(ticket.status, str(ticket.status))
                    time_str = ticket.updated_at.strftime('%m-%d %H:%M')
                    
                    text += f"{status} #{ticket.id}\n"
                    text += f"  {ticket.subject[:30]}{'...' if len(ticket.subject) > 30 else ''}\n"
                    text += f"  {time_str}\n\n"
            
            # 工单按钮
            buttons = []
            for ticket in tickets:
                buttons.append([{
                    'text': f'#{ticket.id} {ticket.subject[:20]}',
                    'callback_data': f'ticket:detail:{ticket.id}'
                }])
            
            # 分页按钮
            nav_row = []
            if page > 1:
                nav_row.append({'text': '⬅️', 'callback_data': f'ticket:list:{page-1}'})
            if total_pages > 0:
                nav_row.append({'text': f'{page}/{total_pages}', 'callback_data': 'noop'})
            if page < total_pages:
                nav_row.append({'text': '➡️', 'callback_data': f'ticket:list:{page+1}'})
            if nav_row:
                buttons.append(nav_row)
            
            buttons.append([{'text': '📝 创建工单', 'callback_data': 'ticket:create'}])
            buttons.append([{'text': self.get_text('common.main_menu', telegram_id),
                           'callback_data': 'menu:main'}])
            
            self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
            
        except Exception as e:
            print(f'[TicketHandler] List error: {e}')
            import traceback
            traceback.print_exc()
            self._show_error(chat_id, message_id, telegram_id, '获取工单列表失败')
    
    def show_ticket_detail(self, chat_id: int, message_id: int,
                          telegram_id: int, ticket_id: int):
        """显示工单详情"""
        user = self.get_user(telegram_id)
        if not user:
            return
        
        try:
            from app.models.ticket import Ticket, TicketReply
            
            ticket = Ticket.query.filter_by(id=ticket_id, from_user_id=user.id).first()
            if not ticket:
                self._show_error(chat_id, message_id, telegram_id,
                    self.get_text('ticket.error_not_found', telegram_id))
                return
            
            status_map = {
                Ticket.STATUS_PENDING: self.get_text('ticket.status_pending', telegram_id),
                Ticket.STATUS_PROCESSING: self.get_text('ticket.status_processing', telegram_id),
                Ticket.STATUS_CLOSED: self.get_text('ticket.status_closed', telegram_id)
            }
            status = status_map.get(ticket.status, str(ticket.status))
            
            text = self.get_text('ticket.detail_title', telegram_id) + "\n\n"
            text += self.get_text('ticket.detail_info', telegram_id,
                ticket_id=ticket.id,
                subject=ticket.subject,
                status=status,
                created_at=ticket.created_at.strftime('%Y-%m-%d %H:%M')
            )
            
            # 显示原始内容
            text += f"\n\n📝 问题描述：\n{ticket.content[:500]}"
            if len(ticket.content) > 500:
                text += "..."
            
            # 显示回复记录
            replies = TicketReply.query.filter_by(ticket_id=ticket_id)\
                .order_by(TicketReply.created_at.asc()).limit(5).all()
            
            if replies:
                text += f"\n\n{self.get_text('ticket.reply_title', telegram_id)}\n"
                for reply in replies:
                    # 判断是否为管理员回复（回复人不是工单发起人）
                    is_admin = reply.user_id != ticket.from_user_id
                    role = self.get_text('ticket.reply_admin', telegram_id) if is_admin \
                        else self.get_text('ticket.reply_user', telegram_id)
                    time_str = reply.created_at.strftime('%m-%d %H:%M')
                    content_preview = reply.content[:100]
                    if len(reply.content) > 100:
                        content_preview += "..."
                    text += f"\n{role}（{time_str}）：\n{content_preview}\n"
            
            buttons = []
            
            # 如果工单未关闭，显示回复和关闭按钮
            if ticket.status != Ticket.STATUS_CLOSED:
                buttons.append([
                    {'text': self.get_text('ticket.btn_reply', telegram_id),
                     'callback_data': f'ticket:reply:{ticket_id}'},
                    {'text': self.get_text('ticket.btn_close', telegram_id),
                     'callback_data': f'ticket:close:{ticket_id}'}
                ])
            
            buttons.append([{'text': '📋 工单列表', 'callback_data': 'ticket:list:1'}])
            buttons.append([{'text': self.get_text('common.main_menu', telegram_id),
                           'callback_data': 'menu:main'}])
            
            self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
            
        except Exception as e:
            print(f'[TicketHandler] Detail error: {e}')
            import traceback
            traceback.print_exc()
            self._show_error(chat_id, message_id, telegram_id, '获取工单详情失败')
    
    def start_reply_ticket(self, chat_id: int, message_id: int,
                          telegram_id: int, ticket_id: int):
        """开始回复工单"""
        user = self.get_user(telegram_id)
        if not user:
            return
        
        try:
            from app.models.ticket import Ticket
            
            ticket = Ticket.query.filter_by(id=ticket_id, from_user_id=user.id).first()
            if not ticket:
                self._show_error(chat_id, message_id, telegram_id, '工单不存在')
                return
            
            if ticket.status == Ticket.STATUS_CLOSED:
                self._show_error(chat_id, message_id, telegram_id,
                    self.get_text('ticket.error_closed', telegram_id))
                return
            
            # 设置会话状态
            self.set_session_state(chat_id, SessionManager.TICKET_INPUT_REPLY, {
                'ticket_id': ticket_id
            })
            
            text = self.get_text('ticket.input_reply', telegram_id)
            buttons = [[{'text': self.get_text('common.cancel', telegram_id),
                        'callback_data': f'ticket:detail:{ticket_id}'}]]
            
            self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
            
        except Exception as e:
            print(f'[TicketHandler] Start reply error: {e}')
            self._show_error(chat_id, message_id, telegram_id, '操作失败')
    
    def _handle_reply_input(self, chat_id: int, telegram_id: int,
                           text: str, data: Dict) -> bool:
        """处理工单回复输入"""
        content = text.strip()
        ticket_id = data.get('ticket_id')
        
        if len(content) < 2:
            msg = "❌ 回复内容太短"
            buttons = [[{'text': self.get_text('common.cancel', telegram_id),
                        'callback_data': f'ticket:detail:{ticket_id}'}]]
            self.send_message(chat_id, msg, self.make_keyboard(buttons))
            return True
        
        user = self.get_user(telegram_id)
        if not user:
            return True
        
        # 清除会话
        self.clear_session_state(chat_id)
        
        try:
            from app.services.ticket_service import TicketService
            
            result = TicketService.reply_ticket(
                ticket_id=ticket_id,
                user_id=user.id,
                content=content,
                is_admin=False
            )
            
            if result.get('success'):
                text = self.get_text('ticket.reply_success', telegram_id)
            else:
                text = self.get_text('ticket.reply_error', telegram_id)
            
            buttons = [
                [{'text': '📋 查看工单', 'callback_data': f'ticket:detail:{ticket_id}'}],
                [{'text': self.get_text('common.main_menu', telegram_id),
                  'callback_data': 'menu:main'}]
            ]
            
            self.send_message(chat_id, text, self.make_keyboard(buttons))
            return True
            
        except Exception as e:
            print(f'[TicketHandler] Reply error: {e}')
            self.send_message(chat_id, '❌ 回复失败，请稍后重试')
            return True
    
    def close_ticket(self, chat_id: int, message_id: int,
                    telegram_id: int, ticket_id: int):
        """关闭工单"""
        user = self.get_user(telegram_id)
        if not user:
            return
        
        try:
            from app.services.ticket_service import TicketService
            
            result = TicketService.close_ticket(ticket_id, user.id)
            
            if result.get('success'):
                text = self.get_text('ticket.close_success', telegram_id)
            else:
                text = self.get_text('ticket.close_error', telegram_id)
            
            buttons = [
                [{'text': '📋 工单列表', 'callback_data': 'ticket:list:1'}],
                [{'text': self.get_text('common.main_menu', telegram_id),
                  'callback_data': 'menu:main'}]
            ]
            
            self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
            
        except Exception as e:
            print(f'[TicketHandler] Close ticket error: {e}')
            self._show_error(chat_id, message_id, telegram_id, '关闭失败')
    
    def _show_error(self, chat_id: int, message_id: int,
                   telegram_id: int, error: str):
        """显示错误消息"""
        text = f"❌ {error}"
        buttons = [[{'text': self.get_text('common.main_menu', telegram_id),
                    'callback_data': 'menu:main'}]]
        self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
