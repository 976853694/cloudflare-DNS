"""
时区工具 - 使用北京时间 (UTC+8)
"""
from datetime import datetime, timezone, timedelta

# 北京时区
BEIJING_TZ = timezone(timedelta(hours=8))


def now():
    """获取当前北京时间"""
    return datetime.now(BEIJING_TZ).replace(tzinfo=None)


def from_utc(dt):
    """将UTC时间转换为北京时间"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BEIJING_TZ).replace(tzinfo=None)


def to_utc(dt):
    """将北京时间转换为UTC时间"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BEIJING_TZ)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)
