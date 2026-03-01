"""
通知发送器

提供各类通知发送功能：
- 域名到期提醒
- 购买成功通知
- 余额变动通知
- 托管商订单通知
- 管理员通知
- 群发通知
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
import asyncio


class NotificationSender:
    """通知发送器"""
    
    def __init__(self, bot=None):
        """
        初始化通知发送器
        
        Args:
            bot: Telegram Bot 实例
        """
        self.bot = bot
        self._keyboards = None
    
    @property
    def keyboards(self):
        """获取键盘构建器"""
        if self._keyboards is None:
            from ..keyboards.builder import KeyboardBuilder
            self._keyboards = KeyboardBuilder()
        return self._keyboards
    
    async def send_message(self, chat_id: int, text: str, 
                          reply_markup: Dict = None) -> bool:
        """
        发送消息
        
        Args:
            chat_id: 聊天 ID
            text: 消息文本
            reply_markup: 键盘标记
            
        Returns:
            是否发送成功
        """
        if not self.bot:
            print('[NotificationSender] Bot not initialized')
            return False
        
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            return True
        except Exception as e:
            print(f'[NotificationSender] Send message error: {e}')
            return False
    
    def _check_notification_enabled(self, user, notification_type: str) -> bool:
        """
        检查用户是否启用了指定类型的通知
        
        Args:
            user: 用户对象
            notification_type: 通知类型
            
        Returns:
            是否启用
        """
        if not user:
            return False
        
        # 获取用户通知设置
        settings = getattr(user, 'tg_notification_settings', None)
        if not settings:
            return True  # 默认启用
        
        if isinstance(settings, str):
            import json
            try:
                settings = json.loads(settings)
            except:
                return True
        
        return settings.get(notification_type, True)
    
    # ==================== 域名到期通知 ====================
    
    async def send_domain_expiry_reminder(self, user, domain, days_left: int) -> bool:
        """
        发送域名到期提醒
        
        Args:
            user: 用户对象
            domain: 域名对象
            days_left: 剩余天数
            
        Returns:
            是否发送成功
        """
        if not self._check_notification_enabled(user, 'expiry_reminder'):
            return False
        
        tg_chat_id = getattr(user, 'telegram_chat_id', None)
        if not tg_chat_id:
            return False
        
        domain_name = getattr(domain, 'full_domain', str(domain))
        domain_id = getattr(domain, 'id', 0)
        expire_date = getattr(domain, 'expire_time', None)
        expire_str = expire_date.strftime('%Y-%m-%d') if expire_date else '未知'
        
        if days_left <= 0:
            text = f"⚠️ <b>域名已过期</b>\n\n"
            text += f"域名：{domain_name}\n"
            text += f"到期时间：{expire_str}\n\n"
            text += "请尽快续费以避免域名被删除！"
        elif days_left == 1:
            text = f"🔴 <b>域名明天到期</b>\n\n"
            text += f"域名：{domain_name}\n"
            text += f"到期时间：{expire_str}\n\n"
            text += "请尽快续费！"
        elif days_left <= 3:
            text = f"🟠 <b>域名即将到期</b>\n\n"
            text += f"域名：{domain_name}\n"
            text += f"到期时间：{expire_str}\n"
            text += f"剩余：{days_left} 天\n\n"
            text += "建议尽快续费"
        else:
            text = f"🟡 <b>域名到期提醒</b>\n\n"
            text += f"域名：{domain_name}\n"
            text += f"到期时间：{expire_str}\n"
            text += f"剩余：{days_left} 天"
        
        buttons = [
            [self.keyboards.button('🔄 立即续费', f'domain:{domain_id}:renew')],
            [self.keyboards.button('📋 查看详情', f'domain:{domain_id}')]
        ]
        keyboard = self.keyboards.make_keyboard(buttons)
        
        return await self.send_message(tg_chat_id, text, keyboard)
    
    # ==================== 购买成功通知 ====================
    
    async def send_purchase_success(self, user, domain, order=None) -> bool:
        """
        发送购买成功通知
        
        Args:
            user: 用户对象
            domain: 域名对象
            order: 订单对象（可选）
            
        Returns:
            是否发送成功
        """
        if not self._check_notification_enabled(user, 'purchase_notify'):
            return False
        
        tg_chat_id = getattr(user, 'telegram_chat_id', None)
        if not tg_chat_id:
            return False
        
        domain_name = getattr(domain, 'full_domain', str(domain))
        domain_id = getattr(domain, 'id', 0)
        
        text = f"✅ <b>域名购买成功</b>\n\n"
        text += f"域名：{domain_name}\n"
        
        if order:
            amount = getattr(order, 'amount', Decimal('0'))
            text += f"支付金额：¥{amount:.2f}\n"
        
        expire_date = getattr(domain, 'expire_time', None)
        if expire_date:
            text += f"到期时间：{expire_date.strftime('%Y-%m-%d')}\n"
        
        text += "\n您可以开始添加 DNS 记录了！"
        
        buttons = [
            [
                self.keyboards.button('📋 查看域名', f'domain:{domain_id}'),
                self.keyboards.button('➕ 添加记录', f'dns:add:{domain_id}')
            ],
            [self.keyboards.button('🏠 主菜单', 'menu:main')]
        ]
        keyboard = self.keyboards.make_keyboard(buttons)
        
        return await self.send_message(tg_chat_id, text, keyboard)
    
    # ==================== 自动续费通知 ====================
    
    async def send_auto_renew_success(self, user, domain, amount: Decimal) -> bool:
        """
        发送自动续费成功通知
        
        Args:
            user: 用户对象
            domain: 域名对象
            amount: 续费金额
            
        Returns:
            是否发送成功
        """
        if not self._check_notification_enabled(user, 'expiry_reminder'):
            return False
        
        tg_chat_id = getattr(user, 'telegram_chat_id', None)
        if not tg_chat_id:
            return False
        
        domain_name = getattr(domain, 'full_domain', str(domain))
        domain_id = getattr(domain, 'id', 0)
        expire_date = getattr(domain, 'expire_time', None)
        expire_str = expire_date.strftime('%Y-%m-%d') if expire_date else '未知'
        
        text = f"✅ <b>自动续费成功</b>\n\n"
        text += f"域名：{domain_name}\n"
        text += f"续费金额：¥{amount:.2f}\n"
        text += f"新到期时间：{expire_str}"
        
        buttons = [
            [self.keyboards.button('📋 查看域名', f'domain:{domain_id}')],
            [self.keyboards.button('🏠 主菜单', 'menu:main')]
        ]
        keyboard = self.keyboards.make_keyboard(buttons)
        
        return await self.send_message(tg_chat_id, text, keyboard)
    
    async def send_auto_renew_failed(self, user, domain, reason: str) -> bool:
        """
        发送自动续费失败通知
        
        Args:
            user: 用户对象
            domain: 域名对象
            reason: 失败原因
            
        Returns:
            是否发送成功
        """
        if not self._check_notification_enabled(user, 'expiry_reminder'):
            return False
        
        tg_chat_id = getattr(user, 'telegram_chat_id', None)
        if not tg_chat_id:
            return False
        
        domain_name = getattr(domain, 'full_domain', str(domain))
        domain_id = getattr(domain, 'id', 0)
        
        text = f"❌ <b>自动续费失败</b>\n\n"
        text += f"域名：{domain_name}\n"
        text += f"原因：{reason}\n\n"
        text += "请手动续费以避免域名过期"
        
        buttons = [
            [self.keyboards.button('🔄 手动续费', f'domain:{domain_id}:renew')],
            [self.keyboards.button('💰 去充值', 'menu:account')]
        ]
        keyboard = self.keyboards.make_keyboard(buttons)
        
        return await self.send_message(tg_chat_id, text, keyboard)
    
    # ==================== 余额充值通知 ====================
    
    async def send_recharge_success(self, user, amount: Decimal, 
                                    new_balance: Decimal) -> bool:
        """
        发送充值成功通知
        
        Args:
            user: 用户对象
            amount: 充值金额
            new_balance: 新余额
            
        Returns:
            是否发送成功
        """
        if not self._check_notification_enabled(user, 'recharge_notify'):
            return False
        
        tg_chat_id = getattr(user, 'telegram_chat_id', None)
        if not tg_chat_id:
            return False
        
        text = f"✅ <b>充值成功</b>\n\n"
        text += f"充值金额：¥{amount:.2f}\n"
        text += f"当前余额：¥{new_balance:.2f}"
        
        buttons = [
            [self.keyboards.button('💰 查看账户', 'menu:account')],
            [self.keyboards.button('🛒 购买域名', 'menu:buy')]
        ]
        keyboard = self.keyboards.make_keyboard(buttons)
        
        return await self.send_message(tg_chat_id, text, keyboard)
    
    # ==================== 公告发布通知 ====================
    
    async def send_announcement_notification(self, user, announcement) -> bool:
        """
        发送公告发布通知
        
        Args:
            user: 用户对象
            announcement: 公告对象
            
        Returns:
            是否发送成功
        """
        if not self._check_notification_enabled(user, 'announcement_notify'):
            return False
        
        tg_chat_id = getattr(user, 'telegram_chat_id', None)
        if not tg_chat_id:
            return False
        
        ann_id = getattr(announcement, 'id', 0)
        title = getattr(announcement, 'title', '新公告')
        content = getattr(announcement, 'content', '')
        
        # 截取内容预览
        preview = content[:200] + '...' if len(content) > 200 else content
        
        text = f"📢 <b>新公告</b>\n\n"
        text += f"<b>{title}</b>\n\n"
        text += preview
        
        buttons = [
            [self.keyboards.button('📖 查看详情', f'announcement:{ann_id}')],
            [self.keyboards.button('🏠 主菜单', 'menu:main')]
        ]
        keyboard = self.keyboards.make_keyboard(buttons)
        
        return await self.send_message(tg_chat_id, text, keyboard)
    
    # ==================== 托管商订单通知 ====================
    
    async def send_host_order_notification(self, host_user, order, 
                                           commission: Decimal) -> bool:
        """
        发送托管商订单通知
        
        Args:
            host_user: 托管商用户对象
            order: 订单对象
            commission: 佣金金额
            
        Returns:
            是否发送成功
        """
        if not self._check_notification_enabled(host_user, 'host_order_notify'):
            return False
        
        tg_chat_id = getattr(host_user, 'telegram_chat_id', None)
        if not tg_chat_id:
            return False
        
        domain_name = getattr(order, 'domain_name', '未知')
        amount = getattr(order, 'amount', Decimal('0'))
        
        text = f"💰 <b>新订单收益</b>\n\n"
        text += f"域名：{domain_name}\n"
        text += f"订单金额：¥{amount:.2f}\n"
        text += f"您的佣金：¥{commission:.2f}"
        
        buttons = [
            [self.keyboards.button('📜 查看记录', 'hc:orders')],
            [self.keyboards.button('🏢 托管中心', 'menu:host_center')]
        ]
        keyboard = self.keyboards.make_keyboard(buttons)
        
        return await self.send_message(tg_chat_id, text, keyboard)
    
    # ==================== 托管商每日收益汇总 ====================
    
    async def send_host_daily_summary(self, host_user, order_count: int,
                                      total_commission: Decimal) -> bool:
        """
        发送托管商每日收益汇总
        
        Args:
            host_user: 托管商用户对象
            order_count: 订单数量
            total_commission: 总佣金
            
        Returns:
            是否发送成功
        """
        if not self._check_notification_enabled(host_user, 'host_daily_summary'):
            return False
        
        tg_chat_id = getattr(host_user, 'telegram_chat_id', None)
        if not tg_chat_id:
            return False
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        text = f"📊 <b>每日收益汇总</b>\n\n"
        text += f"日期：{today}\n"
        text += f"订单数：{order_count} 笔\n"
        text += f"总收益：¥{total_commission:.2f}"
        
        if order_count == 0:
            text += "\n\n今日暂无订单，继续加油！"
        
        buttons = [
            [self.keyboards.button('📊 详细统计', 'hc:stats')],
            [self.keyboards.button('🏢 托管中心', 'menu:host_center')]
        ]
        keyboard = self.keyboards.make_keyboard(buttons)
        
        return await self.send_message(tg_chat_id, text, keyboard)
    
    # ==================== 管理员通知 ====================
    
    async def send_admin_new_user(self, admin_user, new_user) -> bool:
        """
        发送新用户注册通知给管理员
        
        Args:
            admin_user: 管理员用户对象
            new_user: 新注册用户对象
            
        Returns:
            是否发送成功
        """
        if not self._check_notification_enabled(admin_user, 'admin_new_user'):
            return False
        
        tg_chat_id = getattr(admin_user, 'telegram_chat_id', None)
        if not tg_chat_id:
            return False
        
        username = getattr(new_user, 'username', '未知')
        email = getattr(new_user, 'email', '未知')
        user_id = getattr(new_user, 'id', 0)
        
        text = f"👤 <b>新用户注册</b>\n\n"
        text += f"用户名：{username}\n"
        text += f"邮箱：{email}\n"
        text += f"注册时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        buttons = [
            [self.keyboards.button('👤 查看用户', f'admin:user:{user_id}')],
            [self.keyboards.button('⚙️ 管理后台', 'menu:admin')]
        ]
        keyboard = self.keyboards.make_keyboard(buttons)
        
        return await self.send_message(tg_chat_id, text, keyboard)
    
    async def send_admin_large_order(self, admin_user, order, 
                                     threshold: Decimal) -> bool:
        """
        发送大额订单通知给管理员
        
        Args:
            admin_user: 管理员用户对象
            order: 订单对象
            threshold: 阈值金额
            
        Returns:
            是否发送成功
        """
        if not self._check_notification_enabled(admin_user, 'admin_large_order'):
            return False
        
        tg_chat_id = getattr(admin_user, 'telegram_chat_id', None)
        if not tg_chat_id:
            return False
        
        amount = getattr(order, 'amount', Decimal('0'))
        domain_name = getattr(order, 'domain_name', '未知')
        
        text = f"💰 <b>大额订单提醒</b>\n\n"
        text += f"订单金额：¥{amount:.2f}\n"
        text += f"域名：{domain_name}\n"
        text += f"阈值：¥{threshold:.2f}"
        
        buttons = [
            [self.keyboards.button('📊 查看统计', 'admin:stats')],
            [self.keyboards.button('⚙️ 管理后台', 'menu:admin')]
        ]
        keyboard = self.keyboards.make_keyboard(buttons)
        
        return await self.send_message(tg_chat_id, text, keyboard)
    
    async def send_admin_new_host_application(self, admin_user, 
                                              application) -> bool:
        """
        发送新托管商申请通知给管理员
        
        Args:
            admin_user: 管理员用户对象
            application: 申请对象
            
        Returns:
            是否发送成功
        """
        if not self._check_notification_enabled(admin_user, 'admin_host_application'):
            return False
        
        tg_chat_id = getattr(admin_user, 'telegram_chat_id', None)
        if not tg_chat_id:
            return False
        
        app_id = getattr(application, 'id', 0)
        
        # 获取申请人信息
        from app.models.user import User
        applicant = User.query.get(application.user_id)
        username = applicant.username if applicant else '未知'
        
        text = f"📝 <b>新托管商申请</b>\n\n"
        text += f"申请人：{username}\n"
        text += f"申请时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        buttons = [
            [self.keyboards.button('📝 查看申请', f'admin:app:{app_id}')],
            [self.keyboards.button('📋 申请列表', 'admin:applications')]
        ]
        keyboard = self.keyboards.make_keyboard(buttons)
        
        return await self.send_message(tg_chat_id, text, keyboard)
    
    async def send_admin_daily_report(self, admin_user, stats: Dict) -> bool:
        """
        发送管理员每日统计报表
        
        Args:
            admin_user: 管理员用户对象
            stats: 统计数据字典
            
        Returns:
            是否发送成功
        """
        if not self._check_notification_enabled(admin_user, 'admin_daily_report'):
            return False
        
        tg_chat_id = getattr(admin_user, 'telegram_chat_id', None)
        if not tg_chat_id:
            return False
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        text = f"📊 <b>每日统计报表</b>\n\n"
        text += f"日期：{today}\n\n"
        text += f"新用户：{stats.get('new_users', 0)}\n"
        text += f"新订单：{stats.get('new_orders', 0)}\n"
        text += f"收入：¥{stats.get('income', Decimal('0')):.2f}\n"
        text += f"新域名：{stats.get('new_domains', 0)}"
        
        buttons = [
            [self.keyboards.button('📊 详细统计', 'admin:stats')],
            [self.keyboards.button('⚙️ 管理后台', 'menu:admin')]
        ]
        keyboard = self.keyboards.make_keyboard(buttons)
        
        return await self.send_message(tg_chat_id, text, keyboard)
    
    # ==================== 群发通知 ====================
    
    async def broadcast_message(self, message: str, 
                               user_filter: Dict = None) -> Dict:
        """
        群发消息
        
        Args:
            message: 消息内容
            user_filter: 用户筛选条件
            
        Returns:
            发送结果统计
        """
        from app.models.user import User
        
        query = User.query.filter(User.telegram_chat_id.isnot(None))
        
        if user_filter:
            if user_filter.get('is_host'):
                query = query.filter(User.is_host == True)
            if user_filter.get('is_admin'):
                query = query.filter(User.is_admin == True)
        
        users = query.all()
        
        success_count = 0
        fail_count = 0
        
        for user in users:
            tg_chat_id = user.telegram_chat_id
            if tg_chat_id:
                try:
                    result = await self.send_message(tg_chat_id, message)
                    if result:
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    print(f'[NotificationSender] Broadcast error for {tg_chat_id}: {e}')
                    fail_count += 1
                
                # 避免发送过快
                await asyncio.sleep(0.1)
        
        return {
            'total': len(users),
            'success': success_count,
            'failed': fail_count
        }
    
    # ==================== 批量发送到期提醒 ====================
    
    async def send_batch_expiry_reminders(self, days_list: List[int] = None):
        """
        批量发送到期提醒
        
        Args:
            days_list: 提醒天数列表，默认 [7, 3, 1]
        """
        if days_list is None:
            days_list = [7, 3, 1]
        
        from app.models.subdomain import Subdomain
        from app.models.user import User
        
        now = datetime.now()
        
        for days in days_list:
            target_date = now + timedelta(days=days)
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # 查询即将到期的域名
            domains = Subdomain.query.filter(
                Subdomain.expire_time >= start_of_day,
                Subdomain.expire_time <= end_of_day,
                Subdomain.status == 1
            ).all()
            
            for domain in domains:
                user = User.query.get(domain.user_id)
                if user:
                    await self.send_domain_expiry_reminder(user, domain, days)
                    await asyncio.sleep(0.1)
        
        # 发送已过期提醒
        expired_domains = Subdomain.query.filter(
            Subdomain.expire_time < now,
            Subdomain.status == 1
        ).all()
        
        for domain in expired_domains:
            user = User.query.get(domain.user_id)
            if user:
                await self.send_domain_expiry_reminder(user, domain, 0)
                await asyncio.sleep(0.1)
    
    # ==================== 域名转移通知 ====================
    
    async def send_transfer_initiated(self, to_user, from_username: str, 
                                      domain_name: str) -> bool:
        """
        发送转移发起通知给接收方
        
        Args:
            to_user: 接收方用户对象
            from_username: 发起方用户名
            domain_name: 域名名称
            
        Returns:
            是否发送成功
        """
        if not self._check_notification_enabled(to_user, 'transfer_notify'):
            return False
        
        tg_chat_id = getattr(to_user, 'telegram_chat_id', None)
        if not tg_chat_id:
            return False
        
        text = f"📬 <b>域名转移通知</b>\n\n"
        text += f"用户 {from_username} 向您发起了域名转移\n\n"
        text += f"域名：{domain_name}\n\n"
        text += "请登录网站确认接收"
        
        buttons = [
            [self.keyboards.button('📋 查看转移', 'transfer:list')],
            [self.keyboards.button('🏠 主菜单', 'menu:main')]
        ]
        keyboard = self.keyboards.make_keyboard(buttons)
        
        return await self.send_message(tg_chat_id, text, keyboard)
    
    async def send_transfer_completed(self, user, domain_name: str, 
                                      is_sender: bool, other_username: str) -> bool:
        """
        发送转移完成通知
        
        Args:
            user: 用户对象
            domain_name: 域名名称
            is_sender: 是否为发起方
            other_username: 对方用户名
            
        Returns:
            是否发送成功
        """
        if not self._check_notification_enabled(user, 'transfer_notify'):
            return False
        
        tg_chat_id = getattr(user, 'telegram_chat_id', None)
        if not tg_chat_id:
            return False
        
        if is_sender:
            direction = "转出给"
        else:
            direction = "转入自"
        
        text = f"✅ <b>域名转移完成</b>\n\n"
        text += f"域名：{domain_name}\n"
        text += f"{direction}：{other_username}"
        
        buttons = [
            [self.keyboards.button('📋 我的域名', 'domain:list')],
            [self.keyboards.button('🏠 主菜单', 'menu:main')]
        ]
        keyboard = self.keyboards.make_keyboard(buttons)
        
        return await self.send_message(tg_chat_id, text, keyboard)
    
    async def send_transfer_cancelled(self, to_user, from_username: str, 
                                      domain_name: str) -> bool:
        """
        发送转移取消通知给接收方
        
        Args:
            to_user: 接收方用户对象
            from_username: 发起方用户名
            domain_name: 域名名称
            
        Returns:
            是否发送成功
        """
        if not self._check_notification_enabled(to_user, 'transfer_notify'):
            return False
        
        tg_chat_id = getattr(to_user, 'telegram_chat_id', None)
        if not tg_chat_id:
            return False
        
        text = f"❌ <b>域名转移已取消</b>\n\n"
        text += f"域名：{domain_name}\n"
        text += f"发起用户：{from_username}"
        
        buttons = [
            [self.keyboards.button('🏠 主菜单', 'menu:main')]
        ]
        keyboard = self.keyboards.make_keyboard(buttons)
        
        return await self.send_message(tg_chat_id, text, keyboard)
    
    # ==================== 工单通知 ====================
    
    async def send_ticket_reply(self, user, ticket_id: int, 
                                ticket_subject: str, reply_content: str) -> bool:
        """
        发送工单回复通知
        
        Args:
            user: 用户对象
            ticket_id: 工单 ID
            ticket_subject: 工单主题
            reply_content: 回复内容
            
        Returns:
            是否发送成功
        """
        if not self._check_notification_enabled(user, 'ticket_notify'):
            return False
        
        tg_chat_id = getattr(user, 'telegram_chat_id', None)
        if not tg_chat_id:
            return False
        
        # 截取回复内容预览
        preview = reply_content[:200] + '...' if len(reply_content) > 200 else reply_content
        
        text = f"💬 <b>工单有新回复</b>\n\n"
        text += f"工单号：#{ticket_id}\n"
        text += f"主题：{ticket_subject}\n\n"
        text += f"回复内容：\n{preview}"
        
        buttons = [
            [self.keyboards.button('📋 查看工单', f'ticket:detail:{ticket_id}')],
            [self.keyboards.button('🏠 主菜单', 'menu:main')]
        ]
        keyboard = self.keyboards.make_keyboard(buttons)
        
        return await self.send_message(tg_chat_id, text, keyboard)
    
    async def send_ticket_status_change(self, user, ticket_id: int,
                                        ticket_subject: str, new_status: str) -> bool:
        """
        发送工单状态变更通知
        
        Args:
            user: 用户对象
            ticket_id: 工单 ID
            ticket_subject: 工单主题
            new_status: 新状态
            
        Returns:
            是否发送成功
        """
        if not self._check_notification_enabled(user, 'ticket_notify'):
            return False
        
        tg_chat_id = getattr(user, 'telegram_chat_id', None)
        if not tg_chat_id:
            return False
        
        status_map = {
            'pending': '⏳ 待处理',
            'processing': '🔄 处理中',
            'replied': '💬 已回复',
            'closed': '🔒 已关闭'
        }
        status_text = status_map.get(new_status, new_status)
        
        text = f"📋 <b>工单状态更新</b>\n\n"
        text += f"工单号：#{ticket_id}\n"
        text += f"主题：{ticket_subject}\n"
        text += f"新状态：{status_text}"
        
        buttons = [
            [self.keyboards.button('📋 查看工单', f'ticket:detail:{ticket_id}')],
            [self.keyboards.button('🏠 主菜单', 'menu:main')]
        ]
        keyboard = self.keyboards.make_keyboard(buttons)
        
        return await self.send_message(tg_chat_id, text, keyboard)
    
    # ==================== 积分变动通知 ====================
    
    async def send_points_change(self, user, points: int, 
                                 reason: str, balance: int) -> bool:
        """
        发送积分变动通知
        
        Args:
            user: 用户对象
            points: 变动积分（正数为增加，负数为减少）
            reason: 变动原因
            balance: 当前余额
            
        Returns:
            是否发送成功
        """
        if not self._check_notification_enabled(user, 'points_notify'):
            return False
        
        tg_chat_id = getattr(user, 'telegram_chat_id', None)
        if not tg_chat_id:
            return False
        
        if points > 0:
            emoji = "➕"
            action = "获得"
        else:
            emoji = "➖"
            action = "消耗"
        
        text = f"{emoji} <b>积分变动</b>\n\n"
        text += f"{action}：{abs(points)} 积分\n"
        text += f"原因：{reason}\n"
        text += f"当前余额：{balance} 积分"
        
        buttons = [
            [self.keyboards.button('💰 积分中心', 'points:menu')],
            [self.keyboards.button('🏠 主菜单', 'menu:main')]
        ]
        keyboard = self.keyboards.make_keyboard(buttons)
        
        return await self.send_message(tg_chat_id, text, keyboard)
