"""
Telegram 机器人服务模块

注意：此文件已弃用，实际服务实现在 app/services/telegram_bot.py

主服务 TelegramBotService 使用同步的 requests 库实现，
支持多 API 地址轮询、模块化处理器架构。

如需使用 Telegram 机器人服务，请导入：
    from app.services.telegram_bot import TelegramBotService
"""

# 为了向后兼容，从主服务导入
from app.services.telegram_bot import TelegramBotService

__all__ = ['TelegramBotService']
