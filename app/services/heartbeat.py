"""
站点心跳上报服务 - 定期向官方服务器上报站点基本信息
"""
import uuid
import requests
from urllib.parse import urlparse
from flask import current_app
from sqlalchemy import desc


# 心跳上报地址（使用版本检查同域名）
HEARTBEAT_URL = 'https://gx.6qu.cc/api/site/heartbeat'

# IP 查询服务
IP_SERVICES = [
    'https://api.ipify.org?format=json',
    'https://ifconfig.me/ip',
]


def get_or_create_site_uuid():
    """获取或创建站点 UUID"""
    from app.models import Setting
    
    site_uuid = Setting.get('site_uuid')
    if not site_uuid:
        site_uuid = str(uuid.uuid4())
        Setting.set('site_uuid', site_uuid)
    return site_uuid


def get_server_ip():
    """获取服务器公网 IP"""
    for service_url in IP_SERVICES:
        try:
            resp = requests.get(service_url, timeout=5)
            if resp.status_code == 200:
                # ipify 返回 JSON
                if 'json' in service_url:
                    return resp.json().get('ip', '')
                # 其他服务返回纯文本
                return resp.text.strip()
        except Exception:
            continue
    return ''


def get_site_domain():
    """从 site_url 设置中提取域名"""
    from app.models import Setting
    
    site_url = Setting.get('site_url', '')
    if not site_url:
        return ''
    
    try:
        parsed = urlparse(site_url)
        return parsed.netloc or ''
    except Exception:
        return ''


def get_last_active_time():
    """获取最后活跃时间（最近一次用户登录时间）"""
    from app.models import User
    from app.utils.timezone import now as beijing_now
    
    # 查询最近登录的用户
    last_user = User.query.filter(
        User.last_login_at != None
    ).order_by(desc(User.last_login_at)).first()
    
    if last_user and last_user.last_login_at:
        return last_user.last_login_at.strftime('%Y-%m-%d %H:%M:%S')
    
    # 没有登录记录则返回当前时间
    return beijing_now().strftime('%Y-%m-%d %H:%M:%S')


def collect_heartbeat_data():
    """收集心跳上报数据"""
    from app.models import User
    from flask import current_app
    
    return {
        'uuid': get_or_create_site_uuid(),
        'version': current_app.config.get('APP_VERSION', ''),
        'domain': get_site_domain(),
        'ip': get_server_ip(),
        'last_active': get_last_active_time(),
        'stats': {
            'userCount': User.query.count()
        }
    }


def send_heartbeat():
    """发送心跳请求（静默执行，不输出日志）"""
    try:
        data = collect_heartbeat_data()
        
        resp = requests.post(
            HEARTBEAT_URL,
            json=data,
            timeout=10,
            headers={'Content-Type': 'application/json'}
        )
        
        return resp.status_code == 200
            
    except Exception:
        return False


def test_heartbeat():
    """测试心跳上报（用于调试）"""
    print('=' * 50)
    print('[Heartbeat Test] 开始测试心跳上报...')
    print('=' * 50)
    
    # 1. 收集数据
    print('\n[1] 收集上报数据:')
    try:
        data = collect_heartbeat_data()
        for key, value in data.items():
            print(f'    {key}: {value}')
    except Exception as e:
        print(f'    错误: {e}')
        return False
    
    # 2. 测试上报
    print(f'\n[2] 发送到: {HEARTBEAT_URL}')
    try:
        resp = requests.post(
            HEARTBEAT_URL,
            json=data,
            timeout=10,
            headers={'Content-Type': 'application/json'}
        )
        print(f'    状态码: {resp.status_code}')
        print(f'    响应: {resp.text[:200]}')
        
        if resp.status_code == 200:
            print('\n[结果] ✓ 心跳上报成功!')
            return True
        else:
            print(f'\n[结果] ✗ 上报失败，状态码: {resp.status_code}')
            return False
            
    except requests.exceptions.Timeout:
        print('    错误: 请求超时')
        print('\n[结果] ✗ 上报失败，连接超时')
        return False
    except requests.exceptions.ConnectionError as e:
        print(f'    错误: 无法连接服务器')
        print('\n[结果] ✗ 上报失败，无法连接到心跳服务器')
        return False
    except Exception as e:
        print(f'    错误: {e}')
        print('\n[结果] ✗ 上报失败')
        return False
