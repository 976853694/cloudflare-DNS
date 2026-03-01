"""
短信验证码模型
"""
from datetime import datetime, timedelta
from app import db
from app.utils.timezone import now as beijing_now


class SmsVerification(db.Model):
    """短信验证码"""
    __tablename__ = 'sms_verifications'
    
    # 验证码类型
    TYPE_LOGIN = 'login'           # 登录/注册
    TYPE_CHANGE_PHONE = 'change'   # 修改手机号
    TYPE_RESET_PWD = 'reset'       # 重置密码
    TYPE_BIND_PHONE = 'bind'       # 绑定新手机号
    TYPE_VERIFY_PHONE = 'verify'   # 验证绑定手机号
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    phone = db.Column(db.String(20), nullable=False, index=True)
    code = db.Column(db.String(10), nullable=False)
    type = db.Column(db.String(20), nullable=False, default='login')
    user_id = db.Column(db.Integer, nullable=True)  # 关联用户（可选）
    used = db.Column(db.SmallInteger, default=0, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    
    @classmethod
    def create(cls, phone, code, v_type='login', user_id=None, expire_minutes=5):
        """创建验证码记录"""
        # 删除该手机号该类型的旧验证码
        cls.query.filter_by(phone=phone, type=v_type, used=0).delete()
        
        verification = cls(
            phone=phone,
            code=code,
            type=v_type,
            user_id=user_id,
            expires_at=beijing_now() + timedelta(minutes=expire_minutes)
        )
        db.session.add(verification)
        db.session.commit()
        return verification
    
    @classmethod
    def verify(cls, phone, code, v_type='login'):
        """验证验证码"""
        verification = cls.query.filter_by(
            phone=phone,
            code=code,
            type=v_type,
            used=0
        ).first()
        
        if not verification:
            return False, '验证码错误'
        
        if verification.expires_at < beijing_now():
            return False, '验证码已过期'
        
        # 标记为已使用
        verification.used = 1
        db.session.commit()
        
        return True, verification
    
    @classmethod
    def can_send(cls, phone, v_type='login', interval_seconds=60):
        """检查是否可以发送验证码（防止频繁发送）"""
        last = cls.query.filter_by(phone=phone, type=v_type).order_by(
            cls.created_at.desc()
        ).first()
        
        if not last:
            return True, 0
        
        elapsed = (beijing_now() - last.created_at).total_seconds()
        if elapsed < interval_seconds:
            return False, int(interval_seconds - elapsed)
        
        return True, 0
    
    @classmethod
    def cleanup_expired(cls):
        """清理过期的验证码"""
        cls.query.filter(cls.expires_at < beijing_now()).delete()
        db.session.commit()
