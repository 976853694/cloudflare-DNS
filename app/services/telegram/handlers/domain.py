"""
域名管理处理器

处理域名列表、详情、设置等功能
"""

from datetime import datetime, timedelta
from .base import BaseHandler


class DomainHandler(BaseHandler):
    """域名管理处理器"""
    
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
        # 检查绑定
        if not self.require_bind(chat_id, telegram_id, message_id):
            return
        
        user = self.get_user(telegram_id)
        
        parts = data.split(':')
        action = parts[1] if len(parts) > 1 else ''
        
        if action == 'list':
            page = int(parts[2]) if len(parts) > 2 else 1
            filter_type = parts[3] if len(parts) > 3 else None
            self._show_domain_list(chat_id, message_id, user, telegram_id, page, filter_type)
        elif action.isdigit():
            domain_id = int(action)
            sub_action = parts[2] if len(parts) > 2 else None
            if sub_action == 'settings':
                self._show_domain_settings(chat_id, message_id, user, telegram_id, domain_id)
            elif sub_action == 'renew':
                self._show_domain_renew(chat_id, message_id, user, telegram_id, domain_id)
            elif sub_action == 'renew_confirm':
                self._do_domain_renew(chat_id, message_id, user, telegram_id, domain_id)
            elif sub_action == 'points_renew':
                self._show_points_renew(chat_id, message_id, user, telegram_id, domain_id)
            elif sub_action == 'points_renew_confirm':
                self._do_points_renew(chat_id, message_id, user, telegram_id, domain_id)
            elif sub_action == 'toggle_auto_renew':
                self._toggle_auto_renew(chat_id, message_id, user, telegram_id, domain_id)
            elif sub_action == 'toggle_ns_mode':
                self._toggle_ns_mode(chat_id, message_id, user, telegram_id, domain_id)
            else:
                self._show_domain_detail(chat_id, message_id, user, telegram_id, domain_id)
    
    def _show_domain_list(self, chat_id: int, message_id: int, user, 
                         telegram_id: int, page: int = 1, filter_type: str = None):
        """显示域名列表"""
        try:
            from app.models.subdomain import Subdomain
            
            query = Subdomain.query.filter_by(user_id=user.id)
            now = datetime.now()
            
            if filter_type == 'expiring':
                expiry_date = now + timedelta(days=7)
                query = query.filter(
                    Subdomain.expires_at > now,
                    Subdomain.expires_at <= expiry_date
                )
            elif filter_type == 'expired':
                query = query.filter(Subdomain.expires_at <= now)
            
            query = query.order_by(Subdomain.expires_at.asc())
            
            total = query.count()
            total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            page = max(1, min(page, total_pages))
            
            domains = query.offset((page - 1) * self.PAGE_SIZE).limit(self.PAGE_SIZE).all()
            
            if total == 0:
                text = "📋 我的域名\n\n暂无域名，点击下方按钮购买"
            else:
                text = f"📋 我的域名\n\n共 {total} 个域名"
                if filter_type:
                    filter_name = '即将到期' if filter_type == 'expiring' else '已过期'
                    text += f"（筛选：{filter_name}）"
                text += f"\n📄 第 {page}/{total_pages} 页\n\n"
                
                for d in domains:
                    status = self._get_domain_status(d)
                    text += f"{status} {d.full_domain}\n"
                    text += f"   到期：{d.expires_at.strftime('%Y-%m-%d')}\n"
            
            buttons = []
            
            # 域名按钮
            for d in domains:
                buttons.append([{'text': f'🌐 {d.full_domain}', 'callback_data': f'domain:{d.id}'}])
            
            # 分页按钮（优化版）
            if total_pages > 1:
                nav = []
                filter_param = filter_type or ""
                
                # 首页按钮（当前不在第一页时显示）
                if page > 2:
                    nav.append({'text': '⏮️', 'callback_data': f'domain:list:1:{filter_param}'})
                
                # 上一页按钮
                if page > 1:
                    nav.append({'text': '◀️', 'callback_data': f'domain:list:{page-1}:{filter_param}'})
                
                # 页码显示
                nav.append({'text': f'{page}/{total_pages}', 'callback_data': 'noop'})
                
                # 下一页按钮
                if page < total_pages:
                    nav.append({'text': '▶️', 'callback_data': f'domain:list:{page+1}:{filter_param}'})
                
                # 末页按钮（当前不在最后一页时显示）
                if page < total_pages - 1:
                    nav.append({'text': '⏭️', 'callback_data': f'domain:list:{total_pages}:{filter_param}'})
                
                if nav:
                    buttons.append(nav)
            
            # 筛选按钮
            buttons.append([
                {'text': '📅 即将到期', 'callback_data': 'domain:list:1:expiring'},
                {'text': '⚠️ 已过期', 'callback_data': 'domain:list:1:expired'}
            ])
            
            # 清除筛选按钮（如果有筛选）
            if filter_type:
                buttons.append([{'text': '🔄 显示全部', 'callback_data': 'domain:list:1:'}])
            
            buttons.append([
                {'text': '🛒 购买域名', 'callback_data': 'buy:plans'},
                {'text': '🏠 主菜单', 'callback_data': 'menu:main'}
            ])
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[DomainHandler] List error: {e}')
            self.handle_error(chat_id, e, message_id, telegram_id=telegram_id)
    
    def _show_domain_detail(self, chat_id: int, message_id: int, user, 
                           telegram_id: int, domain_id: int):
        """显示域名详情"""
        try:
            from app.models.subdomain import Subdomain
            from app.services.transfer_service import TransferService
            from app.services.plan_service import PlanService
            
            domain = Subdomain.query.filter_by(id=domain_id, user_id=user.id).first()
            if not domain:
                text = '❌ 域名不存在'
                buttons = [[{'text': '🏠 返回主菜单', 'callback_data': 'menu:main'}]]
                keyboard = self.make_keyboard(buttons)
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            status = self._get_domain_status(domain)
            
            text = f"🌐 域名详情\n\n"
            text += f"域名：{domain.full_domain}\n"
            text += f"状态：{status}\n"
            text += f"套餐：{domain.plan.name if domain.plan else '未知'}\n"
            text += f"到期时间：{domain.expires_at.strftime('%Y-%m-%d %H:%M')}\n"
            text += f"自动续费：{'✅ 开启' if domain.auto_renew else '❌ 关闭'}\n"
            
            # 显示续费窗口信息
            if domain.plan and domain.plan.renew_before_days > 0:
                remaining_days = PlanService.get_remaining_days(domain)
                if remaining_days >= 0:
                    if remaining_days <= domain.plan.renew_before_days:
                        text += f"续费窗口：✅ 可续费（剩余 {remaining_days} 天）\n"
                    else:
                        days_until_renew = remaining_days - domain.plan.renew_before_days
                        text += f"续费窗口：⏳ {days_until_renew} 天后可续费\n"
            
            text += f"创建时间：{domain.created_at.strftime('%Y-%m-%d')}"
            
            buttons = [
                [{'text': '📝 DNS 记录', 'callback_data': f'dns:list:{domain_id}'}],
                [
                    {'text': '🔄 续费', 'callback_data': f'domain:{domain_id}:renew'},
                    {'text': '⚙️ 设置', 'callback_data': f'domain:{domain_id}:settings'}
                ]
            ]
            
            # 检查积分续费功能是否开启
            if domain.plan and domain.plan.points_per_day > 0:
                buttons.append([{'text': '💰 积分续费', 'callback_data': f'domain:{domain_id}:points_renew'}])
            
            # 检查转移功能是否开启
            transfer_config = TransferService.get_config()
            if transfer_config['enabled']:
                buttons.append([{'text': '🔄 转移域名', 'callback_data': f'transfer:start:{domain_id}'}])
            
            buttons.append([{'text': '◀️ 返回列表', 'callback_data': 'domain:list'}])
            buttons.append([{'text': '🏠 主菜单', 'callback_data': 'menu:main'}])
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[DomainHandler] Detail error: {e}')
            self.handle_error(chat_id, e, message_id, telegram_id=telegram_id)
    
    def _show_domain_settings(self, chat_id: int, message_id: int, user,
                             telegram_id: int, domain_id: int):
        """显示域名设置"""
        try:
            from app.models.subdomain import Subdomain
            
            domain = Subdomain.query.filter_by(id=domain_id, user_id=user.id).first()
            if not domain:
                return
            
            text = f"⚙️ 域名设置\n\n"
            text += f"域名：{domain.full_domain}\n\n"
            text += f"自动续费：{'✅ 开启' if domain.auto_renew else '❌ 关闭'}\n"
            
            buttons = [
                [{'text': f"{'❌ 关闭' if domain.auto_renew else '✅ 开启'}自动续费", 
                  'callback_data': f'domain:{domain_id}:toggle_auto_renew'}],
                [{'text': '◀️ 返回详情', 'callback_data': f'domain:{domain_id}'}],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ]
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[DomainHandler] Settings error: {e}')
    
    def _show_domain_renew(self, chat_id: int, message_id: int, user,
                          telegram_id: int, domain_id: int):
        """显示续费确认"""
        try:
            from app.models.subdomain import Subdomain
            from app.services.plan_service import PlanService
            
            domain = Subdomain.query.filter_by(id=domain_id, user_id=user.id).first()
            if not domain or not domain.plan:
                return
            
            # 检查是否可以续费
            can_renew, error_msg, extra_data = PlanService.can_renew(domain_id, domain.plan.id)
            if not can_renew:
                # 解析错误信息
                error_parts = error_msg.split('|')
                display_msg = error_parts[1] if len(error_parts) > 1 else error_msg
                
                text = f"❌ 无法续费\n\n{display_msg}"
                
                # 显示额外信息
                if 'remaining_days' in extra_data and extra_data['remaining_days'] >= 0:
                    text += f"\n\n当前剩余：{extra_data['remaining_days']} 天"
                if 'renew_before_days' in extra_data:
                    text += f"\n续费窗口：到期前 {extra_data['renew_before_days']} 天"
                if 'renew_available_date' in extra_data:
                    text += f"\n可续费日期：{extra_data['renew_available_date']}"
                
                buttons = [
                    [{'text': '◀️ 返回详情', 'callback_data': f'domain:{domain_id}'}],
                    [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
                ]
                keyboard = self.make_keyboard(buttons)
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            price = domain.plan.price
            
            text = f"🔄 域名续费\n\n"
            text += f"域名：{domain.full_domain}\n"
            text += f"套餐：{domain.plan.name}\n"
            text += f"续费价格：¥{price}\n"
            text += f"当前余额：¥{user.balance}\n\n"
            text += f"续费后到期时间将延长 {domain.plan.duration_days} 天"
            
            buttons = [
                [{'text': '✅ 确认续费', 'callback_data': f'domain:{domain_id}:renew_confirm'}],
                [{'text': '❌ 取消', 'callback_data': f'domain:{domain_id}'}]
            ]
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[DomainHandler] Renew error: {e}')
    
    def _do_domain_renew(self, chat_id: int, message_id: int, user,
                        telegram_id: int, domain_id: int):
        """执行续费"""
        try:
            from app import db
            from app.models.subdomain import Subdomain
            
            domain = Subdomain.query.filter_by(id=domain_id, user_id=user.id).first()
            if not domain or not domain.plan:
                return
            
            price = domain.plan.price
            
            if user.balance < price:
                text = f'❌ 余额不足\n\n续费价格：¥{price}\n当前余额：¥{user.balance}'
                buttons = [
                    [{'text': '💳 充值', 'callback_data': 'account:recharge'}],
                    [{'text': '◀️ 返回', 'callback_data': f'domain:{domain_id}'}]
                ]
                keyboard = self.make_keyboard(buttons)
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            # 扣除余额
            user.balance -= price
            
            # 延长到期时间
            if domain.expires_at < datetime.now():
                domain.expires_at = datetime.now() + timedelta(days=domain.plan.duration_days)
            else:
                domain.expires_at += timedelta(days=domain.plan.duration_days)
            
            db.session.commit()
            
            text = f"✅ 续费成功！\n\n"
            text += f"域名：{domain.full_domain}\n"
            text += f"扣除金额：¥{price}\n"
            text += f"剩余余额：¥{user.balance}\n"
            text += f"新到期时间：{domain.expires_at.strftime('%Y-%m-%d')}"
            
            buttons = [
                [{'text': '🌐 查看域名', 'callback_data': f'domain:{domain_id}'}],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ]
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[DomainHandler] Renew execute error: {e}')
    
    def _toggle_auto_renew(self, chat_id: int, message_id: int, user,
                          telegram_id: int, domain_id: int):
        """切换自动续费"""
        try:
            from app import db
            from app.models.subdomain import Subdomain
            
            domain = Subdomain.query.filter_by(id=domain_id, user_id=user.id).first()
            if not domain:
                return
            
            domain.auto_renew = not domain.auto_renew
            db.session.commit()
            
            self._show_domain_settings(chat_id, message_id, user, telegram_id, domain_id)
            
        except Exception as e:
            print(f'[DomainHandler] Toggle auto renew error: {e}')
    
    def _toggle_ns_mode(self, chat_id: int, message_id: int, user,
                       telegram_id: int, domain_id: int):
        """切换 NS 模式"""
        # 暂不实现
        pass
    
    def _get_domain_status(self, domain) -> str:
        """获取域名状态图标"""
        now = datetime.now()
        if domain.expires_at <= now:
            return '🔴'  # 已过期
        elif domain.expires_at <= now + timedelta(days=7):
            return '🟡'  # 即将到期
        else:
            return '🟢'  # 正常
    
    def _show_points_renew(self, chat_id: int, message_id: int, user,
                          telegram_id: int, domain_id: int):
        """显示积分续费确认"""
        try:
            from app.models.subdomain import Subdomain
            from app.services.plan_service import PlanService
            
            domain = Subdomain.query.filter_by(id=domain_id, user_id=user.id).first()
            if not domain or not domain.plan:
                text = '❌ 域名不存在'
                buttons = [[{'text': '🏠 返回主菜单', 'callback_data': 'menu:main'}]]
                keyboard = self.make_keyboard(buttons)
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            # 检查是否支持积分续费
            if domain.plan.points_per_day <= 0:
                text = '❌ 该套餐不支持积分续费'
                buttons = [
                    [{'text': '◀️ 返回详情', 'callback_data': f'domain:{domain_id}'}],
                    [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
                ]
                keyboard = self.make_keyboard(buttons)
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            # 检查是否可以续费
            can_renew, error_msg, extra_data = PlanService.can_renew(domain_id, domain.plan.id)
            if not can_renew:
                error_parts = error_msg.split('|')
                display_msg = error_parts[1] if len(error_parts) > 1 else error_msg
                
                text = f"❌ 无法续费\n\n{display_msg}"
                
                if 'remaining_days' in extra_data and extra_data['remaining_days'] >= 0:
                    text += f"\n\n当前剩余：{extra_data['remaining_days']} 天"
                if 'renew_available_date' in extra_data:
                    text += f"\n可续费日期：{extra_data['renew_available_date']}"
                
                buttons = [
                    [{'text': '◀️ 返回详情', 'callback_data': f'domain:{domain_id}'}],
                    [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
                ]
                keyboard = self.make_keyboard(buttons)
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            # 计算所需积分
            success, error, cost_data = PlanService.calculate_points_cost(domain.plan.id)
            if not success:
                error_parts = error.split('|')
                display_msg = error_parts[1] if len(error_parts) > 1 else error
                text = f'❌ {display_msg}'
                buttons = [
                    [{'text': '◀️ 返回详情', 'callback_data': f'domain:{domain_id}'}],
                    [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
                ]
                keyboard = self.make_keyboard(buttons)
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            total_points = cost_data['total_points']
            renew_days = cost_data['days']
            
            text = f"💰 积分续费\n\n"
            text += f"域名：{domain.full_domain}\n"
            text += f"套餐：{domain.plan.name}\n"
            text += f"续费天数：{renew_days} 天\n"
            text += f"所需积分：{total_points}\n"
            text += f"当前积分：{user.points}\n"
            
            if user.points < total_points:
                text += f"\n❌ 积分不足，还需 {total_points - user.points} 积分"
                buttons = [
                    [{'text': '💰 积分中心', 'callback_data': 'points:menu'}],
                    [{'text': '◀️ 返回详情', 'callback_data': f'domain:{domain_id}'}]
                ]
            else:
                text += f"\n✅ 积分充足"
                buttons = [
                    [{'text': '✅ 确认续费', 'callback_data': f'domain:{domain_id}:points_renew_confirm'}],
                    [{'text': '❌ 取消', 'callback_data': f'domain:{domain_id}'}]
                ]
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[DomainHandler] Points renew error: {e}')
            import traceback
            traceback.print_exc()
    
    def _do_points_renew(self, chat_id: int, message_id: int, user,
                        telegram_id: int, domain_id: int):
        """执行积分续费"""
        try:
            from app.services.plan_service import PlanService
            
            # 调用 PlanService 执行积分续费
            success, error_msg, result_data = PlanService.renew_with_points(user.id, domain_id)
            
            if not success:
                error_parts = error_msg.split('|')
                display_msg = error_parts[1] if len(error_parts) > 1 else error_msg
                
                text = f"❌ 续费失败\n\n{display_msg}"
                
                if 'required_points' in result_data:
                    text += f"\n\n所需积分：{result_data['required_points']}"
                    text += f"\n当前积分：{result_data.get('current_points', user.points)}"
                
                buttons = [
                    [{'text': '💰 积分中心', 'callback_data': 'points:menu'}],
                    [{'text': '◀️ 返回详情', 'callback_data': f'domain:{domain_id}'}]
                ]
                keyboard = self.make_keyboard(buttons)
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            text = f"✅ 积分续费成功！\n\n"
            text += f"域名：{result_data['subdomain_name']}\n"
            text += f"续费天数：{result_data['days_added']} 天\n"
            text += f"消耗积分：{result_data['points_used']}\n"
            text += f"剩余积分：{result_data['points_balance']}\n"
            text += f"新到期时间：{result_data['new_expires_at'][:10]}"
            
            buttons = [
                [{'text': '🌐 查看域名', 'callback_data': f'domain:{domain_id}'}],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ]
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[DomainHandler] Points renew execute error: {e}')
            import traceback
            traceback.print_exc()
