"""
基础处理器

提供所有处理器的基类，包含通用方法：
- 消息发送/编辑
- 回调响应
- 用户获取
- 权限检查
"""

from typing import Optional, Dict, Any, List
from ..utils.session import SessionManager
from ..messages.manager import MessageManager
from ..keyboards.builder import KeyboardBuilder


class BaseHandler:
    """处理器基类"""
    
    def __init__(self, bot_service=None):
        """
        初始化处理器
        
        Args:
            bot_service: TelegramBotService 实例
        """
        self.bot_service = bot_service
        self.session = SessionManager
        self.messages = MessageManager()
        self.keyboards = KeyboardBuilder(self.messages)
    
    def get_user(self, telegram_id: int):
        """
        根据 Telegram ID 获取绑定用户
        
        Args:
            telegram_id: Telegram 用户 ID
            
        Returns:
            绑定的用户对象，未绑定返回 None
        """
        try:
            from app.models.telegram import TelegramUser
            from app.models.user import User
            
            tg_user = TelegramUser.get_by_telegram_id(telegram_id)
            if tg_user and tg_user.user_id:
                return User.query.get(tg_user.user_id)
        except Exception as e:
            print(f'[BaseHandler] Error getting user: {e}')
        
        return None
    
    def get_tg_user(self, telegram_id: int):
        """
        获取 Telegram 用户记录
        
        Args:
            telegram_id: Telegram 用户 ID
            
        Returns:
            TelegramUser 对象
        """
        try:
            from app.models.telegram import TelegramUser
            return TelegramUser.get_by_telegram_id(telegram_id)
        except Exception as e:
            print(f'[BaseHandler] Error getting tg user: {e}')
        return None
    
    def get_user_lang(self, telegram_id: int = None, user=None) -> str:
        """
        获取用户语言设置
        
        Args:
            telegram_id: Telegram 用户 ID
            user: 用户对象
            
        Returns:
            语言代码
        """
        if telegram_id:
            tg_user = self.get_tg_user(telegram_id)
            if tg_user and hasattr(tg_user, 'language') and tg_user.language:
                return tg_user.language
        return 'zh'  # 默认中文
    
    def get_text(self, key: str, telegram_id: int = None, **kwargs) -> str:
        """
        获取消息文本
        
        Args:
            key: 消息键
            telegram_id: Telegram 用户 ID（用于获取语言设置）
            **kwargs: 格式化参数
            
        Returns:
            消息文本
        """
        lang = self.get_user_lang(telegram_id) if telegram_id else 'zh'
        return self.messages.get(key, lang=lang, **kwargs)
    
    def send_message(self, chat_id: int, text: str,
                    keyboard: Dict[str, Any] = None,
                    parse_mode: str = 'HTML') -> bool:
        """
        发送消息
        
        Args:
            chat_id: 聊天 ID
            text: 消息文本
            keyboard: 键盘（InlineKeyboardMarkup 格式）
            parse_mode: 解析模式（HTML/Markdown）
            
        Returns:
            是否成功
        """
        if not self.bot_service:
            return False
        
        return self.bot_service.send_message(chat_id, text, parse_mode, keyboard)
    
    def edit_message(self, chat_id: int, message_id: int, text: str,
                    keyboard: Dict[str, Any] = None,
                    parse_mode: str = 'HTML') -> bool:
        """
        编辑消息
        
        Args:
            chat_id: 聊天 ID
            message_id: 消息 ID
            text: 新文本
            keyboard: 新键盘
            parse_mode: 解析模式
            
        Returns:
            是否成功
        """
        if not self.bot_service:
            return False
        
        return self.bot_service.edit_message(chat_id, message_id, text, parse_mode, keyboard)
    
    def make_keyboard(self, buttons: List[List[Dict[str, str]]], include_ad: bool = True) -> Dict[str, Any]:
        """
        创建内联键盘
        
        Args:
            buttons: 按钮列表
            include_ad: 是否包含广告按钮
            
        Returns:
            键盘对象
        """
        # 使用 KeyboardBuilder 的静态方法，会自动添加广告按钮
        return KeyboardBuilder.make_keyboard(buttons, include_ad=include_ad)
    
    def check_permission(self, user, required: str) -> bool:
        """
        检查用户权限
        
        Args:
            user: 用户对象
            required: 所需权限级别 ('user', 'host', 'admin')
            
        Returns:
            是否有权限
        """
        if not user:
            return False
        
        if required == 'user':
            return True
        elif required == 'host':
            return getattr(user, 'is_host', False)
        elif required == 'admin':
            return getattr(user, 'is_admin', False)
        
        return False
    
    def get_permission_level(self, user) -> str:
        """
        获取用户权限级别
        
        Args:
            user: 用户对象
            
        Returns:
            权限级别 ('unbound', 'user', 'host', 'admin')
        """
        if not user:
            return 'unbound'
        
        if getattr(user, 'is_admin', False):
            return 'admin'
        elif getattr(user, 'is_host', False):
            return 'host'
        else:
            return 'user'
    
    # 会话状态管理快捷方法
    
    def get_session_state(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """获取会话状态"""
        return self.session.get_state(chat_id)
    
    def set_session_state(self, chat_id: int, state: str, data: Dict[str, Any] = None) -> bool:
        """设置会话状态"""
        return self.session.set_state(chat_id, state, data)
    
    def clear_session_state(self, chat_id: int) -> bool:
        """清除会话状态"""
        return self.session.clear_state(chat_id)
    
    def update_session_data(self, chat_id: int, **kwargs) -> bool:
        """更新会话数据"""
        return self.session.update_data(chat_id, **kwargs)

    # 错误处理
    
    def handle_error(self, chat_id: int, error: Exception,
                    message_id: int = None,
                    recovery_actions: List[Dict[str, str]] = None,
                    telegram_id: int = None):
        """
        统一错误处理
        
        Args:
            chat_id: 聊天 ID
            error: 异常对象
            message_id: 消息 ID（用于编辑）
            recovery_actions: 恢复操作列表
            telegram_id: Telegram 用户 ID
        """
        error_type = type(error).__name__
        
        # 记录错误日志
        print(f'[BaseHandler] Error: {error_type} - {str(error)}')
        
        # 获取用户友好的错误消息
        error_key = f'error.{error_type.lower()}'
        text = self.get_text(error_key, telegram_id)
        if text == error_key:
            text = self.get_text('error.generic', telegram_id)
        
        text = f'❌ {text}'
        
        # 构建恢复按钮
        if recovery_actions:
            buttons = [[{'text': action.get('text', '返回'), 
                        'callback_data': action.get('callback', 'menu:main')}] 
                      for action in recovery_actions]
        else:
            buttons = [[{'text': '🏠 返回主菜单', 'callback_data': 'menu:main'}]]
        
        keyboard = self.make_keyboard(buttons)
        
        # 发送或编辑消息
        if message_id:
            self.edit_message(chat_id, message_id, text, keyboard)
        else:
            self.send_message(chat_id, text, keyboard)
    
    def show_loading(self, chat_id: int, message_id: int = None, telegram_id: int = None):
        """
        显示加载中提示
        
        Args:
            chat_id: 聊天 ID
            message_id: 消息 ID（用于编辑）
            telegram_id: Telegram 用户 ID
        """
        text = self.get_text('common.loading', telegram_id)
        if not text or text == 'common.loading':
            text = '⏳ 加载中...'
        
        if message_id:
            self.edit_message(chat_id, message_id, text)
        else:
            self.send_message(chat_id, text)
    
    def require_bind(self, chat_id: int, telegram_id: int, message_id: int = None) -> bool:
        """
        检查用户是否已绑定，未绑定则发送提示
        
        Args:
            chat_id: 聊天 ID
            telegram_id: Telegram 用户 ID
            message_id: 消息 ID（用于编辑）
            
        Returns:
            是否已绑定
        """
        user = self.get_user(telegram_id)
        if user:
            return True
        
        text = self.get_text('bind.required', telegram_id)
        if not text or text == 'bind.required':
            text = '❌ 请先绑定账号\n\n请在网站「安全设置」页面获取绑定码，然后发送：/bind [绑定码]'
        
        buttons = [[{'text': '📖 查看帮助', 'callback_data': 'help:bind'}]]
        keyboard = self.make_keyboard(buttons)
        
        if message_id:
            self.edit_message(chat_id, message_id, text, keyboard)
        else:
            self.send_message(chat_id, text, keyboard)
        
        return False
    
    def require_host(self, chat_id: int, telegram_id: int, message_id: int = None) -> bool:
        """
        检查用户是否为托管商
        
        Args:
            chat_id: 聊天 ID
            telegram_id: Telegram 用户 ID
            message_id: 消息 ID
            
        Returns:
            是否为托管商
        """
        user = self.get_user(telegram_id)
        if user and getattr(user, 'is_host', False):
            return True
        
        text = '❌ 此功能仅限托管商使用'
        buttons = [[{'text': '🏠 返回主菜单', 'callback_data': 'menu:main'}]]
        keyboard = self.make_keyboard(buttons)
        
        if message_id:
            self.edit_message(chat_id, message_id, text, keyboard)
        else:
            self.send_message(chat_id, text, keyboard)
        
        return False
    
    def require_admin(self, chat_id: int, telegram_id: int, message_id: int = None) -> bool:
        """
        检查用户是否为管理员
        
        Args:
            chat_id: 聊天 ID
            telegram_id: Telegram 用户 ID
            message_id: 消息 ID
            
        Returns:
            是否为管理员
        """
        user = self.get_user(telegram_id)
        if user and getattr(user, 'is_admin', False):
            return True
        
        text = '❌ 此功能仅限管理员使用'
        buttons = [[{'text': '🏠 返回主菜单', 'callback_data': 'menu:main'}]]
        keyboard = self.make_keyboard(buttons)
        
        if message_id:
            self.edit_message(chat_id, message_id, text, keyboard)
        else:
            self.send_message(chat_id, text, keyboard)
        
        return False
    
    # ==================== 输入验证方法 ====================
    
    def validate_input(self, text: str, input_type: str, **kwargs) -> tuple:
        """
        通用输入验证
        
        Args:
            text: 用户输入的文本
            input_type: 输入类型 ('username', 'email', 'number', 'code', 'domain_prefix')
            **kwargs: 额外参数（如 min_value, max_value, min_length, max_length）
            
        Returns:
            (is_valid, error_message, cleaned_value)
        """
        import re
        
        text = text.strip() if text else ''
        
        if not text:
            return False, '❌ 输入不能为空', None
        
        if input_type == 'username':
            # 用户名验证：字母、数字、下划线，3-20字符
            if not re.match(r'^[a-zA-Z0-9_]{3,20}$', text):
                return False, '❌ 用户名格式不正确\n\n只能包含字母、数字和下划线，长度3-20字符', None
            return True, '', text
        
        elif input_type == 'email':
            # 邮箱验证
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', text):
                return False, '❌ 邮箱格式不正确', None
            return True, '', text.lower()
        
        elif input_type == 'number':
            # 数字验证
            try:
                value = int(text)
                min_val = kwargs.get('min_value', 0)
                max_val = kwargs.get('max_value', float('inf'))
                
                if value < min_val:
                    return False, f'❌ 数值不能小于 {min_val}', None
                if value > max_val:
                    return False, f'❌ 数值不能大于 {max_val}', None
                
                return True, '', value
            except ValueError:
                return False, '❌ 请输入有效的数字', None
        
        elif input_type == 'code':
            # 验证码验证：6位数字
            if not re.match(r'^\d{6}$', text):
                return False, '❌ 验证码格式不正确\n\n请输入6位数字验证码', None
            return True, '', text
        
        elif input_type == 'domain_prefix':
            # 域名前缀验证
            min_len = kwargs.get('min_length', 1)
            max_len = kwargs.get('max_length', 63)
            
            prefix = text.lower()
            
            if not re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', prefix):
                return False, '❌ 前缀格式不正确\n\n只能包含字母、数字和连字符，不能以连字符开头或结尾', None
            
            if len(prefix) < min_len or len(prefix) > max_len:
                return False, f'❌ 前缀长度必须在 {min_len}-{max_len} 个字符之间', None
            
            return True, '', prefix
        
        elif input_type == 'text':
            # 普通文本验证
            min_len = kwargs.get('min_length', 1)
            max_len = kwargs.get('max_length', 1000)
            
            if len(text) < min_len:
                return False, f'❌ 内容长度不能少于 {min_len} 个字符', None
            if len(text) > max_len:
                return False, f'❌ 内容长度不能超过 {max_len} 个字符', None
            
            return True, '', text
        
        # 默认返回原始文本
        return True, '', text
    
    def show_validation_error(self, chat_id: int, error_message: str, 
                             retry_prompt: str = None,
                             cancel_callback: str = 'menu:main'):
        """
        显示验证错误并提示重试
        
        Args:
            chat_id: 聊天 ID
            error_message: 错误消息
            retry_prompt: 重试提示（可选）
            cancel_callback: 取消按钮的回调
        """
        text = error_message
        if retry_prompt:
            text += f'\n\n{retry_prompt}'
        
        buttons = [[{'text': '❌ 取消', 'callback_data': cancel_callback}]]
        keyboard = self.make_keyboard(buttons)
        self.send_message(chat_id, text, keyboard)
