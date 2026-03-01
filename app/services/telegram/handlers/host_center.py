"""
托管商中心处理器

处理托管商仪表盘、渠道管理、域名管理、套餐管理、交易记录、收益统计等功能
"""

from datetime import datetime, timedelta
from decimal import Decimal
from .base import BaseHandler


class HostCenterHandler(BaseHandler):
    """托管商中心处理器"""
    
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
        # 检查绑定和托管商权限
        user = self.get_user(telegram_id)
        if not user:
            self.require_bind(chat_id, telegram_id, message_id)
            return
        
        if not self.check_permission(user, 'host'):
            self.require_host(chat_id, telegram_id, message_id)
            return
        
        parts = data.split(':')
        
        if data in ['hc:dashboard', 'menu:host_center']:
            self._show_dashboard(chat_id, message_id, user)
        elif data == 'hc:channels' or data.startswith('hc:channels:'):
            page = int(parts[2]) if len(parts) >= 3 else 1
            self._show_channels(chat_id, message_id, user, page)

        elif data == 'hc:domains' or data.startswith('hc:domains:'):
            page = int(parts[2]) if len(parts) >= 3 else 1
            self._show_host_domains(chat_id, message_id, user, page)
        elif data == 'hc:plans' or data.startswith('hc:plans:'):
            page = int(parts[2]) if len(parts) >= 3 else 1
            self._show_host_plans(chat_id, message_id, user, page)
        elif data == 'hc:orders' or data.startswith('hc:orders:'):
            page = int(parts[2]) if len(parts) >= 3 else 1
            self._show_host_orders(chat_id, message_id, user, page)
        elif data == 'hc:stats':
            self._show_stats(chat_id, message_id, user)
        elif data.startswith('hc:channel:'):
            try:
                channel_id = int(parts[2])
                if len(parts) >= 4:
                    action = parts[3]
                    self._handle_channel_action(chat_id, message_id, user, channel_id, action)
                else:
                    self._show_channel_detail(chat_id, message_id, user, channel_id)
            except:
                self.handle_error(chat_id, Exception('参数错误'), message_id)
        elif data.startswith('hc:domain:'):
            try:
                domain_id = int(parts[2])
                if len(parts) >= 4:
                    action = parts[3]
                    self._handle_domain_action(chat_id, message_id, user, domain_id, action)
                else:
                    self._show_domain_detail(chat_id, message_id, user, domain_id)
            except:
                self.handle_error(chat_id, Exception('参数错误'), message_id)
        elif data.startswith('hc:plan:'):
            try:
                plan_id = int(parts[2])
                if len(parts) >= 4:
                    action = parts[3]
                    self._handle_plan_action(chat_id, message_id, user, plan_id, action)
                else:
                    self._show_plan_detail(chat_id, message_id, user, plan_id)
            except:
                self.handle_error(chat_id, Exception('参数错误'), message_id)
    
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
        if not user or not self.check_permission(user, 'host'):
            return False
        
        state = session.get('state')
        
        if state == 'hc_plan_price':
            return self._handle_plan_price_input(chat_id, user, text, session)
        
        return False

    def _show_dashboard(self, chat_id: int, message_id: int, user):
        """显示托管商仪表盘"""
        try:
            from app.models.domain import Domain
            from app.models.subdomain import Subdomain
            from app.models.host_transaction import HostTransaction
            from app import db
            
            # 统计数据 - 托管商拥有的域名
            host_domains = Domain.query.filter_by(owner_id=user.id).count()
            
            # 本月收益
            now = datetime.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            month_earnings = HostTransaction.query.filter(
                HostTransaction.host_id == user.id,
                HostTransaction.created_at >= month_start
            ).with_entities(db.func.sum(HostTransaction.host_earnings)).scalar() or Decimal('0')
            
            # 总收益
            total_earnings = HostTransaction.query.filter(
                HostTransaction.host_id == user.id
            ).with_entities(db.func.sum(HostTransaction.host_earnings)).scalar() or Decimal('0')
            
            # 佣金比例
            commission_rate = getattr(user, 'host_commission_rate', 10) or 10
            
            text = f"🏢 托管商中心\n\n"
            text += f"💰 余额：¥{user.balance:.2f}\n"
            text += f"📊 佣金比例：{commission_rate}%\n\n"
            text += f"📈 收益统计\n"
            text += f"本月收益：¥{month_earnings:.2f}\n"
            text += f"总收益：¥{total_earnings:.2f}\n\n"
            text += f"📦 资源统计\n"
            text += f"托管域名：{host_domains} 个"
            
            buttons = [
                [
                    {'text': '🌐 渠道管理', 'callback_data': 'hc:channels'},
                    {'text': '📋 域名管理', 'callback_data': 'hc:domains'}
                ],
                [
                    {'text': '📦 套餐管理', 'callback_data': 'hc:plans'},
                    {'text': '📜 交易记录', 'callback_data': 'hc:orders'}
                ],
                [{'text': '📊 收益统计', 'callback_data': 'hc:stats'}],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ]
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[HostCenterHandler] Dashboard error: {e}')
            self.handle_error(chat_id, e, message_id)

    def _show_channels(self, chat_id: int, message_id: int, user, page: int = 1):
        """显示渠道列表"""
        try:
            from app.models.dns_channel import DNSChannel
            
            query = DNSChannel.query.filter_by(user_id=user.id)
            query = query.order_by(DNSChannel.created_at.desc())
            
            total = query.count()
            total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            page = max(1, min(page, total_pages))
            
            channels = query.offset((page - 1) * self.PAGE_SIZE).limit(self.PAGE_SIZE).all()
            
            if total == 0:
                text = "🌐 渠道管理\n\n暂无渠道"
            else:
                text = f"🌐 渠道管理\n\n共 {total} 个渠道"
            
            buttons = []
            
            for channel in channels:
                status_icon = '✅' if channel.status == 1 else '❌'
                verified_icon = '🔒' if getattr(channel, 'verified', False) else '⚠️'
                buttons.append([{'text': f'{status_icon}{verified_icon} {channel.name}',
                               'callback_data': f'hc:channel:{channel.id}'}])
            
            # 分页
            if total_pages > 1:
                nav_buttons = []
                if page > 1:
                    nav_buttons.append({'text': '◀️', 'callback_data': f'hc:channels:{page - 1}'})
                nav_buttons.append({'text': f'{page}/{total_pages}', 'callback_data': 'noop'})
                if page < total_pages:
                    nav_buttons.append({'text': '▶️', 'callback_data': f'hc:channels:{page + 1}'})
                buttons.append(nav_buttons)
            
            buttons.append([
                {'text': '◀️ 返回', 'callback_data': 'hc:dashboard'},
                {'text': '🏠 主菜单', 'callback_data': 'menu:main'}
            ])
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[HostCenterHandler] Channels error: {e}')
            self.handle_error(chat_id, e, message_id)
    
    def _show_channel_detail(self, chat_id: int, message_id: int, user, channel_id: int):
        """显示渠道详情"""
        try:
            from app.models.dns_channel import DNSChannel
            
            channel = DNSChannel.query.filter_by(id=channel_id, user_id=user.id).first()
            if not channel:
                text = "❌ 渠道不存在"
                keyboard = self.make_keyboard([[{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]])
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            status_text = '启用' if channel.status == 1 else '禁用'
            verified_text = '已验证' if getattr(channel, 'verified', False) else '未验证'
            
            text = f"🌐 渠道详情\n\n"
            text += f"名称：{channel.name}\n"
            text += f"类型：{channel.provider}\n"
            text += f"状态：{status_text}\n"
            text += f"验证：{verified_text}"
            
            buttons = [
                [
                    {'text': '🔍 验证', 'callback_data': f'hc:channel:{channel_id}:verify'},
                    {'text': '🔓 启用' if channel.status == 0 else '🔒 禁用',
                     'callback_data': f'hc:channel:{channel_id}:toggle'}
                ],
                [
                    {'text': '◀️ 返回', 'callback_data': 'hc:channels'},
                    {'text': '🏠 主菜单', 'callback_data': 'menu:main'}
                ]
            ]
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[HostCenterHandler] Channel detail error: {e}')
            self.handle_error(chat_id, e, message_id)

    def _handle_channel_action(self, chat_id: int, message_id: int, user, channel_id: int, action: str):
        """处理渠道操作"""
        try:
            from app import db
            from app.models.dns_channel import DNSChannel
            
            channel = DNSChannel.query.filter_by(id=channel_id, user_id=user.id).first()
            if not channel:
                self.handle_error(chat_id, Exception('渠道不存在'), message_id)
                return
            
            if action == 'toggle':
                channel.status = 0 if channel.status == 1 else 1
                db.session.commit()
                self._show_channel_detail(chat_id, message_id, user, channel_id)
            elif action == 'verify':
                # 验证渠道逻辑
                self._show_channel_detail(chat_id, message_id, user, channel_id)
                
        except Exception as e:
            print(f'[HostCenterHandler] Channel action error: {e}')
            self.handle_error(chat_id, e, message_id)
    
    def _show_host_domains(self, chat_id: int, message_id: int, user, page: int = 1):
        """显示托管域名列表"""
        try:
            from app.models.domain import Domain
            from app.models.subdomain import Subdomain
            
            # 查询托管商拥有的域名
            query = Domain.query.filter_by(owner_id=user.id)
            query = query.order_by(Domain.name.asc())
            
            total = query.count()
            total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            page = max(1, min(page, total_pages))
            
            domains = query.offset((page - 1) * self.PAGE_SIZE).limit(self.PAGE_SIZE).all()
            
            if total == 0:
                text = "📋 托管域名\n\n暂无托管域名"
            else:
                text = f"📋 托管域名\n\n共 {total} 个域名"
            
            buttons = []
            
            for domain in domains:
                sub_count = Subdomain.query.filter_by(domain_id=domain.id).count()
                status_icon = '✅' if domain.status == 1 else '❌'
                buttons.append([{'text': f'{status_icon} {domain.name} ({sub_count})',
                               'callback_data': f'hc:domain:{domain.id}'}])
            
            # 分页
            if total_pages > 1:
                nav_buttons = []
                if page > 1:
                    nav_buttons.append({'text': '◀️', 'callback_data': f'hc:domains:{page - 1}'})
                nav_buttons.append({'text': f'{page}/{total_pages}', 'callback_data': 'noop'})
                if page < total_pages:
                    nav_buttons.append({'text': '▶️', 'callback_data': f'hc:domains:{page + 1}'})
                buttons.append(nav_buttons)
            
            buttons.append([
                {'text': '◀️ 返回', 'callback_data': 'hc:dashboard'},
                {'text': '🏠 主菜单', 'callback_data': 'menu:main'}
            ])
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[HostCenterHandler] Host domains error: {e}')
            self.handle_error(chat_id, e, message_id)

    def _show_domain_detail(self, chat_id: int, message_id: int, user, domain_id: int):
        """显示托管域名详情"""
        try:
            from app.models.domain import Domain
            from app.models.subdomain import Subdomain
            
            domain = Domain.query.filter_by(id=domain_id, owner_id=user.id).first()
            if not domain:
                text = "❌ 域名不存在"
                keyboard = self.make_keyboard([[{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]])
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            sub_count = Subdomain.query.filter_by(domain_id=domain.id).count()
            status_text = '启用' if domain.status == 1 else '禁用'
            allow_reg = '是' if domain.allow_register == 1 else '否'
            
            text = f"📋 域名详情\n\n"
            text += f"域名：{domain.name}\n"
            text += f"子域名数：{sub_count}\n"
            text += f"状态：{status_text}\n"
            text += f"允许注册：{allow_reg}"
            
            buttons = [
                [
                    {'text': '✅ 允许注册' if domain.allow_register == 0 else '❌ 禁止注册',
                     'callback_data': f'hc:domain:{domain_id}:toggle_reg'},
                    {'text': '🔓 启用' if domain.status == 0 else '🔒 禁用',
                     'callback_data': f'hc:domain:{domain_id}:toggle'}
                ],
                [
                    {'text': '◀️ 返回', 'callback_data': 'hc:domains'},
                    {'text': '🏠 主菜单', 'callback_data': 'menu:main'}
                ]
            ]
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[HostCenterHandler] Domain detail error: {e}')
            self.handle_error(chat_id, e, message_id)
    
    def _handle_domain_action(self, chat_id: int, message_id: int, user, domain_id: int, action: str):
        """处理域名操作"""
        try:
            from app import db
            from app.models.domain import Domain
            
            domain = Domain.query.filter_by(id=domain_id, owner_id=user.id).first()
            if not domain:
                self.handle_error(chat_id, Exception('域名不存在'), message_id)
                return
            
            if action == 'toggle':
                domain.status = 0 if domain.status == 1 else 1
                db.session.commit()
            elif action == 'toggle_reg':
                domain.allow_register = 0 if domain.allow_register == 1 else 1
                db.session.commit()
            
            self._show_domain_detail(chat_id, message_id, user, domain_id)
                
        except Exception as e:
            print(f'[HostCenterHandler] Domain action error: {e}')
            self.handle_error(chat_id, e, message_id)

    def _show_host_plans(self, chat_id: int, message_id: int, user, page: int = 1):
        """显示套餐列表"""
        try:
            from app.models.plan import Plan
            
            # 查询托管商拥有的套餐
            query = Plan.query.filter_by(owner_id=user.id)
            query = query.order_by(Plan.price.asc())
            
            total = query.count()
            total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            page = max(1, min(page, total_pages))
            
            plans = query.offset((page - 1) * self.PAGE_SIZE).limit(self.PAGE_SIZE).all()
            
            if total == 0:
                text = "📦 套餐管理\n\n暂无套餐"
            else:
                text = f"📦 套餐管理\n\n共 {total} 个套餐"
            
            buttons = []
            
            for plan in plans:
                status_icon = '✅' if plan.status == 1 else '❌'
                buttons.append([{'text': f'{status_icon} {plan.name} - ¥{plan.price:.2f}',
                               'callback_data': f'hc:plan:{plan.id}'}])
            
            # 分页
            if total_pages > 1:
                nav_buttons = []
                if page > 1:
                    nav_buttons.append({'text': '◀️', 'callback_data': f'hc:plans:{page - 1}'})
                nav_buttons.append({'text': f'{page}/{total_pages}', 'callback_data': 'noop'})
                if page < total_pages:
                    nav_buttons.append({'text': '▶️', 'callback_data': f'hc:plans:{page + 1}'})
                buttons.append(nav_buttons)
            
            buttons.append([
                {'text': '◀️ 返回', 'callback_data': 'hc:dashboard'},
                {'text': '🏠 主菜单', 'callback_data': 'menu:main'}
            ])
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[HostCenterHandler] Plans error: {e}')
            self.handle_error(chat_id, e, message_id)
    
    def _show_plan_detail(self, chat_id: int, message_id: int, user, plan_id: int):
        """显示套餐详情"""
        try:
            from app.models.plan import Plan
            
            plan = Plan.query.filter_by(id=plan_id, owner_id=user.id).first()
            if not plan:
                text = "❌ 套餐不存在"
                keyboard = self.make_keyboard([[{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]])
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            status_text = '启用' if plan.status == 1 else '禁用'
            
            text = f"📦 套餐详情\n\n"
            text += f"名称：{plan.name}\n"
            text += f"价格：¥{plan.price:.2f}\n"
            text += f"状态：{status_text}"
            if hasattr(plan, 'description') and plan.description:
                text += f"\n描述：{plan.description}"
            
            buttons = [
                [
                    {'text': '💰 修改价格', 'callback_data': f'hc:plan:{plan_id}:price'},
                    {'text': '🔓 启用' if plan.status == 0 else '🔒 禁用',
                     'callback_data': f'hc:plan:{plan_id}:toggle'}
                ],
                [
                    {'text': '◀️ 返回', 'callback_data': 'hc:plans'},
                    {'text': '🏠 主菜单', 'callback_data': 'menu:main'}
                ]
            ]
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[HostCenterHandler] Plan detail error: {e}')
            self.handle_error(chat_id, e, message_id)

    def _handle_plan_action(self, chat_id: int, message_id: int, user, plan_id: int, action: str):
        """处理套餐操作"""
        try:
            from app import db
            from app.models.plan import Plan
            
            plan = Plan.query.filter_by(id=plan_id, owner_id=user.id).first()
            if not plan:
                self.handle_error(chat_id, Exception('套餐不存在'), message_id)
                return
            
            if action == 'toggle':
                plan.status = 0 if plan.status == 1 else 1
                db.session.commit()
                self._show_plan_detail(chat_id, message_id, user, plan_id)
            elif action == 'price':
                # 设置会话状态，等待价格输入
                self.session.set(chat_id, 'hc_plan_price', {
                    'plan_id': plan_id,
                    'plan_name': plan.name,
                    'current_price': float(plan.price)
                })
                self.set_session_state(chat_id, 'hc_plan_price', {'plan_id': plan_id})
                
                text = f"💰 修改套餐价格\n\n"
                text += f"套餐：{plan.name}\n"
                text += f"当前价格：¥{plan.price:.2f}\n\n"
                text += "请输入新价格（数字）："
                
                keyboard = self.make_keyboard([
                    [{'text': '❌ 取消', 'callback_data': f'hc:plan:{plan_id}'}]
                ])
                
                self.edit_message(chat_id, message_id, text, keyboard)
                
        except Exception as e:
            print(f'[HostCenterHandler] Plan action error: {e}')
            self.handle_error(chat_id, e, message_id)
    
    def _handle_plan_price_input(self, chat_id: int, user, text: str, session: dict) -> bool:
        """处理套餐价格输入"""
        try:
            new_price = Decimal(text.strip())
            if new_price < 0:
                self.send_message(chat_id, "❌ 价格不能为负数，请重新输入")
                return True
        except:
            self.send_message(chat_id, "❌ 无效的价格，请输入数字")
            return True
        
        plan_id = session.get('data', {}).get('plan_id')
        if not plan_id:
            self.clear_session_state(chat_id)
            return True
        
        try:
            from app import db
            from app.models.plan import Plan
            
            plan = Plan.query.filter_by(id=plan_id, owner_id=user.id).first()
            if not plan:
                self.send_message(chat_id, "❌ 套餐不存在")
                self.clear_session_state(chat_id)
                return True
            
            old_price = plan.price
            plan.price = new_price
            db.session.commit()
            
            self.clear_session_state(chat_id)
            
            text = f"✅ 价格修改成功\n\n"
            text += f"套餐：{plan.name}\n"
            text += f"原价格：¥{old_price:.2f}\n"
            text += f"新价格：¥{new_price:.2f}"
            
            keyboard = self.make_keyboard([
                [{'text': '📦 返回套餐', 'callback_data': f'hc:plan:{plan_id}'}],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ])
            
            self.send_message(chat_id, text, keyboard)
            
        except Exception as e:
            print(f'[HostCenterHandler] Plan price update error: {e}')
            self.send_message(chat_id, f"❌ 修改失败：{str(e)}")
            self.clear_session_state(chat_id)
        
        return True

    def _show_host_orders(self, chat_id: int, message_id: int, user, page: int = 1):
        """显示交易记录"""
        try:
            from app.models.host_transaction import HostTransaction
            from app import db
            
            query = HostTransaction.query.filter_by(host_id=user.id)
            query = query.order_by(HostTransaction.created_at.desc())
            
            total = query.count()
            total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            page = max(1, min(page, total_pages))
            
            transactions = query.offset((page - 1) * self.PAGE_SIZE).limit(self.PAGE_SIZE).all()
            
            # 计算总收益
            total_earnings = HostTransaction.query.filter_by(
                host_id=user.id
            ).with_entities(db.func.sum(HostTransaction.host_earnings)).scalar() or Decimal('0')
            
            if total == 0:
                text = "📜 交易记录\n\n暂无记录"
            else:
                text = f"📜 交易记录\n\n"
                text += f"共 {total} 条记录\n"
                text += f"总收益：¥{total_earnings:.2f}\n\n"
                
                for tx in transactions:
                    date = tx.created_at.strftime('%m-%d') if tx.created_at else ''
                    domain_name = tx.domain.name if tx.domain else '未知'
                    text += f"• {domain_name}\n"
                    text += f"  ¥{tx.total_amount:.2f} | 收益 ¥{tx.host_earnings:.2f} | {date}\n"
            
            buttons = []
            
            # 分页
            if total_pages > 1:
                nav_buttons = []
                if page > 1:
                    nav_buttons.append({'text': '◀️', 'callback_data': f'hc:orders:{page - 1}'})
                nav_buttons.append({'text': f'{page}/{total_pages}', 'callback_data': 'noop'})
                if page < total_pages:
                    nav_buttons.append({'text': '▶️', 'callback_data': f'hc:orders:{page + 1}'})
                buttons.append(nav_buttons)
            
            buttons.append([
                {'text': '◀️ 返回', 'callback_data': 'hc:dashboard'},
                {'text': '🏠 主菜单', 'callback_data': 'menu:main'}
            ])
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[HostCenterHandler] Orders error: {e}')
            self.handle_error(chat_id, e, message_id)
    
    def _show_stats(self, chat_id: int, message_id: int, user):
        """显示收益统计"""
        try:
            from app.models.host_transaction import HostTransaction
            from app import db
            
            now = datetime.now()
            
            # 今日
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_earnings = HostTransaction.query.filter(
                HostTransaction.host_id == user.id,
                HostTransaction.created_at >= today_start
            ).with_entities(db.func.sum(HostTransaction.host_earnings)).scalar() or Decimal('0')
            
            today_orders = HostTransaction.query.filter(
                HostTransaction.host_id == user.id,
                HostTransaction.created_at >= today_start
            ).count()
            
            # 本周
            week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            week_earnings = HostTransaction.query.filter(
                HostTransaction.host_id == user.id,
                HostTransaction.created_at >= week_start
            ).with_entities(db.func.sum(HostTransaction.host_earnings)).scalar() or Decimal('0')
            
            # 本月
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            month_earnings = HostTransaction.query.filter(
                HostTransaction.host_id == user.id,
                HostTransaction.created_at >= month_start
            ).with_entities(db.func.sum(HostTransaction.host_earnings)).scalar() or Decimal('0')
            
            # 总计
            total_earnings = HostTransaction.query.filter(
                HostTransaction.host_id == user.id
            ).with_entities(db.func.sum(HostTransaction.host_earnings)).scalar() or Decimal('0')
            
            text = f"📊 收益统计\n\n"
            text += f"📅 今日\n"
            text += f"订单：{today_orders} 笔\n"
            text += f"收益：¥{today_earnings:.2f}\n\n"
            text += f"📅 本周收益：¥{week_earnings:.2f}\n"
            text += f"📅 本月收益：¥{month_earnings:.2f}\n"
            text += f"📅 总收益：¥{total_earnings:.2f}"
            
            keyboard = self.make_keyboard([
                [{'text': '◀️ 返回', 'callback_data': 'hc:dashboard'}],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ])
            
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[HostCenterHandler] Stats error: {e}')
            self.handle_error(chat_id, e, message_id)
