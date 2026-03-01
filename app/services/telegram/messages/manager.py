"""
消息管理器

提供多语言消息获取和格式化功能
"""

from typing import Optional, Dict, Any
from .zh import ZH_MESSAGES
from .en import EN_MESSAGES


class MessageManager:
    """多语言消息管理"""
    
    # 支持的语言
    SUPPORTED_LANGUAGES = ['zh', 'en']
    
    # 默认语言
    DEFAULT_LANGUAGE = 'zh'
    
    # 消息字典
    _messages = {
        'zh': ZH_MESSAGES,
        'en': EN_MESSAGES
    }
    
    def __init__(self, default_lang: str = None):
        """
        初始化消息管理器
        
        Args:
            default_lang: 默认语言，不传则使用类默认值
        """
        self.default_lang = default_lang or self.DEFAULT_LANGUAGE
    
    def get(self, key: str, lang: str = None, default: str = None, **kwargs) -> str:
        """
        获取消息文本
        
        Args:
            key: 消息键，支持点号分隔的层级结构，如 "error.not_bound"
            lang: 语言代码，不传则使用默认语言
            default: 默认值，消息不存在时返回
            **kwargs: 格式化参数
            
        Returns:
            格式化后的消息文本
        """
        lang = lang or self.default_lang
        
        # 确保语言有效
        if lang not in self._messages:
            lang = self.default_lang
        
        messages = self._messages.get(lang, self._messages[self.default_lang])
        
        # 支持点号分隔的键
        value = messages
        for k in key.split('.'):
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = None
                break
        
        # 如果找不到，尝试从默认语言获取
        if value is None and lang != self.default_lang:
            value = self._messages[self.default_lang]
            for k in key.split('.'):
                if isinstance(value, dict):
                    value = value.get(k)
                else:
                    value = None
                    break
        
        # 如果仍然找不到，返回默认值或键名
        if value is None:
            return default if default is not None else key
        
        # 如果不是字符串，返回键名
        if not isinstance(value, str):
            return default if default is not None else key
        
        # 格式化
        if kwargs:
            try:
                return value.format(**kwargs)
            except (KeyError, ValueError):
                return value
        
        return value
    
    def get_user_lang(self, user) -> str:
        """
        获取用户语言设置
        
        Args:
            user: 用户对象，需要有 tg_language 属性
            
        Returns:
            语言代码
        """
        if user and hasattr(user, 'tg_language') and user.tg_language:
            lang = user.tg_language
            if lang in self.SUPPORTED_LANGUAGES:
                return lang
        return self.default_lang
    
    def set_default_lang(self, lang: str):
        """
        设置默认语言
        
        Args:
            lang: 语言代码
        """
        if lang in self.SUPPORTED_LANGUAGES:
            self.default_lang = lang
    
    @classmethod
    def register_messages(cls, lang: str, messages: Dict[str, Any]):
        """
        注册新的语言消息
        
        Args:
            lang: 语言代码
            messages: 消息字典
        """
        cls._messages[lang] = messages
        if lang not in cls.SUPPORTED_LANGUAGES:
            cls.SUPPORTED_LANGUAGES.append(lang)
    
    @classmethod
    def update_messages(cls, lang: str, messages: Dict[str, Any]):
        """
        更新语言消息（合并）
        
        Args:
            lang: 语言代码
            messages: 要合并的消息字典
        """
        if lang not in cls._messages:
            cls._messages[lang] = {}
        
        cls._deep_merge(cls._messages[lang], messages)
    
    @staticmethod
    def _deep_merge(base: dict, update: dict):
        """深度合并字典"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                MessageManager._deep_merge(base[key], value)
            else:
                base[key] = value


# 全局消息管理器实例
messages = MessageManager()
