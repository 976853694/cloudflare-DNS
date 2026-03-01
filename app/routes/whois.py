"""
WHOIS 查询路由
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.whois_service import WhoisService
from app.utils.ip_utils import get_real_ip

whois_bp = Blueprint('whois', __name__)


@whois_bp.route('/api/whois/<path:domain>', methods=['GET'])
@jwt_required(optional=True)
def query_whois(domain):
    """
    查询域名 WHOIS 信息
    
    Args:
        domain: 域名
        
    Returns:
        JSON: WHOIS 信息或错误消息
    """
    # 获取用户标识（用于频率限制）
    identity = get_jwt_identity()
    if identity:
        identifier = f"user:{identity}"
    else:
        identifier = f"ip:{get_real_ip()}"
    
    try:
        result = WhoisService.query(domain, identifier)
        return jsonify({
            'code': 200,
            'data': result
        })
    
    except ValueError as e:
        # 域名格式无效
        return jsonify({
            'code': 400,
            'message': str(e)
        }), 400
    
    except PermissionError as e:
        # 频率限制
        return jsonify({
            'code': 429,
            'message': str(e),
            'data': {
                'retry_after': WhoisService.RATE_WINDOW
            }
        }), 429
    
    except LookupError as e:
        # 域名未注册
        return jsonify({
            'code': 404,
            'message': str(e)
        }), 404
    
    except Exception as e:
        # 其他错误
        return jsonify({
            'code': 500,
            'message': str(e) or 'WHOIS 查询服务暂时不可用'
        }), 500
