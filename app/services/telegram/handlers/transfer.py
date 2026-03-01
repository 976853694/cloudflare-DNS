"""
域名转移处理器

处理域名转移相关的所有交互：
- 发起转移
- 验证转移
- 查看转移记录
"""

from typing import Dict, Any
from .base import BaseHandler
from ..utils.session import SessionManager


class TransferHandler(BaseHandler):
    """域名转移处理器"""
    
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
            if action == 'start':
                # 开始转移流程
                domain_id = int(parts[2]) if len(parts) > 2 else 0
                self.start_transfer(chat_id, message_id, telegram_id, domain_id)
            
            elif action == 'confirm':
                # 确认转移
                domain_id = int(parts[2]) if len(parts) > 2 else 0
                self.confirm_transfer(chat_id, message_id, telegram_id, domain_id)
            
            elif action == 'execute':
                # 执行转移（发送验证码）
                domain_id = int(parts[2]) if len(parts) > 2 else 0
                self.execute_transfer(chat_id, message_id, telegram_id, domain_id)
            
            elif action == 'cancel':
                # 取消转移
                transfer_id = int(parts[2]) if len(parts) > 2 else 0
                self.cancel_transfer(chat_id, message_id, telegram_id, transfer_id)
            
            elif action == 'list':
                # 转移记录列表
                page = int(parts[2]) if len(parts) > 2 else 1
                self.show_transfer_list(chat_id, message_id, telegram_id, page)
            
            elif action == 'detail':
                # 转移详情
                transfer_id = int(parts[2]) if len(parts) > 2 else 0
                self.show_transfer_detail(chat_id, message_id, telegram_id, transfer_id)
            
            elif action == 'resend':
                # 重发验证码
                transfer_id = int(parts[2]) if len(parts) > 2 else 0
                self.resend_code(chat_id, message_id, telegram_id, transfer_id)
            
            else:
                self._show_error(chat_id, message_id, telegram_id, '未知操作')
                
        except Exception as e:
            print(f'[TransferHandler] Callback error: {e}')
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
        
        if state == SessionManager.TRANSFER_INPUT_USER:
            # 输入接收用户
            return self._handle_user_input(chat_id, telegram_id, text, data)
        
        elif state == SessionManager.TRANSFER_INPUT_CODE:
            # 输入验证码
            return self._handle_code_input(chat_id, telegram_id, text, data)
        
        return False
    
    def start_transfer(self, chat_id: int, message_id: int, 
                      telegram_id: int, domain_id: int):
        """开始转移流程，提示输入接收用户"""
        from app.models.subdomain import Subdomain
        from app.services.transfer_service import TransferService
        
        # 检查转移功能是否开启
        config = TransferService.get_config()
        if not config['enabled']:
            text = self.get_text('transfer.error_disabled', telegram_id)
            buttons = [[{'text': self.get_text('common.back', telegram_id), 
                        'callback_data': f'domain:{domain_id}'}]]
            self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
            return
        
        # 获取域名信息
        domain = Subdomain.query.get(domain_id)
        if not domain:
            self._show_error(chat_id, message_id, telegram_id, '域名不存在')
            return
        
        # 验证所有权
        user = self.get_user(telegram_id)
        if not user or domain.user_id != user.id:
            self._show_error(chat_id, message_id, telegram_id, '您不是该域名的所有者')
            return
        
        # 设置会话状态
        self.set_session_state(chat_id, SessionManager.TRANSFER_INPUT_USER, {
            'domain_id': domain_id,
            'domain_name': domain.full_name
        })
        
        # 显示输入提示
        text = f"🔄 <b>域名转移</b>\n\n"
        text += f"域名：{domain.full_name}\n"
        text += f"手续费：{config['fee']} 积分\n\n"
        text += self.get_text('transfer.input_user', telegram_id)
        
        buttons = [[{'text': self.get_text('common.cancel', telegram_id), 
                    'callback_data': f'domain:{domain_id}'}]]
        
        self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
    
    def _handle_user_input(self, chat_id: int, telegram_id: int, 
                          text: str, data: Dict) -> bool:
        """处理接收用户输入"""
        from app.models.user import User
        
        domain_id = data.get('domain_id')
        domain_name = data.get('domain_name')
        to_username = text.strip()
        
        # 验证用户是否存在
        to_user = User.query.filter(
            (User.username == to_username) | (User.email == to_username)
        ).first()
        
        if not to_user:
            text = self.get_text('transfer.error_user_not_found', telegram_id)
            text += f"\n\n请重新输入接收用户的用户名或邮箱："
            buttons = [[{'text': self.get_text('common.cancel', telegram_id), 
                        'callback_data': f'domain:{domain_id}'}]]
            self.send_message(chat_id, text, self.make_keyboard(buttons))
            return True
        
        # 检查是否转给自己
        user = self.get_user(telegram_id)
        if user and to_user.id == user.id:
            text = self.get_text('transfer.error_self', telegram_id)
            text += f"\n\n请重新输入接收用户的用户名或邮箱："
            buttons = [[{'text': self.get_text('common.cancel', telegram_id), 
                        'callback_data': f'domain:{domain_id}'}]]
            self.send_message(chat_id, text, self.make_keyboard(buttons))
            return True
        
        # 更新会话数据
        self.session.update_data(chat_id, 
            to_username=to_user.username,
            to_user_id=to_user.id
        )
        
        # 显示确认信息
        from app.services.transfer_service import TransferService
        config = TransferService.get_config()
        
        text = self.get_text('transfer.confirm_info', telegram_id,
            domain=domain_name,
            to_user=to_user.username,
            fee=config['fee']
        )
        
        buttons = [
            [{'text': self.get_text('transfer.confirm', telegram_id), 
              'callback_data': f'transfer:execute:{domain_id}'}],
            [{'text': self.get_text('common.cancel', telegram_id), 
              'callback_data': f'domain:{domain_id}'}]
        ]
        
        self.send_message(chat_id, text, self.make_keyboard(buttons))
        return True

    def confirm_transfer(self, chat_id: int, message_id: int,
                        telegram_id: int, domain_id: int):
        """显示转移确认信息"""
        session = self.get_session_state(chat_id)
        if not session:
            self._show_error(chat_id, message_id, telegram_id, '会话已过期，请重新开始')
            return
        
        data = session.get('data', {})
        domain_name = data.get('domain_name')
        to_username = data.get('to_username')
        
        from app.services.transfer_service import TransferService
        config = TransferService.get_config()
        
        text = self.get_text('transfer.confirm_info', telegram_id,
            domain=domain_name,
            to_user=to_username,
            fee=config['fee']
        )
        
        buttons = [
            [{'text': self.get_text('transfer.confirm', telegram_id), 
              'callback_data': f'transfer:execute:{domain_id}'}],
            [{'text': self.get_text('common.cancel', telegram_id), 
              'callback_data': f'domain:{domain_id}'}]
        ]
        
        self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
    
    def execute_transfer(self, chat_id: int, message_id: int,
                        telegram_id: int, domain_id: int):
        """执行转移，发送验证码"""
        session = self.get_session_state(chat_id)
        if not session:
            self._show_error(chat_id, message_id, telegram_id, '会话已过期，请重新开始')
            return
        
        data = session.get('data', {})
        to_username = data.get('to_username')
        
        if not to_username:
            self._show_error(chat_id, message_id, telegram_id, '会话数据不完整，请重新开始')
            return
        
        user = self.get_user(telegram_id)
        if not user:
            self._show_error(chat_id, message_id, telegram_id, '用户未绑定')
            return
        
        try:
            from app.services.transfer_service import TransferService
            
            result = TransferService.initiate_transfer(
                user_id=user.id,
                subdomain_id=domain_id,
                to_username=to_username
            )
            
            transfer_id = result['transfer_id']
            
            # 更新会话状态为输入验证码
            self.set_session_state(chat_id, SessionManager.TRANSFER_INPUT_CODE, {
                'transfer_id': transfer_id,
                'domain_id': domain_id,
                'domain_name': data.get('domain_name'),
                'to_username': to_username
            })
            
            # 显示验证码输入提示
            text = self.get_text('transfer.input_code', telegram_id)
            
            buttons = [
                [{'text': '🔄 重发验证码', 'callback_data': f'transfer:resend:{transfer_id}'}],
                [{'text': self.get_text('common.cancel', telegram_id), 
                  'callback_data': f'transfer:cancel:{transfer_id}'}]
            ]
            
            self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
            
            # 发送通知给接收方
            self._notify_recipient(to_username, user.username, data.get('domain_name'))
            
        except ValueError as e:
            error_msg = str(e)
            if '|' in error_msg:
                error_msg = error_msg.split('|')[1]
            self._show_error(chat_id, message_id, telegram_id, error_msg)
        except Exception as e:
            print(f'[TransferHandler] Execute transfer error: {e}')
            self._show_error(chat_id, message_id, telegram_id, '系统错误，请稍后重试')
    
    def _handle_code_input(self, chat_id: int, telegram_id: int,
                          text: str, data: Dict) -> bool:
        """处理验证码输入"""
        transfer_id = data.get('transfer_id')
        verify_code = text.strip()
        
        # 验证码格式检查
        if not verify_code.isdigit() or len(verify_code) != 6:
            msg = "❌ 请输入6位数字验证码"
            buttons = [
                [{'text': '🔄 重发验证码', 'callback_data': f'transfer:resend:{transfer_id}'}],
                [{'text': self.get_text('common.cancel', telegram_id), 
                  'callback_data': f'transfer:cancel:{transfer_id}'}]
            ]
            self.send_message(chat_id, msg, self.make_keyboard(buttons))
            return True
        
        user = self.get_user(telegram_id)
        if not user:
            self.send_message(chat_id, '❌ 用户未绑定')
            return True
        
        try:
            from app.services.transfer_service import TransferService
            
            result = TransferService.verify_transfer(
                user_id=user.id,
                transfer_id=transfer_id,
                verify_code=verify_code
            )
            
            # 清除会话
            self.clear_session_state(chat_id)
            
            # 显示成功消息
            text = self.get_text('transfer.success', telegram_id,
                domain=result['subdomain_name'],
                to_user=result['to_username']
            )
            
            buttons = [
                [{'text': '📋 我的域名', 'callback_data': 'domain:list'}],
                [{'text': self.get_text('common.main_menu', telegram_id), 
                  'callback_data': 'menu:main'}]
            ]
            
            self.send_message(chat_id, text, self.make_keyboard(buttons))
            
            # 发送完成通知
            self._notify_transfer_completed(
                result['subdomain_name'],
                user.username,
                result['to_username']
            )
            
            return True
            
        except ValueError as e:
            error_msg = str(e)
            if '|' in error_msg:
                error_msg = error_msg.split('|')[1]
            
            buttons = [
                [{'text': '🔄 重发验证码', 'callback_data': f'transfer:resend:{transfer_id}'}],
                [{'text': self.get_text('common.cancel', telegram_id), 
                  'callback_data': f'transfer:cancel:{transfer_id}'}]
            ]
            self.send_message(chat_id, f'❌ {error_msg}', self.make_keyboard(buttons))
            return True
        except Exception as e:
            print(f'[TransferHandler] Verify transfer error: {e}')
            self.send_message(chat_id, '❌ 系统错误，请稍后重试')
            return True
    
    def cancel_transfer(self, chat_id: int, message_id: int,
                       telegram_id: int, transfer_id: int):
        """取消转移"""
        user = self.get_user(telegram_id)
        if not user:
            self._show_error(chat_id, message_id, telegram_id, '用户未绑定')
            return
        
        try:
            from app.services.transfer_service import TransferService
            
            TransferService.cancel_transfer(user.id, transfer_id)
            
            # 清除会话
            self.clear_session_state(chat_id)
            
            text = self.get_text('transfer.cancelled', telegram_id)
            buttons = [
                [{'text': '📋 我的域名', 'callback_data': 'domain:list'}],
                [{'text': self.get_text('common.main_menu', telegram_id), 
                  'callback_data': 'menu:main'}]
            ]
            
            self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
            
        except ValueError as e:
            error_msg = str(e)
            if '|' in error_msg:
                error_msg = error_msg.split('|')[1]
            self._show_error(chat_id, message_id, telegram_id, error_msg)
        except Exception as e:
            print(f'[TransferHandler] Cancel transfer error: {e}')
            self._show_error(chat_id, message_id, telegram_id, '系统错误')
    
    def resend_code(self, chat_id: int, message_id: int,
                   telegram_id: int, transfer_id: int):
        """重发验证码"""
        user = self.get_user(telegram_id)
        if not user:
            self._show_error(chat_id, message_id, telegram_id, '用户未绑定')
            return
        
        try:
            from app.services.transfer_service import TransferService
            
            TransferService.resend_code(user.id, transfer_id)
            
            text = "✅ 验证码已重新发送到您的邮箱\n\n请输入6位数字验证码："
            buttons = [
                [{'text': '🔄 重发验证码', 'callback_data': f'transfer:resend:{transfer_id}'}],
                [{'text': self.get_text('common.cancel', telegram_id), 
                  'callback_data': f'transfer:cancel:{transfer_id}'}]
            ]
            
            self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
            
        except ValueError as e:
            error_msg = str(e)
            if '|' in error_msg:
                error_msg = error_msg.split('|')[1]
            self._show_error(chat_id, message_id, telegram_id, error_msg)
        except Exception as e:
            print(f'[TransferHandler] Resend code error: {e}')
            self._show_error(chat_id, message_id, telegram_id, '系统错误')

    def show_transfer_list(self, chat_id: int, message_id: int,
                          telegram_id: int, page: int = 1):
        """显示转移记录列表"""
        user = self.get_user(telegram_id)
        if not user:
            self._show_error(chat_id, message_id, telegram_id, '用户未绑定')
            return
        
        try:
            from app.services.transfer_service import TransferService
            
            result = TransferService.get_user_transfers(
                user_id=user.id,
                page=page,
                per_page=5
            )
            
            items = result['items']
            total_pages = result['pages']
            
            text = self.get_text('transfer.list_title', telegram_id) + "\n\n"
            
            if not items:
                text += self.get_text('transfer.no_records', telegram_id)
            else:
                for item in items:
                    # 状态图标
                    status_map = {
                        0: self.get_text('transfer.status_pending', telegram_id),
                        1: self.get_text('transfer.status_completed', telegram_id),
                        2: self.get_text('transfer.status_cancelled', telegram_id),
                        3: self.get_text('transfer.status_expired', telegram_id)
                    }
                    status = status_map.get(item['status'], '未知')
                    
                    # 方向
                    if item['from_user_id'] == user.id:
                        direction = self.get_text('transfer.direction_out', telegram_id)
                        other_user = item['to_username']
                    else:
                        direction = self.get_text('transfer.direction_in', telegram_id)
                        other_user = item['from_username']
                    
                    text += f"{status} {item['subdomain_name']}\n"
                    text += f"  {direction} {other_user}\n"
                    text += f"  {item['created_at'][:16]}\n\n"
            
            # 分页按钮
            buttons = []
            nav_row = []
            if page > 1:
                nav_row.append({'text': '⬅️', 'callback_data': f'transfer:list:{page-1}'})
            if total_pages > 0:
                nav_row.append({'text': f'{page}/{total_pages}', 'callback_data': 'noop'})
            if page < total_pages:
                nav_row.append({'text': '➡️', 'callback_data': f'transfer:list:{page+1}'})
            if nav_row:
                buttons.append(nav_row)
            
            buttons.append([{'text': self.get_text('common.main_menu', telegram_id), 
                           'callback_data': 'menu:main'}])
            
            self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
            
        except Exception as e:
            print(f'[TransferHandler] Show transfer list error: {e}')
            self._show_error(chat_id, message_id, telegram_id, '获取记录失败')
    
    def show_transfer_detail(self, chat_id: int, message_id: int,
                            telegram_id: int, transfer_id: int):
        """显示转移详情"""
        from app.models.domain_transfer import DomainTransfer
        
        transfer = DomainTransfer.query.get(transfer_id)
        if not transfer:
            self._show_error(chat_id, message_id, telegram_id, '转移记录不存在')
            return
        
        user = self.get_user(telegram_id)
        if not user or (transfer.from_user_id != user.id and transfer.to_user_id != user.id):
            self._show_error(chat_id, message_id, telegram_id, '无权查看此记录')
            return
        
        # 状态
        status_map = {
            0: self.get_text('transfer.status_pending', telegram_id),
            1: self.get_text('transfer.status_completed', telegram_id),
            2: self.get_text('transfer.status_cancelled', telegram_id),
            3: self.get_text('transfer.status_expired', telegram_id)
        }
        status = status_map.get(transfer.status, '未知')
        
        text = f"🔄 <b>转移详情</b>\n\n"
        text += f"域名：{transfer.subdomain_name}\n"
        text += f"状态：{status}\n"
        text += f"发起方：{transfer.from_username}\n"
        text += f"接收方：{transfer.to_username}\n"
        text += f"手续费：{transfer.fee_points} 积分\n"
        text += f"创建时间：{transfer.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        
        if transfer.completed_at:
            text += f"完成时间：{transfer.completed_at.strftime('%Y-%m-%d %H:%M')}\n"
        
        buttons = [
            [{'text': '📋 转移记录', 'callback_data': 'transfer:list:1'}],
            [{'text': self.get_text('common.main_menu', telegram_id), 
              'callback_data': 'menu:main'}]
        ]
        
        self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
    
    def _show_error(self, chat_id: int, message_id: int, 
                   telegram_id: int, error: str):
        """显示错误消息"""
        text = f"❌ {error}"
        buttons = [[{'text': self.get_text('common.main_menu', telegram_id), 
                    'callback_data': 'menu:main'}]]
        self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
    
    def _notify_recipient(self, to_username: str, from_username: str, domain_name: str):
        """通知接收方"""
        try:
            from app.models.user import User
            from app.models.telegram import TelegramUser
            
            to_user = User.query.filter_by(username=to_username).first()
            if not to_user:
                return
            
            tg_user = TelegramUser.query.filter_by(user_id=to_user.id).first()
            if not tg_user or not tg_user.telegram_id:
                return
            
            text = self.get_text('transfer.notify_initiated', None,
                from_user=from_username,
                domain=domain_name
            )
            
            buttons = [
                [{'text': '📋 查看转移', 'callback_data': 'transfer:list:1'}],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ]
            
            self.send_message(tg_user.telegram_id, text, self.make_keyboard(buttons))
        except Exception as e:
            print(f'[TransferHandler] Notify recipient error: {e}')
    
    def _notify_transfer_completed(self, domain_name: str, 
                                   from_username: str, to_username: str):
        """通知转移完成"""
        try:
            from app.models.user import User
            from app.models.telegram import TelegramUser
            
            # 通知接收方
            to_user = User.query.filter_by(username=to_username).first()
            if to_user:
                tg_user = TelegramUser.query.filter_by(user_id=to_user.id).first()
                if tg_user and tg_user.telegram_id:
                    text = self.get_text('transfer.notify_completed', None,
                        domain=domain_name,
                        direction='转入自',
                        user=from_username
                    )
                    buttons = [
                        [{'text': '📋 我的域名', 'callback_data': 'domain:list'}],
                        [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
                    ]
                    self.send_message(tg_user.telegram_id, text, self.make_keyboard(buttons))
        except Exception as e:
            print(f'[TransferHandler] Notify completed error: {e}')
