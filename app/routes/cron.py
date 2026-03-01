"""
定时任务外部调用路由
提供URL触发方式执行定时任务
"""
from flask import Blueprint, Response
from app.services.cron_tasks import CronTaskService
from app.utils.ip_utils import get_real_ip

cron_bp = Blueprint('cron', __name__)


@cron_bp.route('/<secret_key>/run-all', methods=['GET'])
def run_all_tasks(secret_key):
    """
    执行所有定时任务（强制执行）
    
    用于外部cron调用，一次性执行所有任务
    建议每天凌晨调用一次作为兜底
    
    示例: curl https://域名/api/cron/{secret_key}/run-all
    """
    # 验证密钥
    if not CronTaskService.verify_secret_key(secret_key):
        return Response('无效的密钥', status=401, mimetype='text/plain; charset=utf-8')
    
    # 获取触发者IP
    triggered_by = get_real_ip()
    
    # 执行所有任务
    results = CronTaskService.run_all_tasks(triggered_by=triggered_by)
    
    # 简化返回结果，只显示任务名和状态
    executed = results.get('executed', [])
    lines = []
    for item in executed:
        task_name = item.get('task_name', item.get('task_id', '未知任务'))
        status = '成功' if item.get('success') else '失败'
        lines.append(f'{task_name} - {status}')
    
    return Response('\n'.join(lines), status=200, mimetype='text/plain; charset=utf-8')


@cron_bp.route('/<secret_key>/<task_id>', methods=['GET'])
def run_single_task(secret_key, task_id):
    """
    执行单个定时任务
    
    用于外部cron调用特定任务
    
    示例: curl https://域名/api/cron/{secret_key}/domain_expiry_reminder
    """
    # 验证密钥
    if not CronTaskService.verify_secret_key(secret_key):
        return Response('无效的密钥', status=401, mimetype='text/plain; charset=utf-8')
    
    # 获取触发者IP
    triggered_by = get_real_ip()
    
    # 执行任务
    result = CronTaskService.run_task(
        task_id=task_id,
        trigger_type='external',
        triggered_by=triggered_by
    )
    
    # 获取任务名称
    task_name = result.get('task_name', task_id)
    status = '成功' if result['success'] else '失败'
    
    return Response(f'{task_name} - {status}', status=200, mimetype='text/plain; charset=utf-8')
