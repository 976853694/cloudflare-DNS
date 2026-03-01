"""
APP更新检查接口
"""
from flask import Blueprint, request, jsonify
from app import db
from app.models import AppVersion

app_update_bp = Blueprint('app_update', __name__)


@app_update_bp.route('/check-update', methods=['GET'])
def check_update():
    """检查APP更新"""
    platform = request.args.get('platform', '').lower()
    current_version = request.args.get('version', '')
    
    if platform not in ['android', 'ios']:
        return jsonify({'code': 400, 'message': '无效的平台参数'}), 400
    
    if not current_version:
        return jsonify({'code': 400, 'message': '请提供当前版本号'}), 400
    
    # 获取最新版本
    latest = AppVersion.get_latest(platform)
    
    if not latest:
        return jsonify({
            'code': 200,
            'data': {
                'has_update': False
            }
        })
    
    # 比较版本
    has_update = AppVersion.compare_version(latest.version, current_version) > 0
    
    # 判断是否强制更新
    force_update = False
    if has_update and latest.min_version:
        # 当前版本低于最低支持版本时强制更新
        force_update = AppVersion.compare_version(latest.min_version, current_version) > 0
    
    if not has_update:
        return jsonify({
            'code': 200,
            'data': {
                'has_update': False
            }
        })
    
    return jsonify({
        'code': 200,
        'data': {
            'has_update': True,
            'force_update': force_update or latest.force_update == 1,
            'latest_version': latest.version,
            'latest_build': latest.build,
            'download_url': latest.download_url,
            'update_log': latest.update_log,
            'file_size': latest.file_size,
            'publish_time': latest.created_at.strftime('%Y-%m-%d') if latest.created_at else None
        }
    })


@app_update_bp.route('/download/<int:version_id>', methods=['GET'])
def download(version_id):
    """记录下载并重定向到下载地址"""
    version = AppVersion.query.get(version_id)
    if not version or version.status != 1:
        return jsonify({'code': 404, 'message': '版本不存在'}), 404
    
    # 增加下载计数
    version.download_count += 1
    db.session.commit()
    
    # 重定向到下载地址
    from flask import redirect
    return redirect(version.download_url)
