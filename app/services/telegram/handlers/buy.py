"""
购买处理器

处理域名购买流程
"""

from .base import BaseHandler


class BuyHandler(BaseHandler):
    """购买处理器"""
    
    PAGE_SIZE = 5
    
    def handle_callback(self, chat_id: int, message_id: int, telegram_id: int,
                       user_info: dict, data: str):
        """处理回调"""
        if not self.require_bind(chat_id, telegram_id, message_id):
            return
        
        user = self.get_user(telegram_id)
        parts = data.split(':')
        action = parts[1] if len(parts) > 1 else ''
        
        try:
            if action == 'plans':
                page = int(parts[2]) if len(parts) > 2 else 1
                self._show_plan_list(chat_id, message_id, user, telegram_id, page)
            elif action == 'plan' and len(parts) > 2:
                plan_id = int(parts[2])
                self._show_suffix_select(chat_id, message_id, user, telegram_id, plan_id)
            elif action == 'suffix' and len(parts) > 3:
                plan_id = int(parts[2])
                domain_id = int(parts[3])
                self._handle_suffix_select(chat_id, message_id, telegram_id, plan_id, domain_id)
            elif action == 'check':
                self._check_availability(chat_id, message_id, user, telegram_id)
            elif action == 'coupon':
                self._show_coupon_input(chat_id, message_id, telegram_id)
            elif action == 'confirm':
                self._show_order_confirm(chat_id, message_id, user, telegram_id)
            elif action == 'execute':
                self._execute_purchase(chat_id, message_id, user, telegram_id)
        except Exception as e:
            print(f'[BuyHandler] Callback error: {e}')
            import traceback
            traceback.print_exc()
            self.send_message(chat_id, f"❌ 操作失败：{str(e)}")
    
    def handle_text_input(self, chat_id: int, telegram_id: int, text: str, session: dict) -> bool:
        """处理文本输入"""
        state = session.get('state', '')
        print(f'[BuyHandler] handle_text_input: state={state}, text={text}')
        
        if state == 'buy_prefix':
            return self._handle_prefix_input(chat_id, telegram_id, text, session)
        elif state == 'buy_coupon':
            return self._handle_coupon_input(chat_id, telegram_id, text, session)
        
        print(f'[BuyHandler] handle_text_input: unhandled state={state}')
        return False
    
    def _show_plan_list(self, chat_id: int, message_id: int, user,
                       telegram_id: int, page: int = 1):
        """显示套餐列表"""
        try:
            from app.models.plan import Plan
            from app.services.plan_service import PlanService
            
            query = Plan.query.filter_by(status=1).order_by(Plan.price.asc())
            
            total = query.count()
            total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            page = max(1, min(page, total_pages))
            
            plans = query.offset((page - 1) * self.PAGE_SIZE).limit(self.PAGE_SIZE).all()
            
            text = f"🛒 购买域名\n\n"
            text += f"共 {total} 个套餐"
            if total > 0:
                text += f"（第 {page}/{total_pages} 页）"
            text += "\n\n请选择套餐："
            
            buttons = []
            for p in plans:
                duration = '永久' if p.duration_days == -1 else f'{p.duration_days}天'
                
                # 构建套餐显示文本
                plan_text = p.name
                
                # 显示免费标识
                if hasattr(p, 'is_free') and p.is_free:
                    plan_text = f'🆓 {plan_text}'
                
                # 显示价格
                plan_text += f' - ¥{p.price}/{duration}'
                
                # 显示剩余购买次数
                if p.max_purchase_count > 0:
                    purchase_count = PlanService.get_user_purchase_count(user.id, p.id)
                    remaining = p.max_purchase_count - purchase_count
                    if remaining <= 0:
                        plan_text += ' [已达上限]'
                    else:
                        plan_text += f' [剩余{remaining}次]'
                
                buttons.append([{
                    'text': plan_text,
                    'callback_data': f'buy:plan:{p.id}'
                }])
            
            # 分页
            if total_pages > 1:
                nav = []
                if page > 1:
                    nav.append({'text': '◀️', 'callback_data': f'buy:plans:{page-1}'})
                if page < total_pages:
                    nav.append({'text': '▶️', 'callback_data': f'buy:plans:{page+1}'})
                if nav:
                    buttons.append(nav)
            
            buttons.append([{'text': '🏠 返回主菜单', 'callback_data': 'menu:main'}])
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[BuyHandler] Plan list error: {e}')
    
    def _show_suffix_select(self, chat_id: int, message_id: int, user,
                           telegram_id: int, plan_id: int):
        """显示域名后缀选择"""
        try:
            from app.models.plan import Plan
            from app.models.domain import Domain
            from app.services.plan_service import PlanService
            
            plan = Plan.query.get(plan_id)
            if not plan:
                return
            
            # 检查购买次数限制
            can_purchase, error_msg, extra_data = PlanService.can_purchase(user.id, plan_id)
            if not can_purchase:
                # 解析错误信息
                error_parts = error_msg.split('|')
                display_msg = error_parts[1] if len(error_parts) > 1 else error_msg
                
                text = f"❌ 无法购买此套餐\n\n{display_msg}"
                
                if 'purchase_count' in extra_data:
                    text += f"\n\n当前购买次数：{extra_data['purchase_count']}"
                    text += f"\n最大购买次数：{extra_data['max_purchase_count']}"
                
                buttons = [
                    [{'text': '◀️ 返回套餐列表', 'callback_data': 'buy:plans'}],
                    [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
                ]
                keyboard = self.make_keyboard(buttons)
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            # 获取套餐关联的域名
            domains = plan.domains
            
            text = f"🛒 购买域名\n\n"
            text += f"套餐：{plan.name}\n"
            text += f"价格：¥{plan.price}\n\n"
            text += "请选择域名后缀："
            
            buttons = []
            for d in domains:
                buttons.append([{
                    'text': f'.{d.name}',
                    'callback_data': f'buy:suffix:{plan_id}:{d.id}'
                }])
            
            buttons.append([{'text': '◀️ 返回套餐', 'callback_data': 'buy:plans'}])
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[BuyHandler] Suffix select error: {e}')
    
    def _handle_suffix_select(self, chat_id: int, message_id: int,
                             telegram_id: int, plan_id: int, domain_id: int):
        """处理后缀选择"""
        try:
            from app.models.plan import Plan
            from app.models.domain import Domain
            
            plan = Plan.query.get(plan_id)
            domain = Domain.query.get(domain_id)
            
            if not plan or not domain:
                print(f'[BuyHandler] Suffix select: plan={plan}, domain={domain}')
                self.send_message(chat_id, "❌ 套餐或域名不存在")
                return
            
            # 设置会话状态
            self.set_session_state(chat_id, 'buy_prefix', {
                'plan_id': plan_id,
                'domain_id': domain_id,
                'message_id': message_id
            })
            
            # 从套餐获取长度限制
            min_len = plan.min_length or 1
            max_len = plan.max_length or 63
            
            text = f"🛒 购买域名\n\n"
            text += f"套餐：{plan.name}\n"
            text += f"后缀：.{domain.name}\n\n"
            text += "请输入域名前缀：\n"
            text += f"（{min_len}-{max_len} 个字符）"
            
            buttons = [[{'text': '❌ 取消', 'callback_data': 'buy:plans'}]]
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[BuyHandler] Suffix select error: {e}')
            import traceback
            traceback.print_exc()
            self.send_message(chat_id, f"❌ 操作失败：{str(e)}")
    
    def _handle_prefix_input(self, chat_id: int, telegram_id: int, text: str, session: dict) -> bool:
        """处理前缀输入"""
        import re
        
        # 从 session['data'] 获取数据
        data = session.get('data', {})
        plan_id = data.get('plan_id')
        domain_id = data.get('domain_id')
        
        prefix = text.strip().lower()
        
        # 验证前缀格式
        if not re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', prefix):
            msg = "❌ 前缀格式不正确\n\n"
            msg += "只能包含字母、数字和连字符，不能以连字符开头或结尾\n\n"
            msg += "请重新输入："
            self.send_message(chat_id, msg)
            return True
        
        try:
            from app.models.plan import Plan
            from app.models.domain import Domain
            from app.models.subdomain import Subdomain
            
            plan = Plan.query.get(plan_id)
            domain = Domain.query.get(domain_id)
            
            if not plan or not domain:
                return True
            
            # 从套餐获取长度限制
            min_len = plan.min_length or 1
            max_len = plan.max_length or 63
            
            if len(prefix) < min_len or len(prefix) > max_len:
                msg = f"❌ 前缀长度必须在 {min_len}-{max_len} 个字符之间\n\n请重新输入："
                self.send_message(chat_id, msg)
                return True
            
            # 检查是否已存在
            full_domain = f"{prefix}.{domain.name}"
            existing = Subdomain.query.filter_by(name=prefix, domain_id=domain_id).first()
            
            if existing:
                msg = f"❌ 域名 {full_domain} 已被注册\n\n请输入其他前缀："
                self.send_message(chat_id, msg)
                return True
            
            # 保存到会话
            user = self.get_user(telegram_id)
            self.set_session_state(chat_id, 'buy_confirm', {
                'plan_id': plan_id,
                'domain_id': domain_id,
                'prefix': prefix,
                'full_domain': full_domain
            })
            
            # 显示确认
            duration = '永久' if plan.duration_days == -1 else f'{plan.duration_days}天'
            
            msg = f"🛒 订单确认\n\n"
            msg += f"域名：{full_domain}\n"
            msg += f"套餐：{plan.name}\n"
            msg += f"有效期：{duration}\n"
            msg += f"价格：¥{plan.price}\n"
            msg += f"当前余额：¥{user.balance}\n"
            
            buttons = [
                [{'text': '🎫 使用优惠券', 'callback_data': 'buy:coupon'}],
                [{'text': '✅ 确认购买', 'callback_data': 'buy:execute'}],
                [{'text': '❌ 取消', 'callback_data': 'buy:plans'}]
            ]
            keyboard = self.make_keyboard(buttons)
            self.send_message(chat_id, msg, keyboard)
            
            return True
            
        except Exception as e:
            print(f'[BuyHandler] Prefix input error: {e}')
            return True
    
    def _show_coupon_input(self, chat_id: int, message_id: int, telegram_id: int):
        """显示优惠券输入"""
        session = self.get_session_state(chat_id)
        print(f'[BuyHandler] Show coupon input, session: {session}')
        
        if not session:
            self.send_message(chat_id, "❌ 会话已过期，请重新开始购买")
            return
        
        # 保持原有数据，只改变状态
        data = session.get('data', {})
        print(f'[BuyHandler] Session data: {data}')
        
        self.set_session_state(chat_id, 'buy_coupon', data)
        
        text = "🎫 输入优惠券\n\n请输入优惠码："
        
        buttons = [[{'text': '❌ 取消', 'callback_data': 'buy:confirm'}]]
        keyboard = self.make_keyboard(buttons)
        self.edit_message(chat_id, message_id, text, keyboard)
    
    def _handle_coupon_input(self, chat_id: int, telegram_id: int, text: str, session: dict) -> bool:
        """处理优惠券输入"""
        try:
            from app.models.coupon import Coupon
            
            code = text.strip().upper()
            print(f'[BuyHandler] Coupon input: code={code}')
            
            coupon = Coupon.query.filter_by(code=code, status=1).first()
            print(f'[BuyHandler] Coupon found: {coupon}')
            
            if not coupon:
                msg = "❌ 优惠券不存在\n\n请重新输入或点击取消："
                buttons = [[{'text': '❌ 取消', 'callback_data': 'buy:confirm'}]]
                keyboard = self.make_keyboard(buttons)
                self.send_message(chat_id, msg, keyboard)
                return True
            
            if not coupon.is_valid:
                msg = "❌ 优惠券已过期或已用完\n\n请重新输入或点击取消："
                buttons = [[{'text': '❌ 取消', 'callback_data': 'buy:confirm'}]]
                keyboard = self.make_keyboard(buttons)
                self.send_message(chat_id, msg, keyboard)
                return True
            
            # 保存优惠券到 session data
            data = session.get('data', {})
            data['coupon_id'] = coupon.id
            data['coupon_code'] = code
            self.set_session_state(chat_id, 'buy_confirm', data)
            
            msg = f"✅ 优惠券已应用\n\n"
            msg += f"优惠码：{code}\n"
            if coupon.type == 'percent':
                msg += f"折扣：{coupon.value}折"
            else:
                msg += f"减免：¥{coupon.value}"
            
            buttons = [
                [{'text': '✅ 确认购买', 'callback_data': 'buy:execute'}],
                [{'text': '❌ 取消', 'callback_data': 'buy:plans'}]
            ]
            keyboard = self.make_keyboard(buttons)
            self.send_message(chat_id, msg, keyboard)
            
            return True
            
        except Exception as e:
            print(f'[BuyHandler] Coupon input error: {e}')
            import traceback
            traceback.print_exc()
            self.send_message(chat_id, f"❌ 优惠券验证失败：{str(e)}")
            return True
    
    def _show_order_confirm(self, chat_id: int, message_id: int, user, telegram_id: int):
        """显示订单确认"""
        session = self.get_session_state(chat_id)
        if not session:
            return
        
        # 从 session['data'] 获取数据，重新显示确认页面
        data = session.get('data', {})
        self._handle_prefix_input(chat_id, telegram_id, data.get('prefix', ''), session)
    
    def _execute_purchase(self, chat_id: int, message_id: int, user, telegram_id: int):
        """执行购买"""
        try:
            from app import db
            from app.models.plan import Plan
            from app.models.domain import Domain
            from app.models.subdomain import Subdomain
            from app.models.coupon import Coupon
            from datetime import datetime, timedelta
            
            session = self.get_session_state(chat_id)
            if not session:
                return
            
            # 从 session['data'] 获取数据
            data = session.get('data', {})
            plan_id = data.get('plan_id')
            domain_id = data.get('domain_id')
            prefix = data.get('prefix')
            coupon_id = data.get('coupon_id')
            
            plan = Plan.query.get(plan_id)
            domain = Domain.query.get(domain_id)
            
            if not plan or not domain:
                return
            
            # 计算价格 - 统一转为 Decimal 处理
            from decimal import Decimal
            price = Decimal(str(plan.price))
            discount = Decimal('0')
            
            if coupon_id:
                coupon = Coupon.query.get(coupon_id)
                if coupon and coupon.is_valid:
                    # 使用 Coupon 模型的 calculate_discount 方法计算折扣
                    discount = Decimal(str(coupon.calculate_discount(float(price))))
            
            final_price = max(Decimal('0'), price - discount)
            
            # 检查余额
            if user.balance < final_price:
                text = f"❌ 余额不足\n\n"
                text += f"需要支付：¥{final_price}\n"
                text += f"当前余额：¥{user.balance}"
                
                buttons = [
                    [{'text': '💳 充值', 'callback_data': 'account:recharge'}],
                    [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
                ]
                keyboard = self.make_keyboard(buttons)
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            # 扣除余额
            user.balance -= final_price
            
            # 创建域名
            expires_at = None
            if plan.duration_days > 0:
                expires_at = datetime.now() + timedelta(days=plan.duration_days)
            
            full_domain = f"{prefix}.{domain.name}"
            subdomain = Subdomain(
                name=prefix,
                full_name=full_domain,
                domain_id=domain_id,
                user_id=user.id,
                plan_id=plan_id,
                expires_at=expires_at
            )
            db.session.add(subdomain)
            
            # 使用优惠券
            if coupon_id:
                coupon = Coupon.query.get(coupon_id)
                if coupon:
                    coupon.used_count += 1
            
            db.session.commit()
            
            # 清除会话
            self.clear_session_state(chat_id)
            
            duration = '永久' if plan.duration_days == -1 else f'{plan.duration_days}天'
            
            text = f"✅ 购买成功！\n\n"
            text += f"域名：{full_domain}\n"
            text += f"套餐：{plan.name}\n"
            text += f"有效期：{duration}\n"
            text += f"支付金额：¥{final_price}\n"
            text += f"剩余余额：¥{user.balance}"
            
            buttons = [
                [{'text': '🌐 查看域名', 'callback_data': f'domain:{subdomain.id}'}],
                [{'text': '📝 添加 DNS', 'callback_data': f'dns:list:{subdomain.id}'}],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ]
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[BuyHandler] Execute error: {e}')
            self.edit_message(chat_id, message_id, f'❌ 购买失败：{str(e)}')
    
    def _check_availability(self, chat_id: int, message_id: int, user, telegram_id: int):
        """检查域名可用性"""
        # 在 _handle_prefix_input 中已实现
        pass
