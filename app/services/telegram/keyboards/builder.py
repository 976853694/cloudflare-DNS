"""
键盘构建器

提供各种 Inline Keyboard 的构建方法
"""

from typing import List, Optional, Dict, Any, Tuple
import json


class KeyboardBuilder:
    """Inline Keyboard 构建器"""
    
    # 每页显示数量
    PAGE_SIZE = 5
    
    # 全局广告按钮配置（类变量，由外部设置）
    _ad_buttons: List[Tuple[str, str]] = []
    
    def __init__(self, messages=None):
        """
        初始化键盘构建器
        
        Args:
            messages: MessageManager 实例，用于获取按钮文本
        """
        self.messages = messages
    
    @classmethod
    def set_ad_buttons(cls, ad_buttons: List[Tuple[str, str]]):
        """
        设置全局广告按钮列表
        
        Args:
            ad_buttons: [(文字, 链接), ...] 列表
        """
        cls._ad_buttons = ad_buttons or []
    
    @classmethod
    def get_ad_button_rows(cls) -> List[List[Dict[str, str]]]:
        """
        获取广告按钮行列表（自适应排版）
        - 短文字按钮（<=10字符）2个一行
        - 长文字按钮单独一行
        
        Returns:
            按钮行列表
        """
        if not cls._ad_buttons:
            return []
        
        rows = []
        short_buttons = []  # 暂存短按钮
        
        for text, url in cls._ad_buttons:
            if not text or not url:
                continue
            
            button = {'text': f'📢 {text}', 'url': url}
            
            # 判断文字长度（不含emoji）
            if len(text) <= 10:
                short_buttons.append(button)
                # 凑够2个短按钮就输出一行
                if len(short_buttons) == 2:
                    rows.append(short_buttons)
                    short_buttons = []
            else:
                # 长按钮前先输出已有的短按钮
                if short_buttons:
                    rows.append(short_buttons)
                    short_buttons = []
                # 长按钮单独一行
                rows.append([button])
        
        # 处理剩余的短按钮
        if short_buttons:
            rows.append(short_buttons)
        
        return rows
    
    def _get_text(self, key: str, lang: str = None, **kwargs) -> str:
        """获取按钮文本"""
        if self.messages:
            return self.messages.get(key, lang=lang, **kwargs)
        return key
    
    @staticmethod
    def make_keyboard(buttons: List[List[Dict[str, str]]], include_ad: bool = True) -> Dict[str, Any]:
        """
        创建内联键盘
        
        Args:
            buttons: 按钮数组，格式为 [[{'text': '按钮文字', 'callback_data': '回调数据'}], ...]
            include_ad: 是否包含广告按钮
            
        Returns:
            Telegram InlineKeyboardMarkup 格式的字典
        """
        # 添加广告按钮（如果有配置）
        if include_ad:
            ad_rows = KeyboardBuilder.get_ad_button_rows()
            if ad_rows:
                buttons = buttons + ad_rows
        
        return {'inline_keyboard': buttons}
    
    @staticmethod
    def button(text: str, callback_data: str = None, url: str = None) -> Dict[str, str]:
        """
        创建单个按钮
        
        Args:
            text: 按钮文字
            callback_data: 回调数据
            url: 链接地址（与 callback_data 二选一）
            
        Returns:
            按钮字典
        """
        btn = {'text': text}
        if url:
            btn['url'] = url
        elif callback_data:
            btn['callback_data'] = callback_data
        return btn
    
    def main_menu(self, user, lang: str = None) -> Dict[str, Any]:
        """
        构建主菜单键盘
        
        Args:
            user: 用户对象
            lang: 语言代码
            
        Returns:
            InlineKeyboardMarkup
        """
        buttons = [
            [
                self.button('📋 我的域名', 'menu:domains'),
                self.button('🛒 购买域名', 'menu:buy')
            ],
            [
                self.button('💰 我的账户', 'menu:account')
            ],
            [
                self.button('📢 系统公告', 'menu:announcements')
            ]
        ]
        
        # 托管商按钮
        if hasattr(user, 'is_host') and user.is_host:
            buttons.append([
                self.button('🏢 托管商中心', 'menu:host_center')
            ])
        
        # 管理员按钮
        if hasattr(user, 'is_admin') and user.is_admin:
            buttons.append([
                self.button('⚙️ 管理后台', 'menu:admin')
            ])
        
        # 底部按钮
        buttons.append([
            self.button('⚙️ 设置', 'menu:settings'),
            self.button('❓ 帮助', 'menu:help'),
            self.button('🔓 解绑', 'unbind')
        ])
        
        return self.make_keyboard(buttons)
    
    def unbound_menu(self, bot_username: str = None) -> Dict[str, Any]:
        """
        构建未绑定用户菜单
        
        Args:
            bot_username: 机器人用户名，用于生成私聊链接
            
        Returns:
            InlineKeyboardMarkup
        """
        buttons = [
            [self.button('❓ 帮助', 'menu:help')]
        ]
        return self.make_keyboard(buttons)
    
    def private_chat_prompt(self, bot_username: str) -> Dict[str, Any]:
        """
        构建私聊提示键盘
        
        Args:
            bot_username: 机器人用户名
            
        Returns:
            InlineKeyboardMarkup
        """
        url = f'https://t.me/{bot_username}'
        buttons = [
            [self.button('💬 私聊机器人', url=url)]
        ]
        return self.make_keyboard(buttons)
    
    def bind_prompt(self) -> Dict[str, Any]:
        """构建绑定提示键盘"""
        buttons = [
            [self.button('❓ 帮助', 'menu:help')]
        ]
        return self.make_keyboard(buttons)
    
    def confirm_cancel(self, confirm_callback: str, cancel_callback: str = 'cancel') -> Dict[str, Any]:
        """
        构建确认/取消键盘
        
        Args:
            confirm_callback: 确认按钮的回调数据
            cancel_callback: 取消按钮的回调数据
            
        Returns:
            InlineKeyboardMarkup
        """
        buttons = [
            [
                self.button('✅ 确认', confirm_callback),
                self.button('❌ 取消', cancel_callback)
            ]
        ]
        return self.make_keyboard(buttons)
    
    def back_to_menu(self) -> Dict[str, Any]:
        """构建返回主菜单键盘"""
        buttons = [
            [self.button('🏠 返回主菜单', 'menu:main')]
        ]
        return self.make_keyboard(buttons)
    
    def pagination(self, callback_prefix: str, page: int, total_pages: int, 
                   extra_buttons: List[Dict[str, str]] = None) -> List[List[Dict[str, str]]]:
        """
        构建分页按钮行
        
        Args:
            callback_prefix: 回调前缀，如 "page:domains"
            page: 当前页码（从1开始）
            total_pages: 总页数
            extra_buttons: 额外的按钮（放在分页按钮后面）
            
        Returns:
            按钮行列表
        """
        buttons = []
        
        # 分页按钮
        if total_pages > 1:
            page_buttons = []
            
            # 上一页
            if page > 1:
                page_buttons.append(self.button('◀️', f'{callback_prefix}:{page - 1}'))
            
            # 页码显示
            page_buttons.append(self.button(f'{page}/{total_pages}', 'noop'))
            
            # 下一页
            if page < total_pages:
                page_buttons.append(self.button('▶️', f'{callback_prefix}:{page + 1}'))
            
            buttons.append(page_buttons)
        
        # 额外按钮
        if extra_buttons:
            buttons.append(extra_buttons)
        
        return buttons
    
    def domain_list(self, domains: List, page: int = 1, 
                    total_pages: int = 1, filter_type: str = None) -> Dict[str, Any]:
        """
        构建域名列表键盘
        
        Args:
            domains: 域名列表
            page: 当前页码
            total_pages: 总页数
            filter_type: 筛选类型 (expiring/expired/None)
            
        Returns:
            InlineKeyboardMarkup
        """
        buttons = []
        
        # 域名按钮
        for domain in domains:
            domain_name = getattr(domain, 'full_domain', str(domain))
            domain_id = getattr(domain, 'id', 0)
            buttons.append([self.button(f'🌐 {domain_name}', f'domain:{domain_id}')])
        
        # 筛选按钮
        filter_buttons = [
            self.button('⏰ 即将到期', 'domains:filter:expiring'),
            self.button('❌ 已过期', 'domains:filter:expired'),
        ]
        if filter_type:
            filter_buttons.append(self.button('🔄 全部', 'domains:filter:all'))
        buttons.append(filter_buttons)
        
        # 分页按钮
        buttons.extend(self.pagination('page:domains', page, total_pages))
        
        # 返回按钮
        buttons.append([
            self.button('🛒 购买域名', 'menu:buy'),
            self.button('🏠 主菜单', 'menu:main')
        ])
        
        return self.make_keyboard(buttons)
    
    def domain_detail(self, domain_id: int) -> Dict[str, Any]:
        """
        构建域名详情键盘
        
        Args:
            domain_id: 域名ID
            
        Returns:
            InlineKeyboardMarkup
        """
        buttons = [
            [
                self.button('📝 DNS记录', f'dns:list:{domain_id}'),
                self.button('➕ 添加记录', f'dns:add:{domain_id}')
            ],
            [
                self.button('🔄 续费', f'domain:{domain_id}:renew'),
                self.button('⚙️ 设置', f'domain:{domain_id}:settings')
            ],
            [
                self.button('◀️ 返回列表', 'menu:domains'),
                self.button('🏠 主菜单', 'menu:main')
            ]
        ]
        return self.make_keyboard(buttons)
    
    def domain_settings(self, domain_id: int, auto_renew: bool, ns_mode: str) -> Dict[str, Any]:
        """
        构建域名设置键盘
        
        Args:
            domain_id: 域名ID
            auto_renew: 是否自动续费
            ns_mode: NS模式
            
        Returns:
            InlineKeyboardMarkup
        """
        auto_renew_text = '✅ 自动续费: 开' if auto_renew else '❌ 自动续费: 关'
        
        buttons = [
            [self.button(auto_renew_text, f'domain:{domain_id}:toggle_auto_renew')],
            [self.button(f'🔧 NS模式: {ns_mode}', f'domain:{domain_id}:toggle_ns')],
            [
                self.button('◀️ 返回', f'domain:{domain_id}'),
                self.button('🏠 主菜单', 'menu:main')
            ]
        ]
        return self.make_keyboard(buttons)
    
    def dns_record_types(self, domain_id: int) -> Dict[str, Any]:
        """
        构建 DNS 记录类型选择键盘
        
        Args:
            domain_id: 域名ID
            
        Returns:
            InlineKeyboardMarkup
        """
        types = ['A', 'AAAA', 'CNAME', 'TXT', 'MX', 'NS', 'SRV', 'CAA']
        buttons = []
        
        # 每行4个按钮
        row = []
        for i, t in enumerate(types):
            row.append(self.button(t, f'dns:{domain_id}:add:{t}'))
            if len(row) == 4:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        
        # 取消按钮
        buttons.append([
            self.button('❌ 取消', f'dns:list:{domain_id}')
        ])
        
        return self.make_keyboard(buttons)
    
    def dns_record_list(self, domain_id: int, records: List, 
                        page: int = 1, total_pages: int = 1) -> Dict[str, Any]:
        """
        构建 DNS 记录列表键盘
        
        Args:
            domain_id: 域名ID
            records: 记录列表
            page: 当前页码
            total_pages: 总页数
            
        Returns:
            InlineKeyboardMarkup
        """
        buttons = []
        
        # 记录按钮
        for record in records:
            record_id = getattr(record, 'id', 0)
            record_type = getattr(record, 'type', 'A')
            record_name = getattr(record, 'name', '@')
            proxied = getattr(record, 'proxied', False)
            proxy_icon = '🟠' if proxied else '⚪'
            
            text = f'{proxy_icon} {record_type} | {record_name}'
            buttons.append([self.button(text, f'dns:record:{record_id}')])
        
        # 分页按钮
        buttons.extend(self.pagination(f'page:dns:{domain_id}', page, total_pages))
        
        # 操作按钮
        buttons.append([
            self.button('➕ 添加记录', f'dns:add:{domain_id}'),
            self.button('◀️ 返回', f'domain:{domain_id}')
        ])
        
        return self.make_keyboard(buttons)
    
    def dns_record_detail(self, record_id: int, domain_id: int, 
                          can_proxy: bool = False) -> Dict[str, Any]:
        """
        构建 DNS 记录详情键盘
        
        Args:
            record_id: 记录ID
            domain_id: 域名ID
            can_proxy: 是否可以切换代理
            
        Returns:
            InlineKeyboardMarkup
        """
        buttons = [
            [
                self.button('✏️ 编辑', f'dns:{record_id}:edit'),
                self.button('🗑️ 删除', f'dns:{record_id}:delete')
            ]
        ]
        
        if can_proxy:
            buttons[0].insert(1, self.button('🔄 代理', f'dns:{record_id}:proxy'))
        
        buttons.append([
            self.button('◀️ 返回列表', f'dns:list:{domain_id}'),
            self.button('🏠 主菜单', 'menu:main')
        ])
        
        return self.make_keyboard(buttons)
    
    def error_recovery(self, actions: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        构建错误恢复键盘
        
        Args:
            actions: 恢复操作列表，格式为 [{'text': '按钮文字', 'callback': '回调数据'}]
            
        Returns:
            InlineKeyboardMarkup
        """
        buttons = []
        
        if actions:
            for action in actions:
                buttons.append([self.button(action['text'], action['callback'])])
        
        buttons.append([self.button('🏠 返回主菜单', 'menu:main')])
        
        return self.make_keyboard(buttons)
    
    def recharge_prompt(self) -> Dict[str, Any]:
        """构建充值提示键盘"""
        buttons = [
            [self.button('💳 去充值', 'menu:account')],
            [self.button('🏠 返回主菜单', 'menu:main')]
        ]
        return self.make_keyboard(buttons)
