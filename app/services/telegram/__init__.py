"""
Telegram 机器人服务模块

模块化架构，支持四级权限体系：
- 未绑定用户
- 普通用户
- 托管商
- 管理员

所有敏感操作强制私聊使用，保护用户隐私。
"""

from .utils.session import SessionManager
from .messages.manager import MessageManager
from .keyboards.builder import KeyboardBuilder

__all__ = [
    'SessionManager',
    'MessageManager',
    'KeyboardBuilder',
]
