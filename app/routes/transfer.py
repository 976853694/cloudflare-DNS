"""
域名转移用户端路由
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.transfer_service import TransferService

transfer_bp = Blueprint('transfer', __name__)


@transfer_bp.route('/api/domain/transfer/config', methods=['GET'])
@jwt_required()
def get_config():
    """获取转移配置"""
    try:
        config = TransferService.get_config()
        return jsonify({'code': 200, 'data': config})
    except Exception as e:
        return jsonify({'code': 500, 'message': '获取配置失败'}), 500


@transfer_bp.route('/api/domain/transfer/initiate', methods=['POST'])
@jwt_required()
def initiate_transfer():
    """发起转移请求"""
    user_id = int(get_jwt_identity())  # 转换为整数
    data = request.get_json() or {}
    
    subdomain_id = data.get('subdomain_id')
    to_username = data.get('to_username', '').strip()
    remark = data.get('remark')
    if remark:
        remark = remark.strip() or None
    else:
        remark = None
    
    if not subdomain_id:
        return jsonify({'code': 400, 'message': '请选择要转移的域名'}), 400
    
    if not to_username:
        return jsonify({'code': 400, 'message': '请输入目标用户名'}), 400
    
    try:
        result = TransferService.initiate_transfer(
            user_id=user_id,
            subdomain_id=subdomain_id,
            to_username=to_username,
            remark=remark
        )
        return jsonify({
            'code': 200, 
            'data': result, 
            'message': '验证码已发送到您的邮箱'
        })
    except ValueError as e:
        error_msg = str(e)
        if '|' in error_msg:
            _, msg = error_msg.split('|', 1)
        else:
            msg = error_msg
        return jsonify({'code': 400, 'message': msg}), 400
    except Exception as e:
        return jsonify({'code': 500, 'message': '发起转移失败'}), 500


@transfer_bp.route('/api/domain/transfer/verify', methods=['POST'])
@jwt_required()
def verify_transfer():
    """验证并确认转移"""
    user_id = int(get_jwt_identity())  # 转换为整数
    data = request.get_json() or {}
    
    transfer_id = data.get('transfer_id')
    verify_code = data.get('verify_code', '').strip()
    
    if not transfer_id:
        return jsonify({'code': 400, 'message': '转移记录ID不能为空'}), 400
    
    if not verify_code:
        return jsonify({'code': 400, 'message': '请输入验证码'}), 400
    
    try:
        result = TransferService.verify_transfer(
            user_id=user_id,
            transfer_id=transfer_id,
            verify_code=verify_code
        )
        return jsonify({
            'code': 200, 
            'data': result, 
            'message': '域名转移成功'
        })
    except ValueError as e:
        error_msg = str(e)
        if '|' in error_msg:
            _, msg = error_msg.split('|', 1)
        else:
            msg = error_msg
        return jsonify({'code': 400, 'message': msg}), 400
    except Exception as e:
        return jsonify({'code': 500, 'message': '验证转移失败'}), 500


@transfer_bp.route('/api/domain/transfer/cancel', methods=['POST'])
@jwt_required()
def cancel_transfer():
    """取消转移请求"""
    user_id = int(get_jwt_identity())  # 转换为整数
    data = request.get_json() or {}
    
    transfer_id = data.get('transfer_id')
    
    if not transfer_id:
        return jsonify({'code': 400, 'message': '转移记录ID不能为空'}), 400
    
    try:
        TransferService.cancel_transfer(user_id=user_id, transfer_id=transfer_id)
        return jsonify({'code': 200, 'message': '转移已取消'})
    except ValueError as e:
        error_msg = str(e)
        if '|' in error_msg:
            _, msg = error_msg.split('|', 1)
        else:
            msg = error_msg
        return jsonify({'code': 400, 'message': msg}), 400
    except Exception as e:
        return jsonify({'code': 500, 'message': '取消转移失败'}), 500


@transfer_bp.route('/api/domain/transfer/resend', methods=['POST'])
@jwt_required()
def resend_code():
    """重发验证码"""
    user_id = int(get_jwt_identity())  # 转换为整数
    data = request.get_json() or {}
    
    transfer_id = data.get('transfer_id')
    
    if not transfer_id:
        return jsonify({'code': 400, 'message': '转移记录ID不能为空'}), 400
    
    try:
        result = TransferService.resend_code(user_id=user_id, transfer_id=transfer_id)
        return jsonify({
            'code': 200, 
            'data': result, 
            'message': '验证码已重新发送'
        })
    except ValueError as e:
        error_msg = str(e)
        if '|' in error_msg:
            _, msg = error_msg.split('|', 1)
        else:
            msg = error_msg
        return jsonify({'code': 400, 'message': msg}), 400
    except Exception as e:
        return jsonify({'code': 500, 'message': '重发验证码失败'}), 500


@transfer_bp.route('/api/domain/transfer/history', methods=['GET'])
@jwt_required()
def get_history():
    """获取转移记录"""
    user_id = int(get_jwt_identity())  # 转换为整数
    
    direction = request.args.get('type', 'all')
    status = request.args.get('status', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # 限制每页数量
    per_page = min(per_page, 100)
    
    try:
        data = TransferService.get_user_transfers(
            user_id=user_id,
            direction=direction,
            status=status,
            page=page,
            per_page=per_page
        )
        return jsonify({'code': 200, 'data': data})
    except Exception as e:
        return jsonify({'code': 500, 'message': '获取转移记录失败'}), 500
