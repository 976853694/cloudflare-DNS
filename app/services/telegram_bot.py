"""
Telegram 机器人服务
使用轮询模式，无需公网IP
支持多API地址轮询
采用模块化架构，全按钮交互方式
"""
import threading
import time
import requests
import os
import urllib3
from flask import current_app
from decimal import Decimal

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 默认 Telegram API 地址
DEFAULT_API_URL = 'https://api.telegram.org'


class TelegramBotService:
    """Telegram 机器人服务"""
    
    _instance = None
    _bot_thread = None
    _running = False
    _token = None
    _app = None
    _session = None
    _api_urls = []  # API地址列表
    _current_api_index = 0  # 当前使用的API地址索引
    _handlers = {}  # 处理器实例
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def _get_session(cls):
        """获取 requests session"""
        if cls._session is None:
            cls._session = requests.Session()
            http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
            https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
            if http_proxy or https_proxy:
                cls._session.proxies = {
                    'http': http_proxy,
                    'https': https_proxy or http_proxy
                }
        return cls._session
    
    @classmethod
    def _get_api_base_url(cls):
        """获取当前API基础地址"""
        if cls._api_urls:
            return cls._api_urls[cls._current_api_index]
        return DEFAULT_API_URL
    
    @classmethod
    def _switch_api_url(cls):
        """切换到下一个API地址"""
        if cls._api_urls and len(cls._api_urls) > 1:
            cls._current_api_index = (cls._current_api_index + 1) % len(cls._api_urls)
            if cls._app:
                with cls._app.app_context():
                    current_app.logger.info(f'[TelegramBot] 切换API地址: {cls._get_api_base_url()}')
            return True
        return False

    @classmethod
    def init_app(cls, app):
        """初始化机器人服务"""
        cls._app = app
        
        with app.app_context():
            from app.models.telegram import TelegramBot
            from app.models.setting import Setting
            from app.services.telegram.keyboards import KeyboardBuilder
            
            bot_config = TelegramBot.get_enabled_bot()
            
            if bot_config and bot_config.token:
                cls._token = bot_config.token
                # 加载API地址列表
                cls._api_urls = bot_config.get_api_urls()
                cls._current_api_index = 0
                
                # 从系统设置加载广告按钮配置
                ad_buttons_str = Setting.get('ad_buttons', '')
                ad_buttons = cls._parse_ad_buttons(ad_buttons_str)
                KeyboardBuilder.set_ad_buttons(ad_buttons)
                
                # 初始化处理器
                cls._init_handlers()
                
                # 设置命令菜单
                cls._set_bot_commands()
                
                cls.start()
                api_info = f', API地址: {cls._get_api_base_url()}' if cls._api_urls else ''
                ad_info = f', 广告按钮: {len(ad_buttons)}个' if ad_buttons else ''
                app.logger.info(f'[TelegramBot] 机器人已启动: {bot_config.name}{api_info}{ad_info}')
            else:
                app.logger.info('[TelegramBot] 未配置机器人Token，跳过启动')
    
    @classmethod
    def _parse_ad_buttons(cls, ad_buttons_str):
        """解析广告按钮配置字符串"""
        if not ad_buttons_str:
            return []
        buttons = []
        for line in ad_buttons_str.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            parts = line.split(',', 1)
            if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                buttons.append((parts[0].strip(), parts[1].strip()))
        return buttons
    
    @classmethod
    def _init_handlers(cls):
        """初始化所有处理器"""
        from app.services.telegram.handlers import (
            BindHandler,
            MenuHandler,
            DomainHandler,
            DNSHandler,
            BuyHandler,
            AccountHandler,
            AnnouncementHandler,
            SettingsHandler,
            HelpHandler,
            HostCenterHandler,
            AdminHandler,
            TransferHandler,
            PointsHandler,
            TicketHandler
        )
        
        cls._handlers = {
            'bind': BindHandler(cls),
            'menu': MenuHandler(cls),
            'domain': DomainHandler(cls),
            'dns': DNSHandler(cls),
            'buy': BuyHandler(cls),
            'account': AccountHandler(cls),
            'announcement': AnnouncementHandler(cls),
            'settings': SettingsHandler(cls),
            'help': HelpHandler(cls),
            'host_center': HostCenterHandler(cls),
            'admin': AdminHandler(cls),
            'transfer': TransferHandler(cls),
            'points': PointsHandler(cls),
            'ticket': TicketHandler(cls)
        }
    
    @classmethod
    def _set_bot_commands(cls):
        """设置机器人命令菜单"""
        if not cls._token:
            return False
        
        commands = [
            {'command': 'help', 'description': '❓ 帮助中心'}
        ]
        
        base_url = cls._get_api_base_url()
        url = f'{base_url}/bot{cls._token}/setMyCommands'
        
        try:
            session = cls._get_session()
            resp = session.post(url, json={'commands': commands}, timeout=10, verify=False)
            result = resp.json()
            if result.get('ok'):
                if cls._app:
                    with cls._app.app_context():
                        current_app.logger.info('[TelegramBot] 命令菜单设置成功')
                return True
            else:
                if cls._app:
                    with cls._app.app_context():
                        current_app.logger.warning(f'[TelegramBot] 命令菜单设置失败: {result.get("description")}')
        except Exception as e:
            if cls._app:
                with cls._app.app_context():
                    current_app.logger.error(f'[TelegramBot] 设置命令菜单错误: {e}')
        
        return False
    
    @classmethod
    def start(cls):
        """启动机器人轮询"""
        if cls._running:
            return
        
        cls._running = True
        cls._bot_thread = threading.Thread(target=cls._polling_loop, daemon=True)
        cls._bot_thread.start()
    
    @classmethod
    def stop(cls):
        """停止机器人"""
        cls._running = False
        if cls._bot_thread and cls._bot_thread.is_alive():
            cls._bot_thread.join(timeout=10)
        cls._bot_thread = None
    
    @classmethod
    def restart(cls):
        """重启机器人"""
        # 确保完全停止
        cls.stop()
        time.sleep(2)
        
        # 再次确认已停止
        if cls._bot_thread and cls._bot_thread.is_alive():
            cls._running = False
            cls._bot_thread.join(timeout=5)
            cls._bot_thread = None
        
        if cls._app:
            with cls._app.app_context():
                from app.models.telegram import TelegramBot
                from app.models.setting import Setting
                from app.services.telegram.keyboards import KeyboardBuilder
                
                bot_config = TelegramBot.get_enabled_bot()
                
                if bot_config and bot_config.token:
                    cls._token = bot_config.token
                    cls._api_urls = bot_config.get_api_urls()
                    cls._current_api_index = 0
                    
                    # 从系统设置重新加载广告按钮配置
                    ad_buttons_str = Setting.get('ad_buttons', '')
                    ad_buttons = cls._parse_ad_buttons(ad_buttons_str)
                    KeyboardBuilder.set_ad_buttons(ad_buttons)
                    
                    cls._init_handlers()
                    cls.start()
                    return True
        return False
    
    @classmethod
    def _polling_loop(cls):
        """轮询循环"""
        offset = 0
        fail_count = 0
        cleanup_counter = 0  # 清理计数器
        
        while cls._running:
            try:
                updates = cls._get_updates(offset)
                
                if updates is not None:
                    fail_count = 0
                    for update in updates:
                        offset = update['update_id'] + 1
                        cls._handle_update(update)
                else:
                    fail_count += 1
                    if fail_count >= 3 and cls._switch_api_url():
                        fail_count = 0
                
                # 每60次循环（约1分钟）清理一次过期会话
                cleanup_counter += 1
                if cleanup_counter >= 60:
                    cleanup_counter = 0
                    if cls._app:
                        with cls._app.app_context():
                            from app.services.telegram.utils.session import SessionManager
                            cleaned = SessionManager.cleanup_expired_sessions()
                            if cleaned > 0:
                                current_app.logger.info(f'[TelegramBot] 清理了 {cleaned} 个过期会话')
                    
            except Exception as e:
                if cls._app:
                    with cls._app.app_context():
                        current_app.logger.error(f'[TelegramBot] 轮询错误: {e}')
                fail_count += 1
                if fail_count >= 3 and cls._switch_api_url():
                    fail_count = 0
                time.sleep(5)
            
            time.sleep(1)
    
    @classmethod
    def _get_updates(cls, offset=0):
        """获取更新"""
        if not cls._token:
            return []
        
        base_url = cls._get_api_base_url()
        url = f'{base_url}/bot{cls._token}/getUpdates'
        params = {'offset': offset, 'timeout': 30, 'allowed_updates': ['message', 'callback_query']}
        
        try:
            session = cls._get_session()
            resp = session.get(url, params=params, timeout=35, verify=False)
            data = resp.json()
            
            if data.get('ok'):
                return data.get('result', [])
        except Exception as e:
            if cls._app:
                with cls._app.app_context():
                    current_app.logger.error(f'[TelegramBot] 请求错误 ({base_url}): {e}')
        
        return None

    @classmethod
    def _handle_update(cls, update):
        """处理更新 - 支持命令和回调"""
        # 处理回调查询（按钮点击）
        if 'callback_query' in update:
            cls._handle_callback(update['callback_query'])
            return
        
        # 处理普通消息
        if 'message' not in update:
            return
        
        message = update['message']
        chat_id = message['chat']['id']
        chat_type = message['chat'].get('type', 'private')
        text = message.get('text', '')
        user_info = message.get('from', {})
        telegram_id = user_info.get('id')
        
        # 调试日志
        if text.startswith('/'):
            print(f'[TelegramBot] 收到命令: {text}, chat_type: {chat_type}, chat_id: {chat_id}')
        
        # 在应用上下文中执行
        if cls._app:
            with cls._app.app_context():
                # 检查是否有活跃会话
                from app.services.telegram.utils.session import SessionManager
                session = SessionManager.get_state(chat_id)
                
                # 如果有活跃会话且不是命令，处理文本输入
                if session and not text.startswith('/'):
                    cls._handle_text_input(chat_id, telegram_id, text, user_info, session, chat_type)
                    return
                
                # 处理命令
                if text.startswith('/'):
                    cls._handle_command(chat_id, telegram_id, text, user_info, chat_type)
    
    @classmethod
    def _handle_command(cls, chat_id, telegram_id, text, user_info, chat_type):
        """处理命令"""
        # 解析命令
        parts = text.strip().split()
        if not parts:
            return
        cmd = parts[0].lower().split('@')[0]
        args = parts[1:] if len(parts) > 1 else []
        
        # 定义私聊专用命令
        private_only_commands = ['/start', '/bind']
        
        try:
            # 检查是否是群聊中的私聊专用命令
            if chat_type != 'private' and cmd in private_only_commands:
                # 在群聊中提示用户私聊使用
                cls.send_message(
                    chat_id, 
                    '⚠️ 为保护您的隐私，此功能只能在私聊中使用\n\n请点击机器人头像，发送 /start 开始使用'
                )
                return
            
            # 命令路由
            if cmd == '/start':
                handler = cls._handlers.get('menu')
                if handler:
                    handler.handle_start(chat_id, telegram_id, user_info)
            elif cmd == '/bind':
                handler = cls._handlers.get('bind')
                if handler:
                    handler.handle_bind_command(chat_id, telegram_id, user_info, args, chat_type)
            elif cmd == '/help':
                # /help 命令可以在群聊中使用
                handler = cls._handlers.get('help')
                if handler:
                    handler.handle_help(chat_id, telegram_id, user_info)
        except Exception as e:
            if cls._app:
                with cls._app.app_context():
                    current_app.logger.error(f'[TelegramBot] 命令处理错误 ({cmd}): {e}')
                    import traceback
                    traceback.print_exc()
    
    @classmethod
    def _handle_text_input(cls, chat_id, telegram_id, text, user_info, session, chat_type='private'):
        """处理文本输入"""
        state = session.get('state', '')
        handled = False
        
        # 绑定相关
        if state.startswith('bind_'):
            handler = cls._handlers.get('bind')
            if handler and hasattr(handler, 'handle_text_input'):
                handled = handler.handle_text_input(chat_id, telegram_id, text, session)
        
        # DNS 相关
        elif state.startswith('dns_'):
            handler = cls._handlers.get('dns')
            if handler and hasattr(handler, 'handle_text_input'):
                handled = handler.handle_text_input(chat_id, telegram_id, text, session)
        
        # 购买相关
        elif state.startswith('buy_'):
            handler = cls._handlers.get('buy')
            if handler and hasattr(handler, 'handle_text_input'):
                handled = handler.handle_text_input(chat_id, telegram_id, text, session)
        
        # 账户相关
        elif state.startswith('account_'):
            handler = cls._handlers.get('account')
            if handler and hasattr(handler, 'handle_text_input'):
                handled = handler.handle_text_input(chat_id, telegram_id, text, session)
        
        # 托管商中心相关
        elif state.startswith('hc_'):
            handler = cls._handlers.get('host_center')
            if handler and hasattr(handler, 'handle_text_input'):
                handled = handler.handle_text_input(chat_id, telegram_id, text, session)
        
        # 管理后台相关
        elif state.startswith('admin_'):
            handler = cls._handlers.get('admin')
            if handler and hasattr(handler, 'handle_text_input'):
                handled = handler.handle_text_input(chat_id, telegram_id, text, session)
        
        # 域名转移相关
        elif state.startswith('transfer_'):
            handler = cls._handlers.get('transfer')
            if handler and hasattr(handler, 'handle_text_input'):
                handled = handler.handle_text_input(chat_id, telegram_id, text, session)
        
        # 积分相关
        elif state.startswith('points_'):
            handler = cls._handlers.get('points')
            if handler and hasattr(handler, 'handle_text_input'):
                handled = handler.handle_text_input(chat_id, telegram_id, text, session, chat_type)
        
        # 工单相关
        elif state.startswith('ticket_'):
            handler = cls._handlers.get('ticket')
            if handler and hasattr(handler, 'handle_text_input'):
                handled = handler.handle_text_input(chat_id, telegram_id, text, session)
        
        # 如果没有处理，显示主菜单
        if not handled:
            handler = cls._handlers.get('menu')
            if handler:
                handler.handle_start(chat_id, telegram_id, user_info)
    
    @classmethod
    def _handle_callback(cls, callback_query):
        """处理回调查询（按钮点击）"""
        callback_id = callback_query['id']
        chat_id = callback_query['message']['chat']['id']
        message_id = callback_query['message']['message_id']
        user_info = callback_query['from']
        telegram_id = user_info.get('id')
        data = callback_query.get('data', '')
        
        # 应答回调，防止按钮一直转圈
        cls._answer_callback(callback_id)
        
        # 在应用上下文中处理
        if cls._app:
            with cls._app.app_context():
                cls._route_callback(chat_id, message_id, telegram_id, user_info, data)
    
    @classmethod
    def _route_callback(cls, chat_id, message_id, telegram_id, user_info, data):
        """路由回调到对应处理器"""
        # 路由映射
        routes = {
            'menu:': 'menu',
            'bind:': 'bind',
            'domain:': 'domain',
            'dns:': 'dns',
            'buy:': 'buy',
            'account:': 'account',
            'announcement:': 'announcement',
            'settings:': 'settings',
            'help:': 'help',
            'hc:': 'host_center',
            'admin:': 'admin',
            'transfer:': 'transfer',
            'points:': 'points',
            'ticket:': 'ticket'
        }
        
        handler_name = None
        for prefix, name in routes.items():
            if data.startswith(prefix):
                handler_name = name
                break
        
        if handler_name and handler_name in cls._handlers:
            handler = cls._handlers[handler_name]
            if hasattr(handler, 'handle_callback'):
                handler.handle_callback(chat_id, message_id, telegram_id, user_info, data)
        else:
            # 未知回调，显示提示
            cls._answer_callback(None, '未知操作')

    # ==================== 消息发送方法 ====================
    
    @classmethod
    def send_message(cls, chat_id, text, parse_mode='HTML', reply_markup=None):
        """发送消息"""
        if not cls._token:
            return False
        
        base_url = cls._get_api_base_url()
        url = f'{base_url}/bot{cls._token}/sendMessage'
        data = {'chat_id': chat_id, 'text': text}
        if parse_mode:
            data['parse_mode'] = parse_mode
        if reply_markup:
            data['reply_markup'] = reply_markup
        
        try:
            session = cls._get_session()
            resp = session.post(url, json=data, timeout=10, verify=False)
            return resp.json().get('ok', False)
        except:
            return False
    
    @classmethod
    def _answer_callback(cls, callback_query_id, text=None):
        """应答回调查询"""
        if not cls._token or not callback_query_id:
            return False
        
        base_url = cls._get_api_base_url()
        url = f'{base_url}/bot{cls._token}/answerCallbackQuery'
        data = {'callback_query_id': callback_query_id}
        if text:
            data['text'] = text
        
        try:
            session = cls._get_session()
            resp = session.post(url, json=data, timeout=10, verify=False)
            return resp.json().get('ok', False)
        except:
            return False
    
    @classmethod
    def edit_message(cls, chat_id, message_id, text, parse_mode='HTML', reply_markup=None):
        """编辑消息，失败时发送新消息"""
        if not cls._token:
            return False
        
        base_url = cls._get_api_base_url()
        url = f'{base_url}/bot{cls._token}/editMessageText'
        data = {'chat_id': chat_id, 'message_id': message_id, 'text': text}
        if parse_mode:
            data['parse_mode'] = parse_mode
        if reply_markup:
            data['reply_markup'] = reply_markup
        
        try:
            session = cls._get_session()
            resp = session.post(url, json=data, timeout=10, verify=False)
            result = resp.json()
            
            if result.get('ok'):
                return True
            
            # 编辑失败，检查错误类型
            error_desc = result.get('description', '')
            
            # 如果是消息内容相同或消息太旧等错误，尝试发送新消息
            if any(err in error_desc.lower() for err in [
                'message is not modified',
                'message to edit not found',
                'message can\'t be edited',
                'message_id_invalid',
                'bad request'
            ]):
                if cls._app:
                    with cls._app.app_context():
                        current_app.logger.warning(f'[TelegramBot] 编辑消息失败: {error_desc}，尝试发送新消息')
                
                # 发送新消息替代
                return cls.send_message(chat_id, text, parse_mode, reply_markup)
            
            return False
        except Exception as e:
            if cls._app:
                with cls._app.app_context():
                    current_app.logger.error(f'[TelegramBot] 编辑消息异常: {e}，尝试发送新消息')
            
            # 异常时也尝试发送新消息
            return cls.send_message(chat_id, text, parse_mode, reply_markup)
    
    @classmethod
    def make_inline_keyboard(cls, buttons):
        """创建内联键盘
        buttons: [[{'text': '按钮文字', 'callback_data': '回调数据'}], ...]
        """
        return {'inline_keyboard': buttons}
    
    # ==================== 工具方法 ====================
    
    @classmethod
    def get_bound_user(cls, telegram_id):
        """获取绑定的系统用户"""
        from app.models.telegram import TelegramUser
        from app.models.user import User
        
        tg_user = TelegramUser.get_by_telegram_id(telegram_id)
        if tg_user and tg_user.user_id:
            return User.query.get(tg_user.user_id)
        return None
    
    @classmethod
    def get_user_language(cls, telegram_id):
        """获取用户语言设置"""
        from app.models.telegram import TelegramUser
        
        tg_user = TelegramUser.get_by_telegram_id(telegram_id)
        if tg_user and hasattr(tg_user, 'language') and tg_user.language:
            return tg_user.language
        return 'zh'  # 默认中文
    
    @classmethod
    def test_token(cls, token, api_url=None):
        """测试Token是否有效"""
        base_url = api_url.rstrip('/') if api_url else DEFAULT_API_URL
        url = f'{base_url}/bot{token}/getMe'
        
        try:
            session = cls._get_session()
            resp = session.get(url, timeout=10, verify=False)
            data = resp.json()
            
            if data.get('ok'):
                return True, data.get('result', {})
            else:
                return False, data.get('description', '未知错误')
        except Exception as e:
            return False, str(e)
    
    @classmethod
    def test_api_url(cls, api_url, token=None):
        """测试API地址是否可用"""
        test_token = token or cls._token
        if not test_token:
            return False, '未配置Bot Token'
        
        return cls.test_token(test_token, api_url)
    
    @classmethod
    def get_handler(cls, name):
        """获取处理器实例"""
        return cls._handlers.get(name)
