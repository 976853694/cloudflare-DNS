"""
主菜单处理器

处理 /start 命令和主菜单显示
"""

from .base import BaseHandler


class MenuHandler(BaseHandler):
    """主菜单处理器"""
    
    def handle_start(self, chat_id: int, telegram_id: int, user_info: dict):
        """
        处理 /start 命令
        
        Args:
            chat_id: 聊天 ID
            telegram_id: Telegram 用户 ID
            user_info: Telegram 用户信息
        """
        try:
            # 保存/更新 Telegram 用户信息
            self._save_telegram_user(telegram_id, user_info)
            
            # 获取绑定用户
            user = self.get_user(telegram_id)
            
            if user:
                self._show_main_menu(chat_id, user, user_info, telegram_id)
            else:
                self._show_unbound_menu(chat_id, user_info, telegram_id)
        except Exception as e:
            print(f'[MenuHandler] handle_start error: {e}')
            import traceback
            traceback.print_exc()
            # 发送错误提示
            self.send_message(chat_id, '❌ 处理命令时出错，请稍后重试')
    
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
        action = data.replace('menu:', '')
        
        if action == 'main':
            # 清除会话状态
            self.clear_session_state(chat_id)
            
            # 获取绑定用户
            user = self.get_user(telegram_id)
            
            if user:
                self._show_main_menu(chat_id, user, user_info, telegram_id, message_id)
            else:
                self._show_unbound_menu(chat_id, user_info, telegram_id, message_id)
    
    def _show_main_menu(self, chat_id: int, user, user_info: dict, 
                       telegram_id: int, message_id: int = None):
        """
        显示已绑定用户的主菜单
        
        Args:
            chat_id: 聊天 ID
            user: 绑定的用户对象
            user_info: Telegram 用户信息
            telegram_id: Telegram 用户 ID
            message_id: 消息 ID（用于编辑）
        """
        # 获取统计数据
        domain_count = self._get_user_stats(user.id)
        
        # 获取站点名称
        from app.models import Setting
        site_name = Setting.get('site_name', '六趣DNS')
        
        # 构建消息
        first_name = user_info.get('first_name', '') or user.username
        
        text = f"🎉 {site_name}机器人\n\n"
        text += f"你好，{first_name}！\n\n"
        text += f"✅ 已绑定：{user.username}\n"
        text += f"💰 余额：{self._format_balance(user.balance)}\n\n"
        text += f"📊 我的资源\n"
        text += f"🌐 域名：{domain_count} 个"
        
        keyboard = self._build_main_menu_keyboard(user, domain_count)
        
        if message_id:
            self.edit_message(chat_id, message_id, text, keyboard)
        else:
            self.send_message(chat_id, text, keyboard)
    
    def _show_unbound_menu(self, chat_id: int, user_info: dict, 
                          telegram_id: int, message_id: int = None):
        """
        显示未绑定用户的菜单
        
        Args:
            chat_id: 聊天 ID
            user_info: Telegram 用户信息
            telegram_id: Telegram 用户 ID
            message_id: 消息 ID（用于编辑）
        """
        # 获取站点名称
        from app.models import Setting
        site_name = Setting.get('site_name', '六趣DNS')
        
        first_name = user_info.get('first_name', '') or 'User'
        
        text = f"🎉 {site_name}机器人\n\n"
        text += f"你好，{first_name}！\n\n"
        text += "⚠️ 您尚未绑定账号\n\n"
        text += "📝 绑定方式：\n"
        text += "1. 登录网站「安全设置」页面\n"
        text += "2. 点击「绑定 Telegram」获取绑定码\n"
        text += "3. 发送 /bind [绑定码]"
        
        buttons = [[{'text': '📖 查看帮助', 'callback_data': 'help:main'}]]
        keyboard = self.make_keyboard(buttons)
        
        if message_id:
            self.edit_message(chat_id, message_id, text, keyboard)
        else:
            self.send_message(chat_id, text, keyboard)
    
    def _build_main_menu_keyboard(self, user, domain_count: int):
        """
        构建主菜单键盘
        
        Args:
            user: 用户对象
            domain_count: 域名数量
            
        Returns:
            键盘对象
        """
        buttons = [
            [
                {'text': f'🌐 我的域名 ({domain_count})', 'callback_data': 'domain:list'}
            ],
            [
                {'text': '🛒 购买套餐', 'callback_data': 'buy:plans'},
                {'text': '💳 充值卡密', 'callback_data': 'account:recharge'}
            ],
            [
                {'text': '👤 我的账户', 'callback_data': 'account:info'},
                {'text': '💰 余额明细', 'callback_data': 'account:orders'}
            ],
            [
                {'text': '🎁 积分中心', 'callback_data': 'points:menu'},
                {'text': '🎫 工单中心', 'callback_data': 'ticket:menu'}
            ]
        ]
        
        # 托管商按钮
        if getattr(user, 'is_host', False):
            buttons.append([{'text': '🏢 托管商中心', 'callback_data': 'hc:dashboard'}])
        elif getattr(user, 'can_apply_host', False):
            buttons.append([{'text': '📝 申请成为托管商', 'callback_data': 'account:apply_host'}])
        elif getattr(user, 'host_status', None) == 'pending':
            buttons.append([{'text': '⏳ 托管申请审核中', 'callback_data': 'account:apply_status'}])
        
        # 公告和帮助
        buttons.append([
            {'text': '📢 系统公告', 'callback_data': 'announcement:list'},
            {'text': '📖 使用帮助', 'callback_data': 'help:main'}
        ])
        
        # 设置
        buttons.append([{'text': '⚙️ 设置', 'callback_data': 'settings:main'}])
        
        # 管理员按钮
        if getattr(user, 'is_admin', False):
            buttons.append([{'text': '🔧 管理后台', 'callback_data': 'admin:dashboard'}])
        
        return self.make_keyboard(buttons)
    
    def _save_telegram_user(self, telegram_id: int, user_info: dict):
        """
        保存/更新 Telegram 用户信息
        
        Args:
            telegram_id: Telegram 用户 ID
            user_info: Telegram 用户信息
        """
        try:
            from app import db
            from app.models.telegram import TelegramUser
            
            tg_user = TelegramUser.get_by_telegram_id(telegram_id)
            if not tg_user:
                tg_user = TelegramUser(
                    telegram_id=telegram_id,
                    telegram_username=user_info.get('username', ''),
                    telegram_first_name=user_info.get('first_name', '')
                )
                db.session.add(tg_user)
                db.session.commit()
            else:
                # 更新用户名
                username = user_info.get('username', '')
                first_name = user_info.get('first_name', '')
                need_update = False
                
                if username and tg_user.telegram_username != username:
                    tg_user.telegram_username = username
                    need_update = True
                if first_name and tg_user.telegram_first_name != first_name:
                    tg_user.telegram_first_name = first_name
                    need_update = True
                    
                if need_update:
                    db.session.commit()
        except Exception as e:
            print(f'[MenuHandler] Save TG user error: {e}')
            import traceback
            traceback.print_exc()
            # 回滚事务
            try:
                from app import db
                db.session.rollback()
            except:
                pass
    
    def _get_user_stats(self, user_id: int) -> int:
        """
        获取用户统计数据
        
        Args:
            user_id: 用户 ID
            
        Returns:
            domain_count
        """
        try:
            from app.models.subdomain import Subdomain
            
            domain_count = Subdomain.query.filter_by(user_id=user_id).count()
            
            return domain_count
        except Exception as e:
            print(f'[MenuHandler] Get stats error: {e}')
            return 0
    
    def _format_balance(self, balance) -> str:
        """格式化余额显示"""
        if balance == -1:
            return '无限'
        return f'¥{balance}'
