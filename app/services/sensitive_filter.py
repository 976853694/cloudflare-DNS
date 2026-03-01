"""
敏感词过滤服务
用于检测和过滤域名前缀中的敏感词
"""
import re
from app.models import Setting


class SensitiveFilter:
    """敏感词过滤器"""
    
    # 内置敏感词列表（精简版，避免误报）
    DEFAULT_WORDS = [
        # 违法相关
        'porn', 'xxx', 'casino', 'gambling', 'warez',
        # 系统保留（仅核心）
        'www', 'ns1', 'ns2', 'mx', 'smtp', 'pop', 'imap',
    ]
    
    # 敏感词正则模式
    DEFAULT_PATTERNS = [
        r'[-]{2,}',   # 连续横线
        r'^-|-$',     # 横线开头或结尾
    ]
    
    _words_cache = None
    _patterns_cache = None
    
    @classmethod
    def get_sensitive_words(cls):
        """获取敏感词列表"""
        if cls._words_cache is not None:
            return cls._words_cache
        
        # 从数据库获取自定义敏感词
        custom_words = Setting.get('sensitive_words', '')
        custom_list = [w.strip().lower() for w in custom_words.split('\n') if w.strip()]
        
        # 合并默认和自定义
        cls._words_cache = set(cls.DEFAULT_WORDS + custom_list)
        return cls._words_cache
    
    @classmethod
    def get_patterns(cls):
        """获取敏感词正则模式"""
        if cls._patterns_cache is not None:
            return cls._patterns_cache
        
        # 从数据库获取自定义模式
        custom_patterns = Setting.get('sensitive_patterns', '')
        custom_list = [p.strip() for p in custom_patterns.split('\n') if p.strip()]
        
        patterns = cls.DEFAULT_PATTERNS + custom_list
        cls._patterns_cache = [re.compile(p, re.IGNORECASE) for p in patterns]
        return cls._patterns_cache
    
    @classmethod
    def clear_cache(cls):
        """清除缓存（配置更新后调用）"""
        cls._words_cache = None
        cls._patterns_cache = None
    
    @classmethod
    def contains_sensitive(cls, text):
        """
        检查文本是否包含敏感词
        
        Args:
            text: 待检查的文本
            
        Returns:
            bool: 是否包含敏感词
        """
        if not text:
            return False
        
        text_lower = text.lower()
        
        # 检查敏感词
        for word in cls.get_sensitive_words():
            if word in text_lower:
                return True
        
        # 检查正则模式
        for pattern in cls.get_patterns():
            if pattern.search(text_lower):
                return True
        
        return False
    
    @classmethod
    def filter_text(cls, text, replacement='*'):
        """
        过滤敏感词
        
        Args:
            text: 待过滤的文本
            replacement: 替换字符
            
        Returns:
            str: 过滤后的文本
        """
        if not text:
            return text
        
        result = text.lower()
        
        for word in cls.get_sensitive_words():
            if word in result:
                result = result.replace(word, replacement * len(word))
        
        return result
    
    @classmethod
    def get_matched_words(cls, text):
        """
        获取匹配到的敏感词
        
        Args:
            text: 待检查的文本
            
        Returns:
            list: 匹配到的敏感词列表
        """
        if not text:
            return []
        
        text_lower = text.lower()
        matched = []
        
        for word in cls.get_sensitive_words():
            if word in text_lower:
                matched.append(word)
        
        return matched
    
    @classmethod
    def add_words(cls, words):
        """
        添加敏感词
        
        Args:
            words: 敏感词列表
        """
        current = Setting.get('sensitive_words', '')
        new_words = '\n'.join(words)
        if current:
            new_words = current + '\n' + new_words
        Setting.set('sensitive_words', new_words)
        cls.clear_cache()
    
    @classmethod
    def remove_word(cls, word):
        """
        移除敏感词
        
        Args:
            word: 要移除的敏感词
        """
        current = Setting.get('sensitive_words', '')
        words = [w.strip() for w in current.split('\n') if w.strip() and w.strip().lower() != word.lower()]
        Setting.set('sensitive_words', '\n'.join(words))
        cls.clear_cache()
