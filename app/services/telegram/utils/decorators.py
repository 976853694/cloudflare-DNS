"""
权限装饰器

提供各种权限检查装饰器：
- private_only: 强制私聊
- require_bind: 要求绑定
- require_host: 要求托管商权限
- require_admin: 要求管理员权限
"""

from functools import wraps
from typing import Callable, Any


def private_only(func: Callable) -> Callable:
    """
    强制私聊装饰器
    
    在群聊中调用时，会提示用户私聊机器人
    """
    @wraps(func)
    async def wrapper(self, update, context, *args, **kwargs):
        # 获取聊天类型
        chat = update.effective_chat
        if chat and chat.type != 'private':
            # 群聊中，发送私聊提示
            from ..messages.manager import MessageManager
            from ..keyboards.builder import KeyboardBuilder
            
            messages = MessageManager()
            keyboards = KeyboardBuilder()
            
            text = messages.get('error.private_only')
            bot_username = context.bot.username if context.bot else None
            
            if bot_username:
                keyboard = keyboards.private_chat_prompt(bot_username)
            else:
                keyboard = keyboards.back_to_menu()
            
            # 如果是回调查询，使用 answer_callback_query 显示提示
            if update.callback_query:
                await update.callback_query.answer(text, show_alert=True)
            else:
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=text,
                    reply_markup=keyboard
                )
            return None
        
        return await func(self, update, context, *args, **kwargs)
    
    return wrapper


def require_bind(func: Callable) -> Callable:
    """
    要求绑定装饰器
    
    未绑定用户调用时，会提示绑定账号
    """
    @wraps(func)
    async def wrapper(self, update, context, *args, **kwargs):
        from ..messages.manager import MessageManager
        from ..keyboards.builder import KeyboardBuilder
        
        # 获取 Telegram 用户 ID
        user = update.effective_user
        if not user:
            return None
        
        telegram_id = user.id
        
        # 检查绑定状态
        bound_user = await _get_bound_user(telegram_id)
        
        if not bound_user:
            messages = MessageManager()
            keyboards = KeyboardBuilder()
            
            text = messages.get('error.not_bound')
            keyboard = keyboards.bind_prompt()
            
            chat_id = update.effective_chat.id
            
            if update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(
                    text=text,
                    reply_markup=keyboard
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard
                )
            return None
        
        # 将绑定用户存入 context
        context.user_data['bound_user'] = bound_user
        
        return await func(self, update, context, *args, **kwargs)
    
    return wrapper


def require_host(func: Callable) -> Callable:
    """
    要求托管商权限装饰器
    
    非托管商用户调用时，会提示权限不足
    必须在 require_bind 之后使用
    """
    @wraps(func)
    async def wrapper(self, update, context, *args, **kwargs):
        from ..messages.manager import MessageManager
        from ..keyboards.builder import KeyboardBuilder
        
        # 获取绑定用户
        bound_user = context.user_data.get('bound_user')
        
        if not bound_user:
            # 未绑定，先检查绑定
            telegram_id = update.effective_user.id if update.effective_user else None
            if telegram_id:
                bound_user = await _get_bound_user(telegram_id)
                if bound_user:
                    context.user_data['bound_user'] = bound_user
        
        if not bound_user or not getattr(bound_user, 'is_host', False):
            messages = MessageManager()
            keyboards = KeyboardBuilder()
            
            text = messages.get('error.host_required')
            keyboard = keyboards.back_to_menu()
            
            chat_id = update.effective_chat.id
            
            if update.callback_query:
                await update.callback_query.answer(text, show_alert=True)
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard
                )
            return None
        
        return await func(self, update, context, *args, **kwargs)
    
    return wrapper


def require_admin(func: Callable) -> Callable:
    """
    要求管理员权限装饰器
    
    非管理员用户调用时，会提示权限不足
    必须在 require_bind 之后使用
    """
    @wraps(func)
    async def wrapper(self, update, context, *args, **kwargs):
        from ..messages.manager import MessageManager
        from ..keyboards.builder import KeyboardBuilder
        
        # 获取绑定用户
        bound_user = context.user_data.get('bound_user')
        
        if not bound_user:
            # 未绑定，先检查绑定
            telegram_id = update.effective_user.id if update.effective_user else None
            if telegram_id:
                bound_user = await _get_bound_user(telegram_id)
                if bound_user:
                    context.user_data['bound_user'] = bound_user
        
        if not bound_user or not getattr(bound_user, 'is_admin', False):
            messages = MessageManager()
            keyboards = KeyboardBuilder()
            
            text = messages.get('error.admin_required')
            keyboard = keyboards.back_to_menu()
            
            chat_id = update.effective_chat.id
            
            if update.callback_query:
                await update.callback_query.answer(text, show_alert=True)
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard
                )
            return None
        
        return await func(self, update, context, *args, **kwargs)
    
    return wrapper


async def _get_bound_user(telegram_id: int):
    """
    根据 Telegram ID 获取绑定的系统用户
    
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
        print(f'[TG Decorator] Error getting bound user: {e}')
    
    return None


# 组合装饰器
def private_bind(func: Callable) -> Callable:
    """
    私聊 + 绑定 组合装饰器
    
    等同于同时使用 @private_only 和 @require_bind
    """
    return private_only(require_bind(func))


def private_host(func: Callable) -> Callable:
    """
    私聊 + 绑定 + 托管商 组合装饰器
    """
    return private_only(require_bind(require_host(func)))


def private_admin(func: Callable) -> Callable:
    """
    私聊 + 绑定 + 管理员 组合装饰器
    """
    return private_only(require_bind(require_admin(func)))
