"""
APP版本管理 - 管理端API
"""
from flask import request, jsonify
from flask_jwt_extended import jwt_required
from app import db
from app.models import AppVersion
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden


@admin_bp.route('/app-versions', methods=['GET'])
@jwt_required()
@admin_required
def get_versions():
    """获取版本列表"""
    platform = request.args.get('platform', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    query = AppVersion.query
    
    if platform:
        query = query.filter_by(platform=platform)
    
    query = query.order_by(AppVersion.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'code': 200,
        'data': {
            'versions': [v.to_dict() for v in pagination.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        }
    })


@admin_bp.route('/app-versions', methods=['POST'])
@jwt_required()
@admin_required
@demo_forbidden
def create_version():
    """创建新版本"""
    data = request.get_json()
    
    platform = data.get('platform', '').lower()
    version = data.get('version', '').strip()
    build = data.get('build', 0)
    download_url = data.get('download_url', '').strip()
    
    if platform not in ['android', 'ios']:
        return jsonify({'code': 400, 'message': '无效的平台'}), 400
    
    if not version:
        return jsonify({'code': 400, 'message': '请填写版本号'}), 400
    
    if not build:
        return jsonify({'code': 400, 'message': '请填写构建号'}), 400
    
    if not download_url:
        return jsonify({'code': 400, 'message': '请填写下载地址'}), 400
    
    # 检查版本是否已存在
    existing = AppVersion.query.filter_by(platform=platform, version=version).first()
    if existing:
        return jsonify({'code': 409, 'message': '该版本已存在'}), 409
    
    app_version = AppVersion(
        platform=platform,
        version=version,
        build=build,
        download_url=download_url,
        file_size=data.get('file_size', ''),
        update_log=data.get('update_log', ''),
        force_update=1 if data.get('force_update') else 0,
        min_version=data.get('min_version', ''),
        status=1 if data.get('status', True) else 0
    )
    
    db.session.add(app_version)
    db.session.commit()
    
    return jsonify({
        'code': 201,
        'message': '版本创建成功',
        'data': app_version.to_dict()
    }), 201


@admin_bp.route('/app-versions/<int:version_id>', methods=['GET'])
@jwt_required()
@admin_required
def get_version(version_id):
    """获取版本详情"""
    version = AppVersion.query.get(version_id)
    if not version:
        return jsonify({'code': 404, 'message': '版本不存在'}), 404
    
    return jsonify({
        'code': 200,
        'data': version.to_dict()
    })


@admin_bp.route('/app-versions/<int:version_id>', methods=['PUT'])
@jwt_required()
@admin_required
@demo_forbidden
def update_version(version_id):
    """更新版本"""
    version = AppVersion.query.get(version_id)
    if not version:
        return jsonify({'code': 404, 'message': '版本不存在'}), 404
    
    data = request.get_json()
    
    if 'download_url' in data:
        version.download_url = data['download_url']
    if 'file_size' in data:
        version.file_size = data['file_size']
    if 'update_log' in data:
        version.update_log = data['update_log']
    if 'force_update' in data:
        version.force_update = 1 if data['force_update'] else 0
    if 'min_version' in data:
        version.min_version = data['min_version']
    if 'status' in data:
        version.status = data['status']
    
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '更新成功',
        'data': version.to_dict()
    })


@admin_bp.route('/app-versions/<int:version_id>', methods=['DELETE'])
@jwt_required()
@admin_required
@demo_forbidden
def delete_version(version_id):
    """删除版本"""
    version = AppVersion.query.get(version_id)
    if not version:
        return jsonify({'code': 404, 'message': '版本不存在'}), 404
    
    db.session.delete(version)
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '删除成功'
    })
