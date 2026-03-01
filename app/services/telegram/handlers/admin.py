"""
管理后台处理器

处理管理员仪表盘、用户管理、申请审核、卡密管理、公告管理、统计报表等功能
"""

from datetime import datetime, timedelta
from decimal import Decimal
from .base import BaseHandler


class AdminHandler(BaseHandler):
    """管理后台处理器"""
    
    PAGE_SIZE = 5
    
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
        # 检查绑定和管理员权限
        user = self.get_user(telegram_id)
        if not user:
            self.require_bind(chat_id, telegram_id, message_id)
            return
        
        if not self.check_permission(user, 'admin'):
            self.require_admin(chat_id, telegram_id, message_id)
            return
        
        parts = data.split(':')
        
        if data in ['admin:dashboard', 'menu:admin']:
            self._show_admin_dashboard(chat_id, message_id, user)
        elif data == 'admin:users' or data.startswith('admin:users:'):
            if len(parts) >= 3 and parts[2] == 'search':
                self._start_user_search(chat_id, message_id)
            else:
                page = int(parts[2]) if len(parts) >= 3 else 1
                self._show_users(chat_id, message_id, user, page)

        elif data.startswith('admin:user:'):
            try:
                user_id = int(parts[2])
                if len(parts) >= 4:
                    action = parts[3]
                    self._handle_user_action(chat_id, message_id, user, user_id, action)
                else:
                    self._show_user_detail(chat_id, message_id, user, user_id)
            except:
                self.handle_error(chat_id, Exception('参数错误'), message_id)
        elif data == 'admin:applications' or data.startswith('admin:apps:'):
            page = int(parts[2]) if len(parts) >= 3 else 1
            self._show_applications(chat_id, message_id, user, page)
        elif data.startswith('admin:app:'):
            try:
                app_id = int(parts[2])
                if len(parts) >= 4:
                    action = parts[3]
                    self._handle_application_action(chat_id, message_id, user, app_id, action)
                else:
                    self._show_application_detail(chat_id, message_id, user, app_id)
            except:
                self.handle_error(chat_id, Exception('参数错误'), message_id)
        elif data == 'admin:cards':
            self._show_cards_menu(chat_id, message_id, user)
        elif data.startswith('admin:cards:'):
            action = parts[2]
            self._handle_cards_action(chat_id, message_id, user, action)
        elif data == 'admin:announcements' or data.startswith('admin:announcements:'):
            page = int(parts[2]) if len(parts) >= 3 else 1
            self._show_admin_announcements(chat_id, message_id, user, page)
        elif data.startswith('admin:announcement:'):
            if parts[2] == 'new':
                self._start_announcement_create(chat_id, message_id)
            elif parts[2] == 'publish':
                is_pinned = len(parts) >= 4 and parts[3] == 'pinned'
                self._publish_announcement(chat_id, message_id, user, is_pinned)
            else:
                try:
                    ann_id = int(parts[2])
                    if len(parts) >= 4:
                        action = parts[3]
                        self._handle_announcement_action(chat_id, message_id, user, ann_id, action)
                    else:
                        self._show_announcement_detail(chat_id, message_id, user, ann_id)
                except:
                    self.handle_error(chat_id, Exception('参数错误'), message_id)
        elif data == 'admin:stats':
            self._show_stats(chat_id, message_id, user)
        elif data == 'admin:broadcast':
            self._start_broadcast(chat_id, message_id)
        elif data == 'admin:broadcast:confirm':
            self._confirm_broadcast(chat_id, message_id, user)
        elif data == 'admin:broadcast:cancel':
            self.clear_session_state(chat_id)
            self._show_admin_dashboard(chat_id, message_id, user)

    def handle_text_input(self, chat_id: int, telegram_id: int, text: str, session: dict) -> bool:
        """
        处理文本输入
        
        Args:
            chat_id: 聊天 ID
            telegram_id: Telegram 用户 ID
            text: 输入文本
            session: 会话数据
            
        Returns:
            是否处理了该消息
        """
        user = self.get_user(telegram_id)
        if not user or not self.check_permission(user, 'admin'):
            return False
        
        state = session.get('state')
        
        if state == 'admin_search':
            return self._handle_user_search_input(chat_id, user, text)
        elif state == 'admin_balance':
            return self._handle_balance_input(chat_id, user, text, session)
        elif state == 'admin_broadcast':
            return self._handle_broadcast_input(chat_id, user, text, session)
        elif state == 'admin_announcement':
            return self._handle_announcement_input(chat_id, user, text, session)
        elif state == 'admin_approve_custom':
            return self._handle_approve_custom_input(chat_id, user, text, session)
        elif state == 'admin_reject':
            return self._handle_reject_input(chat_id, user, text, session)
        
        return False
    
    def _show_admin_dashboard(self, chat_id: int, message_id: int, user):
        """显示管理员仪表盘"""
        try:
            from app.models.user import User
            from app.models.subdomain import Subdomain
            from app.models.purchase_record import PurchaseRecord
            from app.models.host_application import HostApplication
            from app import db
            
            # 统计数据
            user_count = User.query.count()
            domain_count = Subdomain.query.count()
            
            # 今日订单
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_orders = PurchaseRecord.query.filter(
                PurchaseRecord.created_at >= today_start
            ).count()
            
            today_income = PurchaseRecord.query.filter(
                PurchaseRecord.created_at >= today_start
            ).with_entities(db.func.sum(PurchaseRecord.price)).scalar() or Decimal('0')
            
            # 待审核申请
            pending_apps = HostApplication.query.filter_by(status=0).count()
            
            text = f"⚙️ 管理后台\n\n"
            text += f"📊 系统统计\n"
            text += f"用户总数：{user_count}\n"
            text += f"域名总数：{domain_count}\n"
            text += f"今日订单：{today_orders} 笔\n"
            text += f"今日收入：¥{today_income:.2f}"
            
            if pending_apps > 0:
                text += f"\n\n⚠️ 待审核申请：{pending_apps} 个"
            
            buttons = [
                [
                    {'text': '👥 用户管理', 'callback_data': 'admin:users'},
                    {'text': '📝 申请审核', 'callback_data': 'admin:applications'}
                ],
                [
                    {'text': '💳 卡密管理', 'callback_data': 'admin:cards'},
                    {'text': '📢 公告管理', 'callback_data': 'admin:announcements'}
                ],
                [
                    {'text': '📊 统计报表', 'callback_data': 'admin:stats'},
                    {'text': '📣 群发通知', 'callback_data': 'admin:broadcast'}
                ],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ]
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[AdminHandler] Dashboard error: {e}')
            self.handle_error(chat_id, e, message_id)

    def _show_users(self, chat_id: int, message_id: int, user, page: int = 1):
        """显示用户列表"""
        try:
            from app.models.user import User
            
            query = User.query.order_by(User.created_at.desc())
            
            total = query.count()
            total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            page = max(1, min(page, total_pages))
            
            users = query.offset((page - 1) * self.PAGE_SIZE).limit(self.PAGE_SIZE).all()
            
            text = f"👥 用户管理\n\n共 {total} 个用户\n\n"
            
            for u in users:
                status = '🔒' if u.status == 0 else ''
                host = '🏢' if getattr(u, 'is_host', False) else ''
                admin = '👑' if getattr(u, 'is_admin', False) else ''
                text += f"{status}{host}{admin} {u.username}\n"
            
            buttons = []
            
            # 搜索按钮
            buttons.append([{'text': '🔍 搜索用户', 'callback_data': 'admin:users:search'}])
            
            # 用户按钮
            for u in users:
                buttons.append([{'text': f'{u.username}', 'callback_data': f'admin:user:{u.id}'}])
            
            # 分页
            if total_pages > 1:
                nav_buttons = []
                if page > 1:
                    nav_buttons.append({'text': '◀️', 'callback_data': f'admin:users:{page - 1}'})
                nav_buttons.append({'text': f'{page}/{total_pages}', 'callback_data': 'noop'})
                if page < total_pages:
                    nav_buttons.append({'text': '▶️', 'callback_data': f'admin:users:{page + 1}'})
                buttons.append(nav_buttons)
            
            buttons.append([
                {'text': '◀️ 返回', 'callback_data': 'admin:dashboard'},
                {'text': '🏠 主菜单', 'callback_data': 'menu:main'}
            ])
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[AdminHandler] Users error: {e}')
            self.handle_error(chat_id, e, message_id)
    
    def _start_user_search(self, chat_id: int, message_id: int):
        """开始用户搜索"""
        self.set_session_state(chat_id, 'admin_search', {})
        
        text = "🔍 搜索用户\n\n请输入用户名或邮箱："
        
        keyboard = self.make_keyboard([
            [{'text': '❌ 取消', 'callback_data': 'admin:users'}]
        ])
        
        self.edit_message(chat_id, message_id, text, keyboard)
    
    def _handle_user_search_input(self, chat_id: int, user, keyword: str) -> bool:
        """处理用户搜索输入"""
        self.clear_session_state(chat_id)
        
        try:
            from app.models.user import User
            
            users = User.query.filter(
                (User.username.like(f'%{keyword}%')) |
                (User.email.like(f'%{keyword}%'))
            ).limit(10).all()
            
            if not users:
                text = f"🔍 搜索结果\n\n未找到匹配 \"{keyword}\" 的用户"
                keyboard = self.make_keyboard([
                    [{'text': '🔍 重新搜索', 'callback_data': 'admin:users:search'}],
                    [{'text': '◀️ 返回', 'callback_data': 'admin:users'}]
                ])
            else:
                text = f"🔍 搜索结果\n\n找到 {len(users)} 个用户："
                
                buttons = []
                for u in users:
                    buttons.append([{'text': f'{u.username} ({u.email or "无邮箱"})',
                                   'callback_data': f'admin:user:{u.id}'}])
                
                buttons.append([{'text': '🔍 重新搜索', 'callback_data': 'admin:users:search'}])
                buttons.append([{'text': '◀️ 返回', 'callback_data': 'admin:users'}])
                keyboard = self.make_keyboard(buttons)
            
            self.send_message(chat_id, text, keyboard)
            
        except Exception as e:
            print(f'[AdminHandler] User search error: {e}')
            self.send_message(chat_id, f"❌ 搜索失败：{str(e)}")
        
        return True

    def _show_user_detail(self, chat_id: int, message_id: int, admin_user, target_user_id: int):
        """显示用户详情"""
        try:
            from app.models.user import User
            from app.models.subdomain import Subdomain
            
            target = User.query.get(target_user_id)
            if not target:
                text = "❌ 用户不存在"
                keyboard = self.make_keyboard([[{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]])
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            domain_count = Subdomain.query.filter_by(user_id=target.id).count()
            
            status_text = '正常' if target.status == 1 else '已禁用'
            is_host = '是' if getattr(target, 'is_host', False) else '否'
            is_admin = '是' if getattr(target, 'is_admin', False) else '否'
            
            text = f"👤 用户详情\n\n"
            text += f"ID：{target.id}\n"
            text += f"用户名：{target.username}\n"
            text += f"邮箱：{target.email or '未设置'}\n"
            text += f"余额：¥{target.balance:.2f}\n"
            text += f"域名数：{domain_count}\n"
            text += f"状态：{status_text}\n"
            text += f"托管商：{is_host}\n"
            text += f"管理员：{is_admin}\n"
            text += f"注册时间：{target.created_at.strftime('%Y-%m-%d') if target.created_at else '未知'}"
            
            buttons = [
                [
                    {'text': '💰 调整余额', 'callback_data': f'admin:user:{target.id}:balance'},
                    {'text': '📋 查看域名', 'callback_data': f'admin:user:{target.id}:domains'}
                ],
                [
                    {'text': '🔓 启用' if target.status == 0 else '🔒 禁用',
                     'callback_data': f'admin:user:{target.id}:toggle'},
                    {'text': '🗑️ 删除', 'callback_data': f'admin:user:{target.id}:delete'}
                ],
                [
                    {'text': '◀️ 返回', 'callback_data': 'admin:users'},
                    {'text': '🏠 主菜单', 'callback_data': 'menu:main'}
                ]
            ]
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[AdminHandler] User detail error: {e}')
            self.handle_error(chat_id, e, message_id)
    
    def _handle_user_action(self, chat_id: int, message_id: int, admin_user, target_user_id: int, action: str):
        """处理用户操作"""
        try:
            from app import db
            from app.models.user import User
            
            target = User.query.get(target_user_id)
            if not target:
                self.handle_error(chat_id, Exception('用户不存在'), message_id)
                return
            
            if action == 'toggle':
                target.status = 0 if target.status == 1 else 1
                db.session.commit()
                self._show_user_detail(chat_id, message_id, admin_user, target_user_id)
            elif action == 'balance':
                self.set_session_state(chat_id, 'admin_balance', {
                    'user_id': target_user_id,
                    'username': target.username,
                    'current_balance': float(target.balance)
                })
                
                text = f"💰 调整余额\n\n"
                text += f"用户：{target.username}\n"
                text += f"当前余额：¥{target.balance:.2f}\n\n"
                text += "请输入调整金额：\n"
                text += "• 正数增加余额，如：100\n"
                text += "• 负数减少余额，如：-50"
                
                keyboard = self.make_keyboard([
                    [{'text': '❌ 取消', 'callback_data': f'admin:user:{target_user_id}'}]
                ])
                
                self.edit_message(chat_id, message_id, text, keyboard)
            elif action == 'delete':
                # 删除确认
                text = f"⚠️ 确认删除用户？\n\n用户：{target.username}\n\n此操作不可恢复！"
                keyboard = self.make_keyboard([
                    [
                        {'text': '✅ 确认删除', 'callback_data': f'admin:user:{target_user_id}:confirm_delete'},
                        {'text': '❌ 取消', 'callback_data': f'admin:user:{target_user_id}'}
                    ]
                ])
                self.edit_message(chat_id, message_id, text, keyboard)
            elif action == 'confirm_delete':
                db.session.delete(target)
                db.session.commit()
                
                text = f"✅ 用户 {target.username} 已删除"
                keyboard = self.make_keyboard([
                    [{'text': '👥 返回用户列表', 'callback_data': 'admin:users'}],
                    [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
                ])
                self.edit_message(chat_id, message_id, text, keyboard)
                
        except Exception as e:
            print(f'[AdminHandler] User action error: {e}')
            self.handle_error(chat_id, e, message_id)

    def _handle_balance_input(self, chat_id: int, admin_user, amount_str: str, session: dict) -> bool:
        """处理余额调整输入"""
        try:
            amount = Decimal(amount_str.strip())
        except:
            self.send_message(chat_id, "❌ 无效的金额，请输入数字")
            return True
        
        data = session.get('data', {})
        target_user_id = data.get('user_id')
        
        if not target_user_id:
            self.clear_session_state(chat_id)
            return True
        
        try:
            from app import db
            from app.models.user import User
            
            target = User.query.get(target_user_id)
            if not target:
                self.send_message(chat_id, "❌ 用户不存在")
                self.clear_session_state(chat_id)
                return True
            
            old_balance = target.balance
            target.balance += amount
            
            # 防止余额为负
            if target.balance < 0:
                target.balance = Decimal('0')
            
            db.session.commit()
            
            self.clear_session_state(chat_id)
            
            text = f"✅ 余额调整成功\n\n"
            text += f"用户：{target.username}\n"
            text += f"原余额：¥{old_balance:.2f}\n"
            text += f"调整：{'+' if amount >= 0 else ''}{amount:.2f}\n"
            text += f"新余额：¥{target.balance:.2f}"
            
            keyboard = self.make_keyboard([
                [{'text': '👤 返回用户', 'callback_data': f'admin:user:{target_user_id}'}],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ])
            
            self.send_message(chat_id, text, keyboard)
            
        except Exception as e:
            print(f'[AdminHandler] Balance adjust error: {e}')
            self.send_message(chat_id, f"❌ 调整失败：{str(e)}")
            self.clear_session_state(chat_id)
        
        return True
    
    def _show_applications(self, chat_id: int, message_id: int, user, page: int = 1):
        """显示申请列表"""
        try:
            from app.models.host_application import HostApplication
            from app.models.user import User
            
            query = HostApplication.query.filter_by(status=0)
            query = query.order_by(HostApplication.created_at.desc())
            
            total = query.count()
            total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            page = max(1, min(page, total_pages))
            
            apps = query.offset((page - 1) * self.PAGE_SIZE).limit(self.PAGE_SIZE).all()
            
            if total == 0:
                text = "📝 托管商申请\n\n暂无待审核申请"
            else:
                text = f"📝 托管商申请\n\n待审核：{total} 个"
            
            buttons = []
            
            for app in apps:
                applicant = User.query.get(app.user_id)
                username = applicant.username if applicant else '未知'
                date = app.created_at.strftime('%m-%d') if app.created_at else ''
                buttons.append([{'text': f'⏳ {username} ({date})',
                               'callback_data': f'admin:app:{app.id}'}])
            
            # 分页
            if total_pages > 1:
                nav_buttons = []
                if page > 1:
                    nav_buttons.append({'text': '◀️', 'callback_data': f'admin:apps:{page - 1}'})
                nav_buttons.append({'text': f'{page}/{total_pages}', 'callback_data': 'noop'})
                if page < total_pages:
                    nav_buttons.append({'text': '▶️', 'callback_data': f'admin:apps:{page + 1}'})
                buttons.append(nav_buttons)
            
            buttons.append([
                {'text': '◀️ 返回', 'callback_data': 'admin:dashboard'},
                {'text': '🏠 主菜单', 'callback_data': 'menu:main'}
            ])
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[AdminHandler] Applications error: {e}')
            self.handle_error(chat_id, e, message_id)

    def _show_application_detail(self, chat_id: int, message_id: int, admin_user, app_id: int):
        """显示申请详情"""
        try:
            from app.models.host_application import HostApplication
            from app.models.user import User
            
            app = HostApplication.query.get(app_id)
            if not app:
                text = "❌ 申请不存在"
                keyboard = self.make_keyboard([[{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]])
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            applicant = User.query.get(app.user_id)
            username = applicant.username if applicant else '未知'
            email = applicant.email if applicant else '未知'
            
            status_map = {0: '待审核', 1: '已批准', 2: '已拒绝'}
            status_text = status_map.get(app.status, '未知')
            
            text = f"📝 申请详情\n\n"
            text += f"申请人：{username}\n"
            text += f"邮箱：{email}\n"
            text += f"状态：{status_text}\n"
            text += f"申请时间：{app.created_at.strftime('%Y-%m-%d %H:%M') if app.created_at else '未知'}"
            if hasattr(app, 'reason') and app.reason:
                text += f"\n申请理由：{app.reason}"
            
            buttons = []
            
            if app.status == 0:  # 待审核
                buttons.append([
                    {'text': '✅ 批准', 'callback_data': f'admin:app:{app_id}:approve'},
                    {'text': '❌ 拒绝', 'callback_data': f'admin:app:{app_id}:reject'}
                ])
                buttons.append([
                    {'text': '💰 自定义佣金批准', 'callback_data': f'admin:app:{app_id}:approve_custom'}
                ])
            
            buttons.append([
                {'text': '◀️ 返回', 'callback_data': 'admin:applications'},
                {'text': '🏠 主菜单', 'callback_data': 'menu:main'}
            ])
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[AdminHandler] Application detail error: {e}')
            self.handle_error(chat_id, e, message_id)
    
    def _handle_application_action(self, chat_id: int, message_id: int, admin_user, app_id: int, action: str):
        """处理申请操作"""
        try:
            from app import db
            from app.models.host_application import HostApplication
            from app.models.user import User
            
            app = HostApplication.query.get(app_id)
            if not app:
                self.handle_error(chat_id, Exception('申请不存在'), message_id)
                return
            
            if app.status != 0:
                text = "❌ 申请已处理"
                keyboard = self.make_keyboard([[{'text': '◀️ 返回', 'callback_data': 'admin:applications'}]])
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            if action == 'approve':
                # 默认佣金批准
                app.status = 1
                app.reviewed_at = datetime.now()
                app.reviewed_by = admin_user.id
                
                user = User.query.get(app.user_id)
                if user:
                    user.is_host = True
                    user.host_commission_rate = 10  # 默认10%
                
                db.session.commit()
                
                text = f"✅ 申请已批准\n\n用户：{user.username if user else '未知'}\n佣金比例：10%"
                keyboard = self.make_keyboard([
                    [{'text': '📝 返回列表', 'callback_data': 'admin:applications'}],
                    [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
                ])
                self.edit_message(chat_id, message_id, text, keyboard)
                
            elif action == 'approve_custom':
                self.set_session_state(chat_id, 'admin_approve_custom', {'app_id': app_id})
                
                text = "💰 自定义佣金批准\n\n请输入佣金比例（1-100的整数）："
                keyboard = self.make_keyboard([
                    [{'text': '❌ 取消', 'callback_data': f'admin:app:{app_id}'}]
                ])
                self.edit_message(chat_id, message_id, text, keyboard)
                
            elif action == 'reject':
                self.set_session_state(chat_id, 'admin_reject', {'app_id': app_id})
                
                text = "❌ 拒绝申请\n\n请输入拒绝原因："
                keyboard = self.make_keyboard([
                    [{'text': '❌ 取消', 'callback_data': f'admin:app:{app_id}'}]
                ])
                self.edit_message(chat_id, message_id, text, keyboard)
                
        except Exception as e:
            print(f'[AdminHandler] Application action error: {e}')
            self.handle_error(chat_id, e, message_id)

    def _handle_approve_custom_input(self, chat_id: int, admin_user, rate_str: str, session: dict) -> bool:
        """处理自定义佣金输入"""
        try:
            rate = int(rate_str.strip())
            if rate < 1 or rate > 100:
                self.send_message(chat_id, "❌ 佣金比例必须在1-100之间，请重新输入")
                return True
        except:
            self.send_message(chat_id, "❌ 无效的数字，请输入1-100的整数")
            return True
        
        data = session.get('data', {})
        app_id = data.get('app_id')
        
        if not app_id:
            self.clear_session_state(chat_id)
            return True
        
        try:
            from app import db
            from app.models.host_application import HostApplication
            from app.models.user import User
            
            app = HostApplication.query.get(app_id)
            if not app or app.status != 0:
                self.send_message(chat_id, "❌ 申请不存在或已处理")
                self.clear_session_state(chat_id)
                return True
            
            app.status = 1
            app.reviewed_at = datetime.now()
            app.reviewed_by = admin_user.id
            
            user = User.query.get(app.user_id)
            if user:
                user.is_host = True
                user.host_commission_rate = rate
            
            db.session.commit()
            self.clear_session_state(chat_id)
            
            text = f"✅ 申请已批准\n\n用户：{user.username if user else '未知'}\n佣金比例：{rate}%"
            keyboard = self.make_keyboard([
                [{'text': '📝 返回列表', 'callback_data': 'admin:applications'}],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ])
            self.send_message(chat_id, text, keyboard)
            
        except Exception as e:
            print(f'[AdminHandler] Approve custom error: {e}')
            self.send_message(chat_id, f"❌ 操作失败：{str(e)}")
            self.clear_session_state(chat_id)
        
        return True
    
    def _handle_reject_input(self, chat_id: int, admin_user, reason: str, session: dict) -> bool:
        """处理拒绝原因输入"""
        data = session.get('data', {})
        app_id = data.get('app_id')
        
        if not app_id:
            self.clear_session_state(chat_id)
            return True
        
        try:
            from app import db
            from app.models.host_application import HostApplication
            from app.models.user import User
            
            app = HostApplication.query.get(app_id)
            if not app or app.status != 0:
                self.send_message(chat_id, "❌ 申请不存在或已处理")
                self.clear_session_state(chat_id)
                return True
            
            app.status = 2
            app.reviewed_at = datetime.now()
            app.reviewed_by = admin_user.id
            if hasattr(app, 'reject_reason'):
                app.reject_reason = reason
            
            db.session.commit()
            self.clear_session_state(chat_id)
            
            user = User.query.get(app.user_id)
            
            text = f"✅ 申请已拒绝\n\n用户：{user.username if user else '未知'}\n拒绝原因：{reason}"
            keyboard = self.make_keyboard([
                [{'text': '📝 返回列表', 'callback_data': 'admin:applications'}],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ])
            self.send_message(chat_id, text, keyboard)
            
        except Exception as e:
            print(f'[AdminHandler] Reject error: {e}')
            self.send_message(chat_id, f"❌ 操作失败：{str(e)}")
            self.clear_session_state(chat_id)
        
        return True

    def _show_cards_menu(self, chat_id: int, message_id: int, user):
        """显示卡密管理菜单"""
        try:
            from app.models.redeem_code import RedeemCode
            from app import db
            
            # 统计
            total = RedeemCode.query.count()
            unused = RedeemCode.query.filter_by(status=0).count()
            used = RedeemCode.query.filter_by(status=1).count()
            
            total_amount = RedeemCode.query.filter_by(status=0).with_entities(
                db.func.sum(RedeemCode.amount)
            ).scalar() or Decimal('0')
            
            text = f"💳 卡密管理\n\n"
            text += f"总数：{total} 张\n"
            text += f"未使用：{unused} 张\n"
            text += f"已使用：{used} 张\n"
            text += f"未使用总额：¥{total_amount:.2f}"
            
            buttons = [
                [{'text': '➕ 生成卡密', 'callback_data': 'admin:cards:generate'}],
                [{'text': '📋 卡密列表', 'callback_data': 'admin:cards:list'}],
                [
                    {'text': '◀️ 返回', 'callback_data': 'admin:dashboard'},
                    {'text': '🏠 主菜单', 'callback_data': 'menu:main'}
                ]
            ]
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[AdminHandler] Cards menu error: {e}')
            self.handle_error(chat_id, e, message_id)
    
    def _handle_cards_action(self, chat_id: int, message_id: int, user, action: str):
        """处理卡密操作"""
        if action == 'generate':
            text = "➕ 生成卡密\n\n此功能请在网站后台操作"
            keyboard = self.make_keyboard([
                [{'text': '◀️ 返回', 'callback_data': 'admin:cards'}]
            ])
            self.edit_message(chat_id, message_id, text, keyboard)
        elif action == 'list':
            self._show_cards_list(chat_id, message_id, user)
    
    def _show_cards_list(self, chat_id: int, message_id: int, user, page: int = 1):
        """显示卡密列表"""
        try:
            from app.models.redeem_code import RedeemCode
            
            query = RedeemCode.query.filter_by(status=0)
            query = query.order_by(RedeemCode.created_at.desc())
            
            total = query.count()
            total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            page = max(1, min(page, total_pages))
            
            cards = query.offset((page - 1) * self.PAGE_SIZE).limit(self.PAGE_SIZE).all()
            
            if total == 0:
                text = "📋 卡密列表\n\n暂无未使用卡密"
            else:
                text = f"📋 卡密列表\n\n未使用：{total} 张\n\n"
                for card in cards:
                    text += f"• {card.code} - ¥{card.amount:.2f}\n"
            
            buttons = []
            
            # 分页
            if total_pages > 1:
                nav_buttons = []
                if page > 1:
                    nav_buttons.append({'text': '◀️', 'callback_data': f'admin:cards:list:{page - 1}'})
                nav_buttons.append({'text': f'{page}/{total_pages}', 'callback_data': 'noop'})
                if page < total_pages:
                    nav_buttons.append({'text': '▶️', 'callback_data': f'admin:cards:list:{page + 1}'})
                buttons.append(nav_buttons)
            
            buttons.append([{'text': '◀️ 返回', 'callback_data': 'admin:cards'}])
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[AdminHandler] Cards list error: {e}')
            self.handle_error(chat_id, e, message_id)

    def _show_admin_announcements(self, chat_id: int, message_id: int, user, page: int = 1):
        """显示公告管理列表"""
        try:
            from app.models.announcement import Announcement
            
            query = Announcement.query.order_by(
                Announcement.is_pinned.desc(),
                Announcement.created_at.desc()
            )
            
            total = query.count()
            total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            page = max(1, min(page, total_pages))
            
            announcements = query.offset((page - 1) * self.PAGE_SIZE).limit(self.PAGE_SIZE).all()
            
            if total == 0:
                text = "📢 公告管理\n\n暂无公告"
            else:
                text = f"📢 公告管理\n\n共 {total} 条公告"
            
            buttons = []
            
            # 发布新公告按钮
            buttons.append([{'text': '➕ 发布公告', 'callback_data': 'admin:announcement:new'}])
            
            for ann in announcements:
                pin_icon = '📌' if ann.is_pinned else ''
                title = ann.title[:20] + '...' if len(ann.title) > 20 else ann.title
                buttons.append([{'text': f'{pin_icon} {title}',
                               'callback_data': f'admin:announcement:{ann.id}'}])
            
            # 分页
            if total_pages > 1:
                nav_buttons = []
                if page > 1:
                    nav_buttons.append({'text': '◀️', 'callback_data': f'admin:announcements:{page - 1}'})
                nav_buttons.append({'text': f'{page}/{total_pages}', 'callback_data': 'noop'})
                if page < total_pages:
                    nav_buttons.append({'text': '▶️', 'callback_data': f'admin:announcements:{page + 1}'})
                buttons.append(nav_buttons)
            
            buttons.append([
                {'text': '◀️ 返回', 'callback_data': 'admin:dashboard'},
                {'text': '🏠 主菜单', 'callback_data': 'menu:main'}
            ])
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[AdminHandler] Announcements error: {e}')
            self.handle_error(chat_id, e, message_id)
    
    def _start_announcement_create(self, chat_id: int, message_id: int):
        """开始创建公告"""
        self.set_session_state(chat_id, 'admin_announcement', {'step': 'title'})
        
        text = "📢 发布新公告\n\n请输入公告标题："
        keyboard = self.make_keyboard([
            [{'text': '❌ 取消', 'callback_data': 'admin:announcements'}]
        ])
        
        self.edit_message(chat_id, message_id, text, keyboard)
    
    def _handle_announcement_input(self, chat_id: int, admin_user, text_input: str, session: dict) -> bool:
        """处理公告输入"""
        data = session.get('data', {})
        step = data.get('step')
        
        if step == 'title':
            data['title'] = text_input
            data['step'] = 'content'
            self.set_session_state(chat_id, 'admin_announcement', data)
            
            text = f"📢 发布新公告\n\n标题：{text_input}\n\n请输入公告内容："
            keyboard = self.make_keyboard([
                [{'text': '❌ 取消', 'callback_data': 'admin:announcements'}]
            ])
            self.send_message(chat_id, text, keyboard)
            return True
        
        elif step == 'content':
            data['content'] = text_input
            data['step'] = 'confirm'
            self.set_session_state(chat_id, 'admin_announcement', data)
            
            text = f"📢 确认发布公告\n\n"
            text += f"标题：{data['title']}\n\n"
            text += f"内容：\n{text_input[:200]}{'...' if len(text_input) > 200 else ''}\n\n"
            text += "是否置顶？"
            
            keyboard = self.make_keyboard([
                [
                    {'text': '📌 置顶发布', 'callback_data': 'admin:announcement:publish:pinned'},
                    {'text': '📝 普通发布', 'callback_data': 'admin:announcement:publish:normal'}
                ],
                [{'text': '❌ 取消', 'callback_data': 'admin:announcements'}]
            ])
            self.send_message(chat_id, text, keyboard)
            return True
        
        return False

    def _publish_announcement(self, chat_id: int, message_id: int, admin_user, is_pinned: bool):
        """发布公告"""
        session = self.get_session_state(chat_id)
        if not session or session.get('state') != 'admin_announcement':
            return
        
        data = session.get('data', {})
        if data.get('step') != 'confirm':
            return
        
        try:
            from app import db
            from app.models.announcement import Announcement
            
            announcement = Announcement(
                title=data['title'],
                content=data['content'],
                is_pinned=is_pinned,
                status=1
            )
            if hasattr(announcement, 'created_by'):
                announcement.created_by = admin_user.id
            
            db.session.add(announcement)
            db.session.commit()
            
            self.clear_session_state(chat_id)
            
            text = f"✅ 公告发布成功\n\n标题：{data['title']}\n置顶：{'是' if is_pinned else '否'}"
            keyboard = self.make_keyboard([
                [{'text': '📢 返回列表', 'callback_data': 'admin:announcements'}],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ])
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[AdminHandler] Announcement publish error: {e}')
            self.handle_error(chat_id, e, message_id)
    
    def _show_announcement_detail(self, chat_id: int, message_id: int, admin_user, ann_id: int):
        """显示公告详情"""
        try:
            from app.models.announcement import Announcement
            
            ann = Announcement.query.get(ann_id)
            if not ann:
                text = "❌ 公告不存在"
                keyboard = self.make_keyboard([[{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]])
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            text = f"📢 公告详情\n\n"
            text += f"标题：{ann.title}\n"
            text += f"置顶：{'是' if ann.is_pinned else '否'}\n"
            text += f"发布时间：{ann.created_at.strftime('%Y-%m-%d %H:%M') if ann.created_at else '未知'}\n\n"
            text += f"内容：\n{ann.content[:500]}{'...' if len(ann.content) > 500 else ''}"
            
            buttons = [
                [
                    {'text': '📌 取消置顶' if ann.is_pinned else '📌 置顶',
                     'callback_data': f'admin:announcement:{ann_id}:toggle_pin'},
                    {'text': '🗑️ 删除', 'callback_data': f'admin:announcement:{ann_id}:delete'}
                ],
                [
                    {'text': '◀️ 返回', 'callback_data': 'admin:announcements'},
                    {'text': '🏠 主菜单', 'callback_data': 'menu:main'}
                ]
            ]
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[AdminHandler] Announcement detail error: {e}')
            self.handle_error(chat_id, e, message_id)
    
    def _handle_announcement_action(self, chat_id: int, message_id: int, admin_user, ann_id: int, action: str):
        """处理公告操作"""
        try:
            from app import db
            from app.models.announcement import Announcement
            
            ann = Announcement.query.get(ann_id)
            if not ann:
                self.handle_error(chat_id, Exception('公告不存在'), message_id)
                return
            
            if action == 'toggle_pin':
                ann.is_pinned = not ann.is_pinned
                db.session.commit()
                self._show_announcement_detail(chat_id, message_id, admin_user, ann_id)
            elif action == 'delete':
                title = ann.title
                db.session.delete(ann)
                db.session.commit()
                
                text = f"✅ 公告已删除\n\n标题：{title}"
                keyboard = self.make_keyboard([
                    [{'text': '📢 返回列表', 'callback_data': 'admin:announcements'}],
                    [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
                ])
                self.edit_message(chat_id, message_id, text, keyboard)
                
        except Exception as e:
            print(f'[AdminHandler] Announcement action error: {e}')
            self.handle_error(chat_id, e, message_id)

    def _show_stats(self, chat_id: int, message_id: int, user):
        """显示统计报表"""
        try:
            from app.models.user import User
            from app.models.subdomain import Subdomain
            from app.models.purchase_record import PurchaseRecord
            from app import db
            
            now = datetime.now()
            
            # 今日
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_users = User.query.filter(User.created_at >= today_start).count()
            today_orders = PurchaseRecord.query.filter(
                PurchaseRecord.created_at >= today_start
            ).count()
            today_income = PurchaseRecord.query.filter(
                PurchaseRecord.created_at >= today_start
            ).with_entities(db.func.sum(PurchaseRecord.price)).scalar() or Decimal('0')
            
            # 本周
            week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            week_income = PurchaseRecord.query.filter(
                PurchaseRecord.created_at >= week_start
            ).with_entities(db.func.sum(PurchaseRecord.price)).scalar() or Decimal('0')
            
            # 本月
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            month_income = PurchaseRecord.query.filter(
                PurchaseRecord.created_at >= month_start
            ).with_entities(db.func.sum(PurchaseRecord.price)).scalar() or Decimal('0')
            
            # 总计
            total_income = PurchaseRecord.query.with_entities(
                db.func.sum(PurchaseRecord.price)
            ).scalar() or Decimal('0')
            
            text = f"📊 统计报表\n\n"
            text += f"📅 今日\n"
            text += f"新用户：{today_users}\n"
            text += f"订单数：{today_orders}\n"
            text += f"收入：¥{today_income:.2f}\n\n"
            text += f"📅 本周收入：¥{week_income:.2f}\n"
            text += f"📅 本月收入：¥{month_income:.2f}\n"
            text += f"📅 总收入：¥{total_income:.2f}"
            
            keyboard = self.make_keyboard([
                [{'text': '◀️ 返回', 'callback_data': 'admin:dashboard'}],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ])
            
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[AdminHandler] Stats error: {e}')
            self.handle_error(chat_id, e, message_id)
    
    def _start_broadcast(self, chat_id: int, message_id: int):
        """开始群发通知"""
        self.set_session_state(chat_id, 'admin_broadcast', {'step': 'input'})
        
        text = "📣 群发通知\n\n请输入要发送的消息内容："
        keyboard = self.make_keyboard([
            [{'text': '❌ 取消', 'callback_data': 'admin:dashboard'}]
        ])
        
        self.edit_message(chat_id, message_id, text, keyboard)
    
    def _handle_broadcast_input(self, chat_id: int, admin_user, message_text: str, session: dict) -> bool:
        """处理群发消息输入"""
        data = session.get('data', {})
        step = data.get('step')
        
        if step == 'input':
            data['message'] = message_text
            data['step'] = 'confirm'
            self.set_session_state(chat_id, 'admin_broadcast', data)
            
            text = f"📣 确认群发\n\n消息内容：\n{message_text}\n\n确认发送给所有绑定用户？"
            keyboard = self.make_keyboard([
                [
                    {'text': '✅ 确认发送', 'callback_data': 'admin:broadcast:confirm'},
                    {'text': '❌ 取消', 'callback_data': 'admin:broadcast:cancel'}
                ]
            ])
            self.send_message(chat_id, text, keyboard)
            return True
        
        return False
    
    def _confirm_broadcast(self, chat_id: int, message_id: int, admin_user):
        """确认群发"""
        session = self.get_session_state(chat_id)
        if not session or session.get('state') != 'admin_broadcast':
            return
        
        data = session.get('data', {})
        if data.get('step') != 'confirm':
            return
        
        message_text = data.get('message', '')
        
        try:
            from app.models.telegram import TelegramUser
            
            # 获取所有绑定用户
            tg_users = TelegramUser.query.filter(TelegramUser.user_id.isnot(None)).all()
            
            success_count = 0
            fail_count = 0
            
            for tg_user in tg_users:
                try:
                    self.send_message(tg_user.telegram_id, f"📣 系统通知\n\n{message_text}")
                    success_count += 1
                except:
                    fail_count += 1
            
            self.clear_session_state(chat_id)
            
            text = f"✅ 群发完成\n\n成功：{success_count}\n失败：{fail_count}"
            keyboard = self.make_keyboard([
                [{'text': '◀️ 返回', 'callback_data': 'admin:dashboard'}],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ])
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[AdminHandler] Broadcast error: {e}')
            self.handle_error(chat_id, e, message_id)
