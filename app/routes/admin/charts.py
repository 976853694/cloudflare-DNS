"""
管理员图表数据路由
提供仪表盘可视化图表所需的统计数据
"""
from flask import request, jsonify
from datetime import timedelta
from sqlalchemy import func
from app import db
from app.models import User, Subdomain, PurchaseRecord, RedeemCode, OperationLog
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required
from app.utils.timezone import now as beijing_now


@admin_bp.route('/charts/overview', methods=['GET'])
@admin_required
def get_charts_overview():
    """获取概览图表数据"""
    days = request.args.get('days', 7, type=int)
    end_date = beijing_now().date()
    start_date = end_date - timedelta(days=days - 1)
    
    # 生成日期列表
    date_list = []
    current = start_date
    while current <= end_date:
        date_list.append(current.isoformat())
        current += timedelta(days=1)
    
    # 用户增长趋势
    user_stats = db.session.query(
        func.date(User.created_at).label('date'),
        func.count(User.id).label('count')
    ).filter(
        func.date(User.created_at) >= start_date
    ).group_by(func.date(User.created_at)).all()
    
    user_data = {str(s.date): s.count for s in user_stats}
    
    # 域名注册趋势
    subdomain_stats = db.session.query(
        func.date(Subdomain.created_at).label('date'),
        func.count(Subdomain.id).label('count')
    ).filter(
        func.date(Subdomain.created_at) >= start_date
    ).group_by(func.date(Subdomain.created_at)).all()
    
    subdomain_data = {str(s.date): s.count for s in subdomain_stats}
    
    # 收入趋势
    income_stats = db.session.query(
        func.date(PurchaseRecord.created_at).label('date'),
        func.sum(PurchaseRecord.price).label('total')
    ).filter(
        func.date(PurchaseRecord.created_at) >= start_date
    ).group_by(func.date(PurchaseRecord.created_at)).all()
    
    income_data = {str(s.date): float(s.total or 0) for s in income_stats}
    
    return jsonify({
        'code': 200,
        'data': {
            'dates': date_list,
            'users': [user_data.get(d, 0) for d in date_list],
            'subdomains': [subdomain_data.get(d, 0) for d in date_list],
            'income': [income_data.get(d, 0) for d in date_list]
        }
    })


@admin_bp.route('/charts/user-distribution', methods=['GET'])
@admin_required
def get_user_distribution():
    """获取用户分布数据"""
    # 用户状态分布
    status_stats = db.session.query(
        User.status,
        func.count(User.id).label('count')
    ).group_by(User.status).all()
    
    status_labels = {0: '禁用', 1: '正常'}
    status_data = [{'name': status_labels.get(s.status, f'状态{s.status}'), 'value': s.count} for s in status_stats]
    
    # 用户角色分布
    role_stats = db.session.query(
        User.role,
        func.count(User.id).label('count')
    ).group_by(User.role).all()
    
    role_labels = {'user': '普通用户', 'admin': '管理员'}
    role_data = [{'name': role_labels.get(s.role, s.role), 'value': s.count} for s in role_stats]
    
    return jsonify({
        'code': 200,
        'data': {
            'status': status_data,
            'role': role_data
        }
    })


@admin_bp.route('/charts/subdomain-stats', methods=['GET'])
@admin_required
def get_subdomain_stats():
    """获取域名统计数据"""
    now = beijing_now()
    
    # 域名状态分布
    status_stats = db.session.query(
        Subdomain.status,
        func.count(Subdomain.id).label('count')
    ).group_by(Subdomain.status).all()
    
    status_labels = {0: '已停用', 1: '正常', 2: '待审核'}
    status_data = [{'name': status_labels.get(s.status, f'状态{s.status}'), 'value': s.count} for s in status_stats]
    
    # 过期情况
    total = Subdomain.query.count()
    expired = Subdomain.query.filter(Subdomain.expires_at < now).count()
    expiring_7d = Subdomain.query.filter(
        Subdomain.expires_at >= now,
        Subdomain.expires_at <= now + timedelta(days=7)
    ).count()
    permanent = Subdomain.query.filter(Subdomain.expires_at == None).count()
    normal = total - expired - expiring_7d - permanent
    
    expiry_data = [
        {'name': '已过期', 'value': expired},
        {'name': '7天内到期', 'value': expiring_7d},
        {'name': '正常', 'value': normal},
        {'name': '永久', 'value': permanent}
    ]
    
    return jsonify({
        'code': 200,
        'data': {
            'status': status_data,
            'expiry': expiry_data
        }
    })


@admin_bp.route('/charts/income-stats', methods=['GET'])
@admin_required
def get_income_stats():
    """获取收入统计数据"""
    days = request.args.get('days', 30, type=int)
    end_date = beijing_now().date()
    start_date = end_date - timedelta(days=days - 1)
    
    # 总收入
    total_income = db.session.query(func.sum(PurchaseRecord.price)).scalar() or 0
    
    # 今日收入
    today_income = db.session.query(func.sum(PurchaseRecord.price)).filter(
        func.date(PurchaseRecord.created_at) == end_date
    ).scalar() or 0
    
    # 本月收入
    month_start = end_date.replace(day=1)
    month_income = db.session.query(func.sum(PurchaseRecord.price)).filter(
        func.date(PurchaseRecord.created_at) >= month_start
    ).scalar() or 0
    
    # 卡密统计
    redeem_total = RedeemCode.query.count()
    redeem_used = RedeemCode.query.filter_by(status=RedeemCode.STATUS_USED).count()
    redeem_unused = RedeemCode.query.filter_by(status=RedeemCode.STATUS_UNUSED).count()
    
    return jsonify({
        'code': 200,
        'data': {
            'total_income': float(total_income),
            'today_income': float(today_income),
            'month_income': float(month_income),
            'redeem': {
                'total': redeem_total,
                'used': redeem_used,
                'unused': redeem_unused
            }
        }
    })


@admin_bp.route('/charts/activity', methods=['GET'])
@admin_required
def get_activity_stats():
    """获取活动统计（登录、操作等）"""
    days = request.args.get('days', 7, type=int)
    end_date = beijing_now().date()
    start_date = end_date - timedelta(days=days - 1)
    
    # 登录趋势
    login_stats = db.session.query(
        func.date(OperationLog.created_at).label('date'),
        func.count(OperationLog.id).label('count')
    ).filter(
        OperationLog.action == OperationLog.ACTION_LOGIN,
        func.date(OperationLog.created_at) >= start_date
    ).group_by(func.date(OperationLog.created_at)).all()
    
    # 生成日期列表
    date_list = []
    current = start_date
    while current <= end_date:
        date_list.append(current.isoformat())
        current += timedelta(days=1)
    
    login_data = {str(s.date): s.count for s in login_stats}
    
    # 操作类型分布
    action_stats = db.session.query(
        OperationLog.action,
        func.count(OperationLog.id).label('count')
    ).filter(
        func.date(OperationLog.created_at) >= start_date
    ).group_by(OperationLog.action).all()
    
    action_labels = {
        'login': '登录',
        'logout': '登出',
        'create': '创建',
        'update': '更新',
        'delete': '删除',
        'other': '其他'
    }
    
    action_data = [{'name': action_labels.get(s.action, s.action), 'value': s.count} for s in action_stats]
    
    return jsonify({
        'code': 200,
        'data': {
            'dates': date_list,
            'logins': [login_data.get(d, 0) for d in date_list],
            'actions': action_data
        }
    })
