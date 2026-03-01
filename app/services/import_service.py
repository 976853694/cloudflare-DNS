"""
批量导入服务
支持从CSV导入用户、域名等数据
"""
import csv
import io
from decimal import Decimal
from app import db
from app.models import User, Domain, Subdomain, RedeemCode
from app.utils.validators import validate_email, validate_username, validate_password


class ImportService:
    """批量导入服务"""
    
    @staticmethod
    def parse_csv(file_content, has_header=True):
        """
        解析CSV内容
        
        Args:
            file_content: CSV文件内容（字符串或bytes）
            has_header: 是否有表头
            
        Returns:
            list: 解析后的行列表
        """
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8-sig')
        
        reader = csv.reader(io.StringIO(file_content))
        rows = list(reader)
        
        if has_header and rows:
            headers = rows[0]
            data = []
            for row in rows[1:]:
                if row:  # 跳过空行
                    data.append(dict(zip(headers, row)))
            return data
        
        return rows
    
    @staticmethod
    def import_users(csv_content, default_password='123456'):
        """
        批量导入用户
        
        CSV格式: username,email,password(可选),balance(可选)
        
        Args:
            csv_content: CSV内容
            default_password: 默认密码
            
        Returns:
            dict: {success: int, failed: int, errors: list}
        """
        result = {'success': 0, 'failed': 0, 'errors': []}
        
        try:
            rows = ImportService.parse_csv(csv_content)
        except Exception as e:
            result['errors'].append(f'CSV解析失败: {str(e)}')
            return result
        
        for i, row in enumerate(rows, start=2):  # 从第2行开始（跳过表头）
            try:
                username = row.get('username', '').strip()
                email = row.get('email', '').strip().lower()
                password = row.get('password', '').strip() or default_password
                balance = row.get('balance', '0').strip()
                
                # 验证
                if not username or not email:
                    result['errors'].append(f'第{i}行: 用户名或邮箱为空')
                    result['failed'] += 1
                    continue
                
                if not validate_username(username):
                    result['errors'].append(f'第{i}行: 用户名格式不正确 ({username})')
                    result['failed'] += 1
                    continue
                
                if not validate_email(email):
                    result['errors'].append(f'第{i}行: 邮箱格式不正确 ({email})')
                    result['failed'] += 1
                    continue
                
                # 检查重复
                if User.query.filter_by(username=username).first():
                    result['errors'].append(f'第{i}行: 用户名已存在 ({username})')
                    result['failed'] += 1
                    continue
                
                if User.query.filter_by(email=email).first():
                    result['errors'].append(f'第{i}行: 邮箱已存在 ({email})')
                    result['failed'] += 1
                    continue
                
                # 创建用户
                user = User(
                    username=username,
                    email=email,
                    balance=Decimal(balance) if balance else Decimal('0')
                )
                user.set_password(password)
                db.session.add(user)
                result['success'] += 1
                
            except Exception as e:
                result['errors'].append(f'第{i}行: {str(e)}')
                result['failed'] += 1
        
        if result['success'] > 0:
            db.session.commit()
        
        return result
    
    @staticmethod
    def import_redeem_codes(csv_content):
        """
        批量导入卡密
        
        CSV格式: code,amount
        
        Args:
            csv_content: CSV内容
            
        Returns:
            dict: {success: int, failed: int, errors: list}
        """
        result = {'success': 0, 'failed': 0, 'errors': []}
        
        try:
            rows = ImportService.parse_csv(csv_content)
        except Exception as e:
            result['errors'].append(f'CSV解析失败: {str(e)}')
            return result
        
        for i, row in enumerate(rows, start=2):
            try:
                code = row.get('code', '').strip().upper()
                amount = row.get('amount', '0').strip()
                
                if not code:
                    result['errors'].append(f'第{i}行: 卡密为空')
                    result['failed'] += 1
                    continue
                
                if RedeemCode.query.filter_by(code=code).first():
                    result['errors'].append(f'第{i}行: 卡密已存在 ({code})')
                    result['failed'] += 1
                    continue
                
                redeem_code = RedeemCode(
                    code=code,
                    amount=Decimal(amount)
                )
                db.session.add(redeem_code)
                result['success'] += 1
                
            except Exception as e:
                result['errors'].append(f'第{i}行: {str(e)}')
                result['failed'] += 1
        
        if result['success'] > 0:
            db.session.commit()
        
        return result
    
    @staticmethod
    def export_users_csv():
        """
        导出用户为CSV
        
        Returns:
            str: CSV内容
        """
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 表头
        writer.writerow(['id', 'username', 'email', 'role', 'status', 'balance', 'created_at'])
        
        # 数据
        users = User.query.order_by(User.id).all()
        for user in users:
            writer.writerow([
                user.id,
                user.username,
                user.email,
                user.role,
                user.status,
                float(user.balance),
                user.created_at.isoformat() if user.created_at else ''
            ])
        
        return output.getvalue()
    
    @staticmethod
    def export_subdomains_csv():
        """
        导出二级域名为CSV
        
        Returns:
            str: CSV内容
        """
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 表头
        writer.writerow(['id', 'user_id', 'username', 'full_name', 'status', 'expires_at', 'created_at'])
        
        # 数据
        subdomains = Subdomain.query.order_by(Subdomain.id).all()
        for sub in subdomains:
            writer.writerow([
                sub.id,
                sub.user_id,
                sub.user.username if sub.user else '',
                sub.full_name,
                sub.status,
                sub.expires_at.isoformat() if sub.expires_at else '',
                sub.created_at.isoformat() if sub.created_at else ''
            ])
        
        return output.getvalue()
