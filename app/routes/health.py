"""
健康检查路由
用于负载均衡器和监控系统探测
"""
from flask import Blueprint, jsonify
from app import db

health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
def health_check():
    """
    健康检查端点
    返回应用健康状态
    """
    health_status = {
        'status': 'healthy',
        'checks': {}
    }
    
    # 检查数据库连接
    try:
        db.session.execute(db.text('SELECT 1'))
        health_status['checks']['database'] = 'ok'
    except Exception as e:
        health_status['checks']['database'] = f'error: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    status_code = 200 if health_status['status'] == 'healthy' else 503
    return jsonify(health_status), status_code


@health_bp.route('/health/ready', methods=['GET'])
def readiness_check():
    """
    就绪检查端点
    检查应用是否准备好接收流量
    """
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify({'status': 'ready'}), 200
    except Exception:
        return jsonify({'status': 'not ready'}), 503


@health_bp.route('/health/live', methods=['GET'])
def liveness_check():
    """
    存活检查端点
    检查应用进程是否存活
    """
    return jsonify({'status': 'alive'}), 200
