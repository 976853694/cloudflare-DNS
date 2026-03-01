"""
版本强制更新检查中间件
"""
import requests
import time
from flask import request, redirect, url_for, render_template_string
from functools import wraps

# 缓存版本检查结果，避免每次请求都调用远程 API
_version_cache = {
    'force_update': False,
    'latest_version': None,
    'download_url': None,
    'changelog_html': None,
    'last_check': 0,
    'cache_ttl': 600  # 缓存 60 分钟（测试时可以改短）
}


def check_force_update(app):
    """检查是否需要强制更新（带缓存）"""
    global _version_cache
    
    current_time = time.time()
    
    # 如果缓存未过期，直接返回缓存结果
    if current_time - _version_cache['last_check'] < _version_cache['cache_ttl']:
        print(f"[VERSION CHECK] Using cache: force_update={_version_cache['force_update']}")
        return _version_cache['force_update']
    
    try:
        version_check_url = app.config.get('VERSION_CHECK_URL')
        if not version_check_url:
            print("[VERSION CHECK] No VERSION_CHECK_URL configured")
            return False
        
        current_version = app.config.get('APP_VERSION', '0.0.0')
        print(f"[VERSION CHECK] Checking {version_check_url}, current={current_version}")
        
        response = requests.get(version_check_url, timeout=5)
        if response.status_code != 200:
            print(f"[VERSION CHECK] API returned {response.status_code}")
            return False
        
        data = response.json()
        print(f"[VERSION CHECK] API response: {data}")
        
        # 检查是否有版本信息
        if not data.get('hasVersion'):
            _version_cache['force_update'] = False
            _version_cache['last_check'] = current_time
            return False
        
        remote_version = data.get('version', '0.0.0')
        force_update = data.get('forceUpdate', False)
        
        # 比较版本号
        version_compare = compare_versions(remote_version, current_version)
        print(f"[VERSION CHECK] remote={remote_version}, current={current_version}, compare={version_compare}, forceUpdate={force_update}")
        
        if version_compare > 0 and force_update:
            _version_cache['force_update'] = True
            _version_cache['latest_version'] = remote_version
            _version_cache['download_url'] = data.get('downloadUrl', '')
            _version_cache['changelog_html'] = data.get('changelogHtml', '')
            print("[VERSION CHECK] Force update required!")
        else:
            _version_cache['force_update'] = False
        
        _version_cache['last_check'] = current_time
        return _version_cache['force_update']
        
    except Exception as e:
        # 请求失败时不阻止访问
        print(f"[VERSION CHECK] Error: {e}")
        return False


def compare_versions(v1, v2):
    """比较版本号，v1 > v2 返回 1，v1 < v2 返回 -1，相等返回 0"""
    parts1 = [int(x) for x in str(v1).split('.')]
    parts2 = [int(x) for x in str(v2).split('.')]
    
    max_len = max(len(parts1), len(parts2))
    parts1.extend([0] * (max_len - len(parts1)))
    parts2.extend([0] * (max_len - len(parts2)))
    
    for i in range(max_len):
        if parts1[i] > parts2[i]:
            return 1
        elif parts1[i] < parts2[i]:
            return -1
    return 0


def get_force_update_page(app):
    """返回强制更新页面（使用内联样式，避免外部资源加载问题）"""
    return render_template_string('''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>系统需要更新</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .card {
            background: white;
            border-radius: 16px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            max-width: 420px;
            width: 100%;
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #ef4444 0%, #f97316 100%);
            padding: 20px 24px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .header svg { width: 28px; height: 28px; color: white; }
        .header h1 { color: white; font-size: 20px; font-weight: 600; }
        .content { padding: 24px; }
        .alert {
            background: #fef2f2;
            border: 1px solid #fecaca;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 20px;
        }
        .alert p { color: #dc2626; font-weight: 500; font-size: 14px; line-height: 1.5; }
        .info-row {
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid #f3f4f6;
        }
        .info-label { color: #6b7280; font-size: 14px; }
        .info-value { font-weight: 500; color: #374151; font-size: 14px; }
        .info-value.highlight { color: #dc2626; font-weight: 600; }
        .changelog {
            margin: 20px 0;
        }
        .changelog h3 { font-size: 14px; font-weight: 500; color: #374151; margin-bottom: 8px; }
        .changelog-content {
            max-height: 180px;
            overflow-y: auto;
            padding: 12px;
            background: #f9fafb;
            border-radius: 8px;
            font-size: 13px;
            color: #4b5563;
            line-height: 1.6;
        }
        .changelog-content::-webkit-scrollbar { width: 6px; }
        .changelog-content::-webkit-scrollbar-track { background: #e5e7eb; border-radius: 3px; }
        .changelog-content::-webkit-scrollbar-thumb { background: #9ca3af; border-radius: 3px; }
        .btn {
            display: block;
            width: 100%;
            padding: 14px 20px;
            background: linear-gradient(135deg, #dc2626 0%, #ea580c 100%);
            color: white;
            text-align: center;
            text-decoration: none;
            border-radius: 10px;
            font-weight: 600;
            font-size: 15px;
            transition: transform 0.2s, box-shadow 0.2s;
            margin-top: 8px;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px -5px rgba(220, 38, 38, 0.4);
        }
        .no-url { text-align: center; color: #6b7280; font-size: 14px; padding: 10px 0; }
        @media (prefers-color-scheme: dark) {
            body { background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); }
            .card { background: #1f2937; }
            .alert { background: rgba(127, 29, 29, 0.3); border-color: rgba(185, 28, 28, 0.5); }
            .alert p { color: #fca5a5; }
            .info-row { border-color: #374151; }
            .info-label { color: #9ca3af; }
            .info-value { color: #e5e7eb; }
            .changelog h3 { color: #e5e7eb; }
            .changelog-content { background: rgba(55, 65, 81, 0.5); color: #d1d5db; }
            .changelog-content::-webkit-scrollbar-track { background: #374151; }
            .changelog-content::-webkit-scrollbar-thumb { background: #6b7280; }
            .no-url { color: #9ca3af; }
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="header">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
            </svg>
            <h1>系统需要更新</h1>
        </div>
        <div class="content">
            <div class="alert">
                <p>检测到新版本需要强制更新，请更新系统后继续操作。</p>
            </div>
            
            <div class="info-row">
                <span class="info-label">当前版本</span>
                <span class="info-value">v{{ current_version }}</span>
            </div>
            <div class="info-row">
                <span class="info-label">最新版本</span>
                <span class="info-value highlight">v{{ latest_version }}</span>
            </div>
            
            {% if changelog_html %}
            <div class="changelog">
                <h3>更新日志</h3>
                <div class="changelog-content">{{ changelog_html | safe }}</div>
            </div>
            {% endif %}
            
            {% if download_url %}
            <a href="{{ download_url }}" target="_blank" class="btn">立即更新</a>
            {% else %}
            <p class="no-url">请联系管理员获取更新</p>
            {% endif %}
        </div>
    </div>
</body>
</html>
    ''', 
    current_version=app.config.get('APP_VERSION', ''),
    latest_version=_version_cache.get('latest_version', ''),
    download_url=_version_cache.get('download_url', ''),
    changelog_html=_version_cache.get('changelog_html', ''))


def init_version_check(app):
    """初始化版本检查中间件"""
    
    @app.before_request
    def check_version_before_request():
        path = request.path
        
        # 静态资源直接放行（必须最先检查）
        if path.startswith('/static'):
            return None
        
        # 排除的路径
        excluded_paths = [
            '/api/admin/check-update',  # 版本检查 API
            '/user',                    # 用户页面
            '/api/user',                # 用户 API
            '/api/auth',                # 认证 API
            '/api/open',                # 开放 API
            '/login',                   # 登录页
            '/register',                # 注册页
            '/health',                  # 健康检查
            '/favicon',                 # 图标
        ]
        
        # 检查是否是排除的路径
        for excluded in excluded_paths:
            if path.startswith(excluded):
                return None
        
        # 首页不检查
        if path == '/':
            return None
        
        # 只检查 /admin 开头的路径
        if not path.startswith('/admin') and not path.startswith('/api/admin'):
            return None
        
        print(f"[VERSION CHECK MIDDLEWARE] Checking path: {path}")
        
        # 检查是否需要强制更新
        force_update = check_force_update(app)
        
        print(f"[VERSION CHECK MIDDLEWARE] Path: {path}, Force update: {force_update}")
        
        if force_update:
            print(f"[VERSION CHECK MIDDLEWARE] Blocking path: {path}")
            # API 请求返回 JSON
            if path.startswith('/api/'):
                return {
                    'code': 426,
                    'message': '系统需要强制更新，请更新后继续操作',
                    'data': {
                        'force_update': True,
                        'latest_version': _version_cache.get('latest_version'),
                        'download_url': _version_cache.get('download_url')
                    }
                }, 426
            # 页面请求返回更新页面
            else:
                return get_force_update_page(app), 426
        
        return None
