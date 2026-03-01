"""
手机号绑定验证服务
处理手机绑定相关的业务逻辑
"""
from app.models import Setting


class PhoneBindingService:
    """手机号绑定验证服务"""
    
    @staticmethod
    def is_phone_binding_required() -> bool:
        """
        检查系统是否要求强制绑定手机号
        
        Returns:
            bool: True 表示需要强制绑定，False 表示不需要
        """
        return Setting.get('require_phone_binding', '0') == '1'
    
    @staticmethod
    def check_purchase_allowed(user) -> tuple:
        """
        检查用户是否允许购买
        
        Args:
            user: 用户对象
            
        Returns:
            tuple: (allowed: bool, error_message: str or None)
        """
        # 如果系统未启用强制绑定，直接允许
        if not PhoneBindingService.is_phone_binding_required():
            return True, None
        
        # 检查用户是否已绑定手机号
        if user.phone:
            return True, None
        
        # 未绑定手机号，拒绝购买
        return False, '请先绑定手机号后再进行购买'
    
    @staticmethod
    def mask_phone(phone: str) -> str:
        """
        手机号脱敏处理
        将手机号中间4位替换为星号
        
        Args:
            phone: 原始手机号
            
        Returns:
            str: 脱敏后的手机号，如 138****1234
        """
        if not phone:
            return None
        
        # 处理非标准长度的手机号
        if len(phone) < 7:
            return phone
        
        # 标准11位手机号：保留前3位和后4位
        if len(phone) == 11:
            return phone[:3] + '****' + phone[-4:]
        
        # 其他长度：保留前3位和后4位，中间用星号填充
        return phone[:3] + '****' + phone[-4:]
    
    @staticmethod
    def get_phone_binding_info(user) -> dict:
        """
        获取用户手机绑定信息
        
        Args:
            user: 用户对象
            
        Returns:
            dict: 包含手机绑定状态的字典
        """
        return {
            'phone': PhoneBindingService.mask_phone(user.phone) if user.phone else None,
            'phone_bound': bool(user.phone),
            'require_phone_binding': PhoneBindingService.is_phone_binding_required()
        }
