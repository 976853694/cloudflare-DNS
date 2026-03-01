"""
管理员数据导入导出路由
"""
from flask import request, jsonify, Response
from flask_jwt_extended import get_jwt_identity
from app.models import User, OperationLog
from app.services.import_service import ImportService
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden
from app.utils.ip_utils import get_real_ip


@admin_bp.route('/import/users', methods=['POST'])
@admin_required
@demo_forbidden
def import_users():
    """批量导入用户"""
    data = request.get_json()
    csv_content = data.get('csv_content', '')
    default_password = data.get('default_password', '123456')
    
    if not csv_content:
        return jsonify({'code': 400, 'message': '请提供CSV数据'}), 400
    
    result = ImportService.import_users(csv_content, default_password)
    
    # 记录操作日志
    current_user_id = int(get_jwt_identity())
    admin = User.query.get(current_user_id)
    OperationLog.log(
        user_id=current_user_id,
        username=admin.username if admin else None,
        action=OperationLog.ACTION_CREATE,
        target_type='user',
        detail=f'批量导入用户: 成功{result["success"]}个, 失败{result["failed"]}个',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': f'导入完成: 成功{result["success"]}个, 失败{result["failed"]}个',
        'data': result
    })


@admin_bp.route('/import/redeem-codes', methods=['POST'])
@admin_required
@demo_forbidden
def import_redeem_codes():
    """批量导入卡密"""
    data = request.get_json()
    csv_content = data.get('csv_content', '')
    
    if not csv_content:
        return jsonify({'code': 400, 'message': '请提供CSV数据'}), 400
    
    result = ImportService.import_redeem_codes(csv_content)
    
    # 记录操作日志
    current_user_id = int(get_jwt_identity())
    admin = User.query.get(current_user_id)
    OperationLog.log(
        user_id=current_user_id,
        username=admin.username if admin else None,
        action=OperationLog.ACTION_CREATE,
        target_type='redeem_code',
        detail=f'批量导入卡密: 成功{result["success"]}个, 失败{result["failed"]}个',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': f'导入完成: 成功{result["success"]}个, 失败{result["failed"]}个',
        'data': result
    })


@admin_bp.route('/export/users', methods=['GET'])
@admin_required
def export_users():
    """导出用户CSV"""
    csv_content = ImportService.export_users_csv()
    
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=users.csv'}
    )


@admin_bp.route('/export/subdomains', methods=['GET'])
@admin_required
def export_subdomains():
    """导出二级域名CSV"""
    csv_content = ImportService.export_subdomains_csv()
    
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=subdomains.csv'}
    )
