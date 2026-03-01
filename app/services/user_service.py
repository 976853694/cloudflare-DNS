"""
用户服务
提供用户相关的业务逻辑，包括用户删除等操作
"""
from typing import Tuple
from app import db
from app.models import User, OperationLog
from app.utils.ip_utils import get_real_ip


class UserService:
    """用户服务类"""
    
    @staticmethod
    def delete_user_cascade(user_id: int, operator_id: int) -> Tuple[bool, str]:
        """
        级联删除用户及其所有关联数据
        
        Args:
            user_id: 要删除的用户ID
            operator_id: 操作者ID
            
        Returns:
            (success: bool, message: str)
        """
        # 1. 验证删除权限
        user = User.query.get(user_id)
        is_valid, error_message = UserService._validate_deletion(user, operator_id)
        if not is_valid:
            return False, error_message
        
        # 保存用户名用于日志
        username = user.username
        
        try:
            # 2. 删除DNS记录（外部服务，不在事务中）
            UserService._delete_dns_records(user)
            
            # 3. 删除关联数据（在事务中）
            UserService._delete_related_data(user)
            
            # 4. 删除用户记录（触发级联删除）
            db.session.delete(user)
            
            # 5. 创建操作日志
            operator = User.query.get(operator_id)
            OperationLog.log(
                user_id=operator_id,
                username=operator.username if operator else None,
                action=OperationLog.ACTION_DELETE,
                target_type='user',
                target_id=user_id,
                detail=f'删除用户: {username}',
                ip_address=get_real_ip()
            )
            
            # 6. 提交事务
            db.session.commit()
            
            return True, '用户删除成功'
            
        except Exception as e:
            db.session.rollback()
            return False, f'删除失败: {str(e)}'
    
    @staticmethod
    def _validate_deletion(user: User, operator_id: int) -> Tuple[bool, str]:
        """
        验证是否可以删除用户
        
        Args:
            user: 要删除的用户对象
            operator_id: 操作者ID
            
        Returns:
            (is_valid: bool, error_message: str)
        """
        # 检查用户是否存在
        if not user:
            return False, '用户不存在'
        
        # 检查是否删除自己
        if user.id == operator_id:
            return False, '不能删除自己的账户'
        
        # 检查是否删除管理员
        if user.role == 'admin':
            return False, '不能删除管理员账户'
        
        return True, ''
    
    @staticmethod
    def _delete_dns_records(user: User) -> None:
        """
        删除用户的所有DNS记录
        
        Args:
            user: 用户对象
        """
        for subdomain in user.subdomains:
            domain = subdomain.domain
            # 获取 DNS 服务
            dns_service = domain.get_dns_service() if domain else None
            zone_id = domain.get_zone_id() if domain else None
            
            if dns_service and zone_id:
                for record in subdomain.records:
                    try:
                        dns_service.delete_record(zone_id, record.cf_record_id)
                    except Exception as e:
                        # 记录错误但继续
                        print(f"[WARN] Failed to delete DNS record {record.cf_record_id}: {e}")
    
    @staticmethod
    def _delete_related_data(user: User) -> None:
        """
        删除用户的关联数据
        
        Args:
            user: 用户对象
        """
        # 大部分关联数据由ORM的CASCADE配置自动删除
        # 包括：subdomains, purchase_records, point_records, user_activities,
        # user_signins, announcement_reads, email_verifications, magic_link_tokens,
        # host_applications, free_plan_applications, domain_transfers (from_user_id),
        # telegram_bindings, telegram_bind_codes, coupon_usages, sent_tickets, ticket_replies
        
        # 注意：received_tickets 的 to_user_id 会自动设置为 NULL（ondelete='SET NULL'）
        pass
