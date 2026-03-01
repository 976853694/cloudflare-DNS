"""IP地址工具函数"""
from flask import request


def get_real_ip():
    """
    获取客户端真实IP地址
    
    优先级:
    1. X-Forwarded-For (多级代理时取第一个)
    2. X-Real-IP (Nginx常用)
    3. CF-Connecting-IP (Cloudflare)
    4. request.remote_addr (直连)
    """
    # X-Forwarded-For 可能包含多个IP，取第一个（最原始的客户端IP）
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        # 格式: client, proxy1, proxy2
        return forwarded_for.split(',')[0].strip()
    
    # X-Real-IP (Nginx)
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip.strip()
    
    # CF-Connecting-IP (Cloudflare)
    cf_ip = request.headers.get('CF-Connecting-IP')
    if cf_ip:
        return cf_ip.strip()
    
    # 直连
    return request.remote_addr or '0.0.0.0'
