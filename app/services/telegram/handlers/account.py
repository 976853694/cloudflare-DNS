"""
账户处理器

处理账户信息、充值、订单记录等
"""

from .base import BaseHandler


class AccountHandler(BaseHandler):
    """账户处理器"""
    
    PAGE_SIZE = 5
    
    def handle_callback(self, chat_id: int, message_id: int, telegram_id: int,
                       user_info: dict, data: str):
        """处理回调"""
        if not self.require_bind(chat_id, telegram_id, message_id):
            return
        
        user = self.get_user(telegram_id)
        parts = data.split(':')
        action = parts[1] if len(parts) > 1 else ''
        
        if action == 'info':
            self._show_account_info(chat_id, message_id, user, telegram_id)
        elif action == 'recharge':
            self._show_recharge(chat_id, message_id, telegram_id)
        elif action == 'orders':
            page = int(parts[2]) if len(parts) > 2 else 1
            self._show_orders(chat_id, message_id, user, telegram_id, page)
        elif action == 'api':
            self._show_api_info(chat_id, message_id, user, telegram_id)
        elif action == 'api_show':
            self._show_api_secret(chat_id, message_id, user, telegram_id)
        elif action == 'api_reset':
            self._show_api_reset_confirm(chat_id, message_id, telegram_id)
        elif action == 'api_reset_confirm':
            self._do_api_reset(chat_id, message_id, user, telegram_id)
    
    def handle_text_input(self, chat_id: int, telegram_id: int, text: str, session: dict) -> bool:
        """处理文本输入"""
        state = session.get('state', '')
        
        if state == 'account_recharge':
            return self._handle_recharge_input(chat_id, telegram_id, text, session)
        
        return False
    
    def _show_account_info(self, chat_id: int, message_id: int, user, telegram_id: int):
        """显示账户信息"""
        try:
            from app.models.subdomain import Subdomain
            
            domain_count = Subdomain.query.filter_by(user_id=user.id).count()
            
            text = f"👤 我的账户\n\n"
            text += f"用户名：{user.username}\n"
            text += f"邮箱：{user.email}\n"
            text += f"余额：¥{user.balance}\n\n"
            text += f"📊 资产统计\n"
            text += f"域名：{domain_count} 个"
            
            buttons = [
                [
                    {'text': '💳 充值', 'callback_data': 'account:recharge'},
                    {'text': '📋 订单记录', 'callback_data': 'account:orders'}
                ],
                [{'text': '🔑 API 管理', 'callback_data': 'account:api'}],
                [{'text': '🏠 返回主菜单', 'callback_data': 'menu:main'}]
            ]
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[AccountHandler] Info error: {e}')
    
    def _show_recharge(self, chat_id: int, message_id: int, telegram_id: int):
        """显示充值页面"""
        self.set_session_state(chat_id, 'account_recharge', {'message_id': message_id})
        
        text = "💳 卡密充值\n\n请输入充值卡密："
        
        buttons = [[{'text': '❌ 取消', 'callback_data': 'account:info'}]]
        keyboard = self.make_keyboard(buttons)
        self.edit_message(chat_id, message_id, text, keyboard)
    
    def _handle_recharge_input(self, chat_id: int, telegram_id: int, text: str, session: dict) -> bool:
        """处理充值卡密输入"""
        try:
            from app import db
            from app.models.redeem_code import RedeemCode
            from app.utils.timezone import now as beijing_now
            
            user = self.get_user(telegram_id)
            code = text.strip().upper()
            
            # 查找卡密
            card = RedeemCode.query.filter_by(code=code, status=RedeemCode.STATUS_UNUSED).first()
            
            if not card:
                msg = "❌ 卡密无效或已使用\n\n请重新输入："
                buttons = [[{'text': '❌ 取消', 'callback_data': 'account:info'}]]
                keyboard = self.make_keyboard(buttons)
                self.send_message(chat_id, msg, keyboard)
                return True
            
            # 检查是否过期
            if not card.is_valid:
                msg = "❌ 卡密已过期\n\n请重新输入："
                buttons = [[{'text': '❌ 取消', 'callback_data': 'account:info'}]]
                keyboard = self.make_keyboard(buttons)
                self.send_message(chat_id, msg, keyboard)
                return True
            
            # 充值
            amount = card.amount
            user.balance += amount
            card.status = RedeemCode.STATUS_USED
            card.used_by = user.id
            card.used_at = beijing_now()
            
            db.session.commit()
            
            # 清除会话
            self.clear_session_state(chat_id)
            
            msg = f"✅ 充值成功！\n\n"
            msg += f"充值金额：¥{amount}\n"
            msg += f"当前余额：¥{user.balance}"
            
            buttons = [
                [{'text': '👤 我的账户', 'callback_data': 'account:info'}],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ]
            keyboard = self.make_keyboard(buttons)
            self.send_message(chat_id, msg, keyboard)
            
            return True
            
        except Exception as e:
            print(f'[AccountHandler] Recharge error: {e}')
            import traceback
            traceback.print_exc()
            self.send_message(chat_id, f"❌ 充值失败：{str(e)}")
            return True
    
    def _show_orders(self, chat_id: int, message_id: int, user, telegram_id: int, page: int = 1):
        """显示订单记录"""
        try:
            from app.models.purchase_record import PurchaseRecord
            
            query = PurchaseRecord.query.filter_by(user_id=user.id).order_by(PurchaseRecord.created_at.desc())
            
            total = query.count()
            total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            page = max(1, min(page, total_pages))
            
            orders = query.offset((page - 1) * self.PAGE_SIZE).limit(self.PAGE_SIZE).all()
            
            text = f"📋 订单记录\n\n"
            
            if total == 0:
                text += "暂无订单记录"
            else:
                text += f"共 {total} 条记录（第 {page}/{total_pages} 页）\n\n"
                for o in orders:
                    text += f"📦 {o.plan_name}\n"
                    text += f"   域名：{o.subdomain_name}\n"
                    text += f"   金额：¥{o.price}\n"
                    text += f"   时间：{o.created_at.strftime('%Y-%m-%d')}\n\n"
            
            buttons = []
            
            # 分页
            if total_pages > 1:
                nav = []
                if page > 1:
                    nav.append({'text': '◀️', 'callback_data': f'account:orders:{page-1}'})
                if page < total_pages:
                    nav.append({'text': '▶️', 'callback_data': f'account:orders:{page+1}'})
                if nav:
                    buttons.append(nav)
            
            buttons.append([{'text': '◀️ 返回账户', 'callback_data': 'account:info'}])
            buttons.append([{'text': '🏠 主菜单', 'callback_data': 'menu:main'}])
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[AccountHandler] Orders error: {e}')
    
    def _show_api_info(self, chat_id: int, message_id: int, user, telegram_id: int):
        """显示 API 信息"""
        try:
            text = "🔑 API 管理\n\n"
            
            if user.api_key:
                text += f"API Key：{user.api_key}\n"
                text += f"API Secret：{'*' * 20}\n"
                text += f"状态：{'✅ 启用' if user.api_enabled == 1 else '❌ 禁用'}"
                
                buttons = [
                    [{'text': '👁️ 显示 Secret', 'callback_data': 'account:api_show'}],
                    [{'text': '🔄 重置 Secret', 'callback_data': 'account:api_reset'}],
                    [{'text': '◀️ 返回账户', 'callback_data': 'account:info'}]
                ]
            else:
                text += "暂未创建 API 密钥\n\n请在网站「API 管理」页面创建"
                buttons = [[{'text': '◀️ 返回账户', 'callback_data': 'account:info'}]]
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[AccountHandler] API info error: {e}')
    
    def _show_api_secret(self, chat_id: int, message_id: int, user, telegram_id: int):
        """显示 API Secret"""
        try:
            if not user.api_key:
                return
            
            text = "🔑 API 密钥\n\n"
            text += f"API Key：{user.api_key}\n"
            text += f"API Secret：{user.api_secret}\n\n"
            text += "⚠️ 请妥善保管，不要泄露给他人"
            
            buttons = [
                [{'text': '🔄 重置 Secret', 'callback_data': 'account:api_reset'}],
                [{'text': '◀️ 返回', 'callback_data': 'account:api'}]
            ]
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[AccountHandler] Show secret error: {e}')
    
    def _show_api_reset_confirm(self, chat_id: int, message_id: int, telegram_id: int):
        """显示重置确认"""
        text = "⚠️ 确定要重置 API Secret 吗？\n\n重置后旧的 Secret 将失效"
        
        buttons = [
            [{'text': '✅ 确认重置', 'callback_data': 'account:api_reset_confirm'}],
            [{'text': '❌ 取消', 'callback_data': 'account:api'}]
        ]
        
        keyboard = self.make_keyboard(buttons)
        self.edit_message(chat_id, message_id, text, keyboard)
    
    def _do_api_reset(self, chat_id: int, message_id: int, user, telegram_id: int):
        """执行重置"""
        try:
            from app import db
            import secrets
            
            if not user.api_key:
                return
            
            # 生成新的 Secret
            user.api_secret = secrets.token_hex(32)
            db.session.commit()
            
            text = "✅ API Secret 已重置\n\n"
            text += f"新 Secret：{user.api_secret}\n\n"
            text += "⚠️ 请妥善保管"
            
            buttons = [[{'text': '◀️ 返回', 'callback_data': 'account:api'}]]
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[AccountHandler] Reset error: {e}')
