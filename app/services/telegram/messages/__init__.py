"""
Telegram 消息模块

提供多语言消息支持
"""

from .manager import MessageManager
from .zh import ZH_MESSAGES
from .en import EN_MESSAGES

__all__ = [
    'MessageManager',
    'ZH_MESSAGES',
    'EN_MESSAGES',
]
