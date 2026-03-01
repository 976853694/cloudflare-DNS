"""
管理员定时任务管理路由
"""
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from app.models import User, CronLog, Setting
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden
from app.services.cron_tasks import CronTaskService, CRON_TASKS
from app.utils.ip_utils import get_real_ip


@admin_bp.route('/cron/tasks', methods=['GET'])
@admin_required
def get_cron_tasks():
    """获取定时任务列表"""
    locale = request.args.get('locale', 'zh')
    tasks = CronTaskService.get_task_list(locale=locale)
    
    # 获取Cron URL
    secret_key = CronTaskService.get_secret_key()
    site_url = Setting.get('site_url', '')
    base_url = site_url.rstrip('/') if site_url else request.host_url.rstrip('/')
    external_url = f'{base_url}/api/cron/{secret_key}/run-all'
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'tasks': tasks,
            'external_url': external_url,
            'secret_key': secret_key
        }
    })


@admin_bp.route('/cron/tasks/<task_id>/run', methods=['POST'])
@admin_required
@demo_forbidden
def run_cron_task(task_id):
    """手动执行定时任务"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    triggered_by = user.username if user else f'user_{user_id}'
    
    result = CronTaskService.run_task(
        task_id=task_id,
        trigger_type='manual',
        triggered_by=triggered_by
    )
    
    # 获取任务名称
    task_name = result.get('task_name', task_id)
    
    if result['success']:
        return jsonify({
            'code': 200,
            'message': f'{task_name} - 执行完成',
            'data': {
                'task_id': task_id,
                'task_name': task_name,
                'success': True
            }
        })
    else:
        return jsonify({
            'code': 500,
            'message': f'{task_name} - 执行失败',
            'data': {
                'task_id': task_id,
                'task_name': task_name,
                'success': False,
                'error': result.get('error', '未知错误')
            }
        }), 500


@admin_bp.route('/cron/run-all', methods=['POST'])
@admin_required
@demo_forbidden
def run_all_cron_tasks():
    """手动执行所有定时任务"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    triggered_by = user.username if user else f'user_{user_id}'
    
    results = CronTaskService.run_all_tasks(triggered_by=triggered_by)
    
    # 简化返回结果，只显示任务名和状态
    executed = results.get('executed', [])
    summary = []
    for item in executed:
        task_name = item.get('task_name', item.get('task_id', '未知任务'))
        status = '成功' if item.get('success') else '失败'
        summary.append(f'{task_name} - {status}')
    
    return jsonify({
        'code': 200,
        'message': '全部任务执行完成',
        'data': {
            'summary': summary,
            'total': len(executed),
            'success_count': sum(1 for item in executed if item.get('success')),
            'failed_count': sum(1 for item in executed if not item.get('success'))
        }
    })


@admin_bp.route('/cron/regenerate-key', methods=['POST'])
@admin_required
@demo_forbidden
def regenerate_cron_key():
    """重新生成Cron密钥"""
    new_key = CronTaskService.regenerate_secret_key()
    
    site_url = Setting.get('site_url', '')
    base_url = site_url.rstrip('/') if site_url else request.host_url.rstrip('/')
    external_url = f'{base_url}/api/cron/{new_key}/run-all'
    
    return jsonify({
        'code': 200,
        'message': '密钥已重新生成',
        'data': {
            'secret_key': new_key,
            'external_url': external_url
        }
    })


@admin_bp.route('/cron/logs', methods=['GET'])
@admin_required
def get_cron_logs():
    """获取定时任务执行日志"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    task_id = request.args.get('task_id', '')
    status = request.args.get('status', '')
    
    query = CronLog.query
    
    if task_id:
        query = query.filter_by(task_id=task_id)
    if status:
        query = query.filter_by(status=status)
    
    query = query.order_by(CronLog.started_at.desc())
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'logs': [log.to_dict() for log in pagination.items],
            'total': pagination.total,
            'total_pages': pagination.pages,
            'current_page': page
        }
    })


@admin_bp.route('/cron/logs/clear', methods=['POST'])
@admin_required
@demo_forbidden
def clear_cron_logs():
    """清理全部日志"""
    from app import db
    
    deleted = CronLog.query.delete()
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': f'已清理 {deleted} 条日志',
        'data': {'deleted': deleted}
    })
