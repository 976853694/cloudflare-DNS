from flask import Blueprint, request, jsonify
from app.services.email import EmailService
from app.routes.admin.decorators import admin_required

bp = Blueprint('admin_email_test', __name__, url_prefix='/api/admin/email')


@bp.route('/test-connection', methods=['POST'])
@admin_required
def test_connection():
    """测试邮件服务连接"""
    success, message = EmailService.test_connection()
    
    if success:
        return jsonify({
            'success': True,
            'message': message
        })
    else:
        return jsonify({
            'success': False,
            'message': message
        }), 400


@bp.route('/send-test', methods=['POST'])
@admin_required
def send_test():
    """发送测试邮件"""
    data = request.get_json()
    to_email = data.get('to_email', '').strip()
    
    if not to_email:
        return jsonify({
            'success': False,
            'message': '请输入测试邮箱地址'
        }), 400
    
    success, message = EmailService.send_test_email(to_email)
    
    if success:
        return jsonify({
            'success': True,
            'message': message
        })
    else:
        return jsonify({
            'success': False,
            'message': message
        }), 400
