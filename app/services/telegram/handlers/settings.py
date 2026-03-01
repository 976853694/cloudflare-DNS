"""
设置处理器

处理语言切换、通知设置等功能
"""

from .base import BaseHandler


class SettingsHandler(BaseHandler):
    """设置处理器"""
    
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
        # 检查绑定
        user = self.get_user(telegram_id)
        if not user:
            self.require_bind(chat_id, telegram_id, message_id)
            return
        
        parts = data.split(':')
        
        if data == 'settings:main' or data == 'menu:settings':
            self._show_settings(chat_id, message_id, user)
        elif data == 'settings:language':
            self._show_language_settings(chat_id, message_id, user)
        elif data.startswith('settings:lang:'):
            new_lang = parts[2]
            self._handle_language_change(chat_id, message_id, user, new_lang)
        elif data == 'settings:notifications':
            self._show_notification_settings(chat_id, message_id, user)
        elif data.startswith('settings:notify:'):
            notify_type = parts[2]
            self._handle_notification_toggle(chat_id, message_id, user, notify_type)
    
    def _show_settings(self, chat_id: int, message_id: int, user):
        """
        显示设置菜单
        
        Args:
            chat_id: 聊天 ID
            message_id: 消息 ID
            user: 用户对象
        """
        try:
            # 获取当前语言
            lang = getattr(user, 'tg_language', 'zh') or 'zh'
            lang_text = '中文' if lang == 'zh' else 'English'
            
            text = f"⚙️ 设置\n\n"
            text += f"🌐 当前语言：{lang_text}"
            
            buttons = [
                [{'text': '🌐 语言设置', 'callback_data': 'settings:language'}],
                [{'text': '🔔 通知设置', 'callback_data': 'settings:notifications'}],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ]
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[SettingsHandler] Settings menu error: {e}')
            self.handle_error(chat_id, e, message_id)
    
    def _show_language_settings(self, chat_id: int, message_id: int, user):
        """
        显示语言设置
        
        Args:
            chat_id: 聊天 ID
            message_id: 消息 ID
            user: 用户对象
        """
        lang = getattr(user, 'tg_language', 'zh') or 'zh'
        
        text = "🌐 语言设置\n\n请选择语言："
        
        buttons = [
            [
                {'text': '🇨🇳 中文' + (' ✓' if lang == 'zh' else ''), 'callback_data': 'settings:lang:zh'},
                {'text': '🇺🇸 English' + (' ✓' if lang == 'en' else ''), 'callback_data': 'settings:lang:en'}
            ],
            [{'text': '◀️ 返回', 'callback_data': 'settings:main'}]
        ]
        
        keyboard = self.make_keyboard(buttons)
        self.edit_message(chat_id, message_id, text, keyboard)
    
    def _handle_language_change(self, chat_id: int, message_id: int, user, new_lang: str):
        """
        处理语言切换
        
        Args:
            chat_id: 聊天 ID
            message_id: 消息 ID
            user: 用户对象
            new_lang: 新语言
        """
        if new_lang not in ['zh', 'en']:
            return
        
        try:
            from app import db
            from app.models.user import User
            
            user = User.query.get(user.id)
            user.tg_language = new_lang
            db.session.commit()
            
            # 刷新设置页面
            self._show_settings(chat_id, message_id, user)
            
        except Exception as e:
            print(f'[SettingsHandler] Language change error: {e}')
    
    def _show_notification_settings(self, chat_id: int, message_id: int, user):
        """
        显示通知设置
        
        Args:
            chat_id: 聊天 ID
            message_id: 消息 ID
            user: 用户对象
        """
        try:
            # 获取通知设置
            notify_expiry = getattr(user, 'tg_notify_expiry', True)
            notify_purchase = getattr(user, 'tg_notify_purchase', True)
            notify_recharge = getattr(user, 'tg_notify_recharge', True)
            notify_announcement = getattr(user, 'tg_notify_announcement', True)
            
            if notify_expiry is None:
                notify_expiry = True
            if notify_purchase is None:
                notify_purchase = True
            if notify_recharge is None:
                notify_recharge = True
            if notify_announcement is None:
                notify_announcement = True
            
            text = "🔔 通知设置\n\n点击切换开关："
            
            buttons = [
                [{'text': f"{'✅' if notify_expiry else '❌'} 到期提醒", 'callback_data': 'settings:notify:expiry'}],
                [{'text': f"{'✅' if notify_purchase else '❌'} 购买通知", 'callback_data': 'settings:notify:purchase'}],
                [{'text': f"{'✅' if notify_recharge else '❌'} 充值通知", 'callback_data': 'settings:notify:recharge'}],
                [{'text': f"{'✅' if notify_announcement else '❌'} 公告通知", 'callback_data': 'settings:notify:announcement'}],
            ]
            
            # 托管商额外通知
            if hasattr(user, 'is_host') and user.is_host:
                notify_host_order = getattr(user, 'tg_notify_host_order', True)
                if notify_host_order is None:
                    notify_host_order = True
                buttons.append([{'text': f"{'✅' if notify_host_order else '❌'} 托管商订单通知", 'callback_data': 'settings:notify:host_order'}])
            
            buttons.append([{'text': '◀️ 返回', 'callback_data': 'settings:main'}])
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[SettingsHandler] Notification settings error: {e}')
            self.handle_error(chat_id, e, message_id)
    
    def _handle_notification_toggle(self, chat_id: int, message_id: int, user, notify_type: str):
        """
        处理通知开关切换
        
        Args:
            chat_id: 聊天 ID
            message_id: 消息 ID
            user: 用户对象
            notify_type: 通知类型
        """
        # 映射字段名
        field_map = {
            'expiry': 'tg_notify_expiry',
            'purchase': 'tg_notify_purchase',
            'recharge': 'tg_notify_recharge',
            'announcement': 'tg_notify_announcement',
            'host_order': 'tg_notify_host_order'
        }
        
        field_name = field_map.get(notify_type)
        if not field_name:
            return
        
        try:
            from app import db
            from app.models.user import User
            
            user = User.query.get(user.id)
            
            # 切换状态
            current = getattr(user, field_name, True)
            if current is None:
                current = True
            new_value = not current
            setattr(user, field_name, new_value)
            
            db.session.commit()
            
            # 刷新通知设置页面
            self._show_notification_settings(chat_id, message_id, user)
            
        except Exception as e:
            print(f'[SettingsHandler] Notification toggle error: {e}')
