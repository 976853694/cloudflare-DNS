"""
帮助处理器

处理帮助菜单和帮助内容显示
"""

from .base import BaseHandler


class HelpHandler(BaseHandler):
    """帮助处理器"""
    
    # 帮助主题
    HELP_TOPICS = {
        'quickstart': {
            'title': '🚀 快速入门',
            'content': '''欢迎使用域名管理机器人！

1️⃣ 绑定账号
发送 /bind 绑定码 绑定您的账号

2️⃣ 购买域名
点击「购买套餐」选择套餐和后缀

3️⃣ 管理域名
点击「我的域名」查看和管理域名

4️⃣ 添加 DNS
在域名详情中添加 DNS 记录

5️⃣ 充值余额
点击「充值卡密」使用卡密充值'''
        },
        'bind': {
            'title': '🔗 绑定账号',
            'content': '''如何绑定账号：

1. 登录网站「安全设置」页面
2. 点击「绑定 Telegram」获取绑定码
3. 私聊机器人发送：/bind 绑定码
4. 绑定成功后即可使用所有功能

注意事项：
• 绑定码有效期 5 分钟
• 一个 Telegram 账号只能绑定一个网站账号
• 如需更换绑定，请先解绑'''
        },
        'buy': {
            'title': '🛒 购买域名',
            'content': '''如何购买域名：

1. 点击「购买套餐」
2. 选择套餐
3. 选择域名后缀
4. 输入域名前缀
5. 确认订单并支付

支付方式：
• 使用账户余额支付
• 可使用优惠券抵扣

域名规则：
• 前缀只能包含字母、数字、连字符
• 长度 1-63 个字符
• 不能以连字符开头或结尾'''
        },
        'dns': {
            'title': '📝 添加 DNS',
            'content': '''如何添加 DNS 记录：

1. 进入域名详情
2. 点击「DNS 记录」
3. 点击「添加记录」
4. 选择记录类型
5. 输入记录名称和值

支持的记录类型：
• A - IPv4 地址
• AAAA - IPv6 地址
• CNAME - 别名记录
• TXT - 文本记录
• MX - 邮件记录
• NS - 域名服务器
• SRV - 服务记录
• CAA - 证书授权

Cloudflare 代理：
• A/AAAA/CNAME 记录可开启代理
• 代理可隐藏真实 IP 并提供 CDN 加速'''
        },
        'recharge': {
            'title': '💳 充值余额',
            'content': '''如何充值余额：

1. 点击「充值卡密」
2. 输入充值卡密
3. 充值成功

获取卡密：
• 联系管理员购买
• 通过官方渠道获取

注意事项：
• 卡密只能使用一次
• 充值后余额立即到账'''
        },
        'faq': {
            'title': '❓ 常见问题',
            'content': '''常见问题解答：

Q: 如何解绑账号？
A: 在设置中点击「解绑」按钮

Q: 域名购买后多久生效？
A: 购买成功后立即生效

Q: DNS 记录修改后多久生效？
A: 通常几分钟内生效，最长 24 小时

Q: 如何开启自动续费？
A: 在域名设置中开启自动续费

Q: 余额不足怎么办？
A: 使用卡密充值或联系管理员

Q: 如何联系客服？
A: 请通过官网联系方式联系'''
        }
    }
    
    def handle_help(self, chat_id: int, telegram_id: int, user_info: dict):
        """
        处理 /help 命令
        
        Args:
            chat_id: 聊天 ID
            telegram_id: Telegram 用户 ID
            user_info: Telegram 用户信息
        """
        self._show_help_menu(chat_id, telegram_id)
    
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
        action = data.replace('help:', '')
        
        if action == 'main':
            self._show_help_menu(chat_id, telegram_id, message_id)
        elif action in self.HELP_TOPICS:
            self._show_help_topic(chat_id, telegram_id, action, message_id)
        else:
            self._show_help_menu(chat_id, telegram_id, message_id)
    
    def _show_help_menu(self, chat_id: int, telegram_id: int, message_id: int = None):
        """显示帮助菜单"""
        text = "❓ 帮助中心\n\n请选择帮助主题："
        
        buttons = [
            [{'text': '🚀 快速入门', 'callback_data': 'help:quickstart'}],
            [
                {'text': '🔗 绑定账号', 'callback_data': 'help:bind'},
                {'text': '🛒 购买域名', 'callback_data': 'help:buy'}
            ],
            [
                {'text': '📝 添加 DNS', 'callback_data': 'help:dns'},
                {'text': '💳 充值余额', 'callback_data': 'help:recharge'}
            ],
            [
                {'text': '❓ 常见问题', 'callback_data': 'help:faq'}
            ],
            [{'text': '🏠 返回主菜单', 'callback_data': 'menu:main'}]
        ]
        
        keyboard = self.make_keyboard(buttons)
        
        if message_id:
            self.edit_message(chat_id, message_id, text, keyboard)
        else:
            self.send_message(chat_id, text, keyboard)
    
    def _show_help_topic(self, chat_id: int, telegram_id: int, topic: str, message_id: int = None):
        """显示帮助主题内容"""
        topic_data = self.HELP_TOPICS.get(topic, self.HELP_TOPICS['quickstart'])
        
        text = f"{topic_data['title']}\n\n{topic_data['content']}"
        
        buttons = [
            [{'text': '◀️ 返回帮助', 'callback_data': 'help:main'}],
            [{'text': '🏠 返回主菜单', 'callback_data': 'menu:main'}]
        ]
        
        keyboard = self.make_keyboard(buttons)
        
        if message_id:
            self.edit_message(chat_id, message_id, text, keyboard)
        else:
            self.send_message(chat_id, text, keyboard)
