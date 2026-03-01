"""
Telegram 通知模块

提供各类通知发送功能：
- 域名到期提醒
- 购买成功通知
- 余额变动通知
- 托管商订单通知
- 管理员通知
- 群发通知
"""

from .sender import NotificationSender

__all__ = [
    'NotificationSender',
]

# 全局通知发送器实例
_notification_sender = None


def get_notification_sender(bot=None):
    """
    获取通知发送器实例
    
    Args:
        bot: Telegram Bot 实例（首次调用时需要）
        
    Returns:
        NotificationSender 实例
    """
    global _notification_sender
    
    if _notification_sender is None:
        _notification_sender = NotificationSender(bot)
    elif bot is not None:
        _notification_sender.bot = bot
    
    return _notification_sender


def init_notification_sender(bot):
    """
    初始化通知发送器
    
    Args:
        bot: Telegram Bot 实例
    """
    global _notification_sender
    _notification_sender = NotificationSender(bot)
    return _notification_sender
