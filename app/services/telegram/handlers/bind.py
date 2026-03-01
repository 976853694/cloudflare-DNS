"""
绑定/解绑处理器

处理用户账号绑定和解绑功能
"""

from .base import BaseHandler


class BindHandler(BaseHandler):
    """绑定/解绑处理器"""
    
    def handle_bind_command(self, chat_id: int, telegram_id: int, user_info: dict, 
                           args: list, chat_type: str = 'private'):
        """
        处理 /bind 命令
        
        Args:
            chat_id: 聊天 ID
            telegram_id: Telegram 用户 ID
            user_info: Telegram 用户信息
            args: 命令参数
            chat_type: 聊天类型
        """
        # 检查是否为私聊
        if chat_type != 'private':
            text = '⚠️ 为保护您的账号安全，/bind 命令只能在私聊中使用\n\n请私聊机器人发送绑定命令'
            self.send_message(chat_id, text)
            return
        
        # 检查是否已绑定
        existing_user = self.get_user(telegram_id)
        if existing_user:
            text = f'❌ 您已绑定账号：{existing_user.username}\n\n如需更换，请先解绑'
            buttons = [
                [{'text': '🔓 解除绑定', 'callback_data': 'bind:unbind'}],
                [{'text': '🏠 返回主菜单', 'callback_data': 'menu:main'}]
            ]
            keyboard = self.make_keyboard(buttons)
            self.send_message(chat_id, text, keyboard)
            return
        
        if not args:
            # 没有提供绑定码，提示输入
            text = '❌ 请输入绑定码\n\n格式：/bind [绑定码]\n\n绑定码可在网站「安全设置」页面获取'
            buttons = [[{'text': '📖 查看帮助', 'callback_data': 'help:bind'}]]
            keyboard = self.make_keyboard(buttons)
            self.send_message(chat_id, text, keyboard)
            return
        
        code = args[0].upper()
        
        # 验证绑定码
        success, result = self._verify_and_bind(telegram_id, user_info, code)
        
        if success:
            text = f"✅ 绑定成功！\n\n已绑定账号：{result.username}"
            buttons = [[{'text': '🏠 进入主菜单', 'callback_data': 'menu:main'}]]
        else:
            text = result  # 错误消息
            buttons = [[{'text': '📖 查看帮助', 'callback_data': 'help:bind'}]]
        
        keyboard = self.make_keyboard(buttons)
        self.send_message(chat_id, text, keyboard)
    
    def handle_callback(self, chat_id: int, message_id: int, telegram_id: int,
                       user_info: dict, data: str):
        """
        处理回调
        
        Args:
            chat_id: 聊天 ID
            message_id: 消息 ID
            telegram_id: Telegram 用户 ID
            user_info: Telegram 用户信息
            data: 回调数据
        """
        action = data.replace('bind:', '')
        
        if action == 'unbind':
            self._handle_unbind(chat_id, message_id, telegram_id)
        elif action == 'unbind:confirm':
            self._handle_unbind_confirm(chat_id, message_id, telegram_id)
    
    def _handle_unbind(self, chat_id: int, message_id: int, telegram_id: int):
        """处理解绑按钮"""
        # 获取绑定用户
        user = self.get_user(telegram_id)
        if not user:
            text = '❌ 您尚未绑定账号'
            buttons = [[{'text': '📖 查看帮助', 'callback_data': 'help:bind'}]]
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            return
        
        # 显示确认对话框
        text = f'⚠️ 确定要解除绑定吗？\n\n当前绑定账号：{user.username}'
        buttons = [
            [{'text': '✅ 确认解绑', 'callback_data': 'bind:unbind:confirm'}],
            [{'text': '❌ 取消', 'callback_data': 'menu:main'}]
        ]
        keyboard = self.make_keyboard(buttons)
        self.edit_message(chat_id, message_id, text, keyboard)
    
    def _handle_unbind_confirm(self, chat_id: int, message_id: int, telegram_id: int):
        """处理解绑确认"""
        # 执行解绑
        success = self._do_unbind(telegram_id, chat_id)
        
        if success:
            text = '✅ 解绑成功！\n\n如需重新绑定，请发送 /bind [绑定码]'
            buttons = [[{'text': '📖 查看帮助', 'callback_data': 'help:bind'}]]
        else:
            text = '❌ 解绑失败，请稍后重试'
            buttons = [[{'text': '🏠 返回主菜单', 'callback_data': 'menu:main'}]]
        
        keyboard = self.make_keyboard(buttons)
        self.edit_message(chat_id, message_id, text, keyboard)
    
    def _verify_and_bind(self, telegram_id: int, user_info: dict, code: str):
        """
        验证绑定码并执行绑定
        
        Args:
            telegram_id: Telegram 用户 ID
            user_info: Telegram 用户信息
            code: 绑定码
            
        Returns:
            (success, result): 成功时 result 为用户对象，失败时为错误消息
        """
        try:
            from app import db
            from app.models.telegram import TelegramUser, TelegramBindCode
            from app.models.user import User
            
            # 验证绑定码
            bind_code = TelegramBindCode.verify_code(code)
            if not bind_code:
                return False, '❌ 绑定码无效或已过期\n\n请在网站「安全设置」页面重新获取绑定码'
            
            # 获取用户
            user = User.query.get(bind_code.user_id)
            if not user:
                return False, '❌ 用户不存在'
            
            if not user.is_active:
                return False, '❌ 账号已被禁用'
            
            # 检查该用户是否已绑定其他 Telegram
            existing_tg = TelegramUser.query.filter_by(user_id=user.id).first()
            if existing_tg and existing_tg.telegram_id != telegram_id:
                return False, '❌ 该账号已绑定其他 Telegram'
            
            # 创建或更新 TelegramUser
            tg_user = TelegramUser.get_by_telegram_id(telegram_id)
            if tg_user:
                tg_user.user_id = user.id
                tg_user.telegram_username = user_info.get('username', '')
                tg_user.telegram_first_name = user_info.get('first_name', '')
            else:
                tg_user = TelegramUser(
                    telegram_id=telegram_id,
                    user_id=user.id,
                    telegram_username=user_info.get('username', ''),
                    telegram_first_name=user_info.get('first_name', '')
                )
                db.session.add(tg_user)
            
            # 标记绑定码已使用
            bind_code.used = True
            
            db.session.commit()
            
            return True, user
            
        except Exception as e:
            print(f'[BindHandler] Bind error: {e}')
            return False, '❌ 绑定失败，请稍后重试'
    
    def _do_unbind(self, telegram_id: int, chat_id: int) -> bool:
        """
        执行解绑操作
        
        Args:
            telegram_id: Telegram 用户 ID
            chat_id: 聊天 ID
            
        Returns:
            是否成功
        """
        try:
            from app import db
            from app.models.telegram import TelegramUser
            
            tg_user = TelegramUser.get_by_telegram_id(telegram_id)
            if tg_user:
                tg_user.user_id = None
                db.session.commit()
            
            # 清除会话状态
            self.clear_session_state(chat_id)
            
            return True
            
        except Exception as e:
            print(f'[BindHandler] Unbind error: {e}')
            return False
