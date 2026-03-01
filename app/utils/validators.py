import re
import ipaddress


def validate_email(email):
    if not email or len(email) > 100:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_username(username):
    if not username or len(username) < 3 or len(username) > 20:
        return False
    pattern = r'^[a-zA-Z0-9_]+$'
    return bool(re.match(pattern, username))


def validate_password(password, strict=False):
    """
    验证密码格式
    
    Args:
        password: 密码字符串
        strict: 是否启用严格模式（要求包含大小写、数字、特殊字符）
        
    Returns:
        bool: 是否通过验证
    """
    if not password or len(password) < 6 or len(password) > 32:
        return False
    
    if strict:
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
        
        # 至少满足3项
        score = sum([has_upper, has_lower, has_digit, has_special])
        return score >= 3
    
    return True


def get_password_strength(password):
    """
    获取密码强度
    
    Args:
        password: 密码字符串
        
    Returns:
        dict: {level: 'weak'|'medium'|'strong', score: 0-4, tips: []}
    """
    if not password:
        return {'level': 'weak', 'score': 0, 'tips': ['请输入密码']}
    
    tips = []
    score = 0
    
    # 长度检查
    if len(password) >= 8:
        score += 1
    else:
        tips.append('建议密码长度至少8位')
    
    # 大写字母
    if any(c.isupper() for c in password):
        score += 1
    else:
        tips.append('建议包含大写字母')
    
    # 小写字母
    if any(c.islower() for c in password):
        score += 1
    else:
        tips.append('建议包含小写字母')
    
    # 数字
    if any(c.isdigit() for c in password):
        score += 1
    else:
        tips.append('建议包含数字')
    
    # 特殊字符
    if any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
        score += 1
    else:
        tips.append('建议包含特殊字符')
    
    if score <= 2:
        level = 'weak'
    elif score <= 3:
        level = 'medium'
    else:
        level = 'strong'
    
    return {'level': level, 'score': score, 'tips': tips}


def validate_subdomain_name(name, min_len=3, max_len=30):
    if not name or len(name) < min_len or len(name) > max_len:
        return False
    pattern = r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$'
    if len(name) == 1:
        pattern = r'^[a-z0-9]$'
    if not re.match(pattern, name):
        return False
    if '--' in name:
        return False
    return True


def validate_ipv4(ip):
    try:
        ipaddress.IPv4Address(ip)
        return True
    except ipaddress.AddressValueError:
        return False


def validate_ipv6(ip):
    try:
        ipaddress.IPv6Address(ip)
        return True
    except ipaddress.AddressValueError:
        return False


def validate_domain(domain):
    if not domain or len(domain) > 253:
        return False
    pattern = r'^([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    return bool(re.match(pattern, domain))


def validate_record_content(record_type, content):
    if not content:
        return False
    
    record_type = record_type.upper()
    
    if record_type == 'A':
        return validate_ipv4(content)
    
    elif record_type == 'AAAA':
        return validate_ipv6(content)
    
    elif record_type == 'CNAME':
        return validate_domain(content) or content == '@'
    
    elif record_type == 'TXT':
        return len(content) <= 255
    
    elif record_type == 'MX':
        return validate_domain(content)
    
    return False
