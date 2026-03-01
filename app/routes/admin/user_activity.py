from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from app import db
from app.models import User, UserActivity, OperationLog
from app.services.activity_tracker import ActivityTracker
from app.routes.admin.decorators import admin_required, demo_forbidden
from app.utils.ip_utils import get_real_ip

bp = Blueprint('admin_user_activity', __name__, url_prefix='/api/admin/user-activity')


@bp.route('/stats', methods=['GET'])
@admin_required
def get_activity_stats():
    """获取活跃度统计"""
    stats = ActivityTracker.get_activity_stats()
    
    return jsonify({
        'code': 200,
        'data': stats
    })


@bp.route('/manual-check', methods=['POST'])
@admin_required
def manual_check():
    """手动检测用户活跃度"""
    try:
        from datetime import datetime, timedelta
        from app.utils.timezone import now as beijing_now
        
        now = beijing_now()
        
        # 使用新的综合评分规则统计各等级用户数
        high_count = 0
        medium_count = 0
        low_count = 0
        dormant_count = 0
        lost_count = 0
        
        all_users = User.query.all()
        recent_active = []
        lost_users_list = []
        
        for user in all_users:
            details = ActivityTracker.get_activity_details(user)
            level = details['activity_level']
            
            if level == 'high':
                high_count += 1
                recent_active.append({
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'last_activity_at': user.last_activity_at.strftime('%Y-%m-%d %H:%M:%S') if user.last_activity_at else None,
                    'activity_score': details['total_score'],
                    'domain_count': details['domain_count'],
                    'login_frequency': details['login_frequency']
                })
            elif level == 'medium':
                medium_count += 1
            elif level == 'low':
                low_count += 1
            elif level == 'dormant':
                dormant_count += 1
            else:
                lost_count += 1
                lost_users_list.append({
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'last_activity_at': user.last_activity_at.strftime('%Y-%m-%d %H:%M:%S') if user.last_activity_at else None,
                    'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None,
                    'activity_score': details['total_score'],
                    'domain_count': details['domain_count']
                })
        
        # 按活跃度分数排序，取前10
        recent_active.sort(key=lambda x: x['activity_score'], reverse=True)
        recent_active = recent_active[:10]
        
        # 流失用户按注册时间排序，取前10
        lost_users_list.sort(key=lambda x: x['created_at'] or '', reverse=True)
        lost_users_list = lost_users_list[:10]
        
        return jsonify({
            'code': 200,
            'message': '检测完成',
            'data': {
                'check_time': now.strftime('%Y-%m-%d %H:%M:%S'),
                'summary': {
                    'high': high_count,
                    'medium': medium_count,
                    'low': low_count,
                    'dormant': dormant_count,
                    'lost': lost_count,
                    'total': high_count + medium_count + low_count + dormant_count + lost_count
                },
                'recent_active': recent_active,
                'lost_users': lost_users_list
            }
        })
    except Exception as e:
        return jsonify({'code': 500, 'message': f'检测失败: {str(e)}'})


@bp.route('/users', methods=['GET'])
@admin_required
def get_users_activity():
    """获取用户活跃度列表"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        activity_level = request.args.get('level', '')  # 前端传的是 level
        search = request.args.get('search', '').strip()
        
        query = User.query
        
        # 搜索
        if search:
            query = query.filter(
                db.or_(
                    User.username.like(f'%{search}%'),
                    User.email.like(f'%{search}%')
                )
            )
        
        # 获取所有符合搜索条件的用户
        all_users = query.all()
        
        # 按活跃度等级筛选
        if activity_level:
            filtered_users = [u for u in all_users if ActivityTracker.get_activity_level(u) == activity_level]
        else:
            filtered_users = all_users
        
        # 按活跃度分数排序（高到低）
        filtered_users.sort(key=lambda u: ActivityTracker.get_activity_details(u)['total_score'], reverse=True)
        
        # 手动分页
        total = len(filtered_users)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_users = filtered_users[start:end]
        pages = (total + per_page - 1) // per_page if total > 0 else 1
        
        users = []
        for user in paginated_users:
            user_dict = user.to_dict(include_stats=True)
            activity_details = ActivityTracker.get_activity_details(user)
            user_dict['activity_level'] = activity_details['activity_level']
            user_dict['activity_total_score'] = activity_details['total_score']
            user_dict['domain_count'] = activity_details['domain_count']
            user_dict['login_frequency'] = activity_details['login_frequency']
            user_dict['days_since_register'] = activity_details['days_since_register']
            user_dict['last_login_days'] = activity_details['last_login_days']
            users.append(user_dict)
        
        return jsonify({
            'code': 200,
            'data': {
                'users': users,
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': pages
            }
        })
    except Exception as e:
        return jsonify({'code': 500, 'message': f'获取用户列表失败: {str(e)}'})


@bp.route('/<int:user_id>', methods=['GET'])
@admin_required
def get_user_activity(user_id):
    """获取单个用户活动记录"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    activity_type = request.args.get('activity_type', '')
    
    # 从 UserActivity 表获取活动记录
    query = UserActivity.query.filter_by(user_id=user_id)
    
    # 活动类型筛选
    if activity_type:
        query = query.filter(UserActivity.activity_type == activity_type)
    
    # 分页
    pagination = query.order_by(UserActivity.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    activities = []
    for activity in pagination.items:
        activities.append(activity.to_dict())
    
    # 如果 UserActivity 表没有数据，从 OperationLog 获取登录记录
    if len(activities) == 0:
        login_logs = OperationLog.query.filter_by(
            user_id=user_id,
            action=OperationLog.ACTION_LOGIN
        ).order_by(OperationLog.created_at.desc()).limit(per_page).all()
        
        for log in login_logs:
            activities.append({
                'id': log.id,
                'user_id': user_id,
                'activity_type': 'login',
                'activity_data': {'ip': log.ip_address},
                'ip_address': log.ip_address,
                'created_at': log.created_at.isoformat() if log.created_at else None
            })
    
    # 用户信息
    user_dict = user.to_dict(include_stats=True)
    user_dict['activity_level'] = ActivityTracker.get_activity_level(user)
    
    return jsonify({
        'code': 200,
        'data': {
            'user': user_dict,
            'activities': activities,
            'total': pagination.total if pagination.total > 0 else len(activities),
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages if pagination.pages > 0 else 1
        }
    })


@bp.route('/batch', methods=['POST'])
@admin_required
@demo_forbidden
def batch_operation():
    """
    批量操作用户
    
    Request Body:
    {
        "action": "ban" | "sleep" | "delete",
        "user_ids": [1, 2, 3, ...]
    }
    """
    try:
        data = request.get_json()
        action = data.get('action', '')
        user_ids = data.get('user_ids', [])
        
        # 验证操作类型
        if action not in ['ban', 'sleep', 'delete']:
            return jsonify({'code': 400, 'message': '无效的操作类型'}), 400
        
        # 验证用户ID列表
        if not user_ids or not isinstance(user_ids, list):
            return jsonify({'code': 400, 'message': '请选择要操作的用户'}), 400
        
        # 批量大小限制
        if len(user_ids) > 100:
            return jsonify({'code': 400, 'message': '单次最多操作100个用户'}), 400
        
        # 获取当前登录用户
        current_user_id = int(get_jwt_identity())
        current_user = User.query.get(current_user_id)
        
        success_count = 0
        failed_count = 0
        failed_users = []
        
        for user_id in user_ids:
            user = User.query.get(user_id)
            
            if not user:
                failed_count += 1
                failed_users.append({
                    'id': user_id,
                    'username': '未知',
                    'reason': '用户不存在'
                })
                continue
            
            # 不能操作管理员账号
            if user.role == User.ROLE_ADMIN:
                failed_count += 1
                failed_users.append({
                    'id': user_id,
                    'username': user.username,
                    'reason': '管理员账号不能操作'
                })
                continue
            
            # 不能操作自己的账号
            if user.id == current_user_id:
                failed_count += 1
                failed_users.append({
                    'id': user_id,
                    'username': user.username,
                    'reason': '不能操作自己的账号'
                })
                continue
            
            try:
                if action == 'ban':
                    # 批量封禁
                    user.status = User.STATUS_BANNED
                    db.session.commit()
                    
                    # 记录操作日志
                    OperationLog.log(
                        user_id=current_user_id,
                        username=current_user.username if current_user else None,
                        action=OperationLog.ACTION_UPDATE,
                        target_type='user',
                        target_id=user_id,
                        detail=f'批量封禁用户: {user.username}',
                        ip_address=get_real_ip()
                    )
                    success_count += 1
                    
                elif action == 'sleep':
                    # 批量沉睡
                    user.status = User.STATUS_SLEEPING
                    db.session.commit()
                    
                    # 记录操作日志
                    OperationLog.log(
                        user_id=current_user_id,
                        username=current_user.username if current_user else None,
                        action=OperationLog.ACTION_UPDATE,
                        target_type='user',
                        target_id=user_id,
                        detail=f'批量设置用户沉睡: {user.username}',
                        ip_address=get_real_ip()
                    )
                    success_count += 1
                    
                elif action == 'delete':
                    # 批量删除 - 需要先删除关联的DNS记录
                    username = user.username
                    
                    for subdomain in user.subdomains:
                        domain = subdomain.domain
                        dns_service = domain.get_dns_service() if domain else None
                        zone_id = domain.get_zone_id() if domain else None
                        
                        if dns_service and zone_id:
                            for record in subdomain.records:
                                try:
                                    dns_service.delete_record(zone_id, record.cf_record_id)
                                except:
                                    pass
                    
                    db.session.delete(user)
                    db.session.commit()
                    
                    # 记录操作日志
                    OperationLog.log(
                        user_id=current_user_id,
                        username=current_user.username if current_user else None,
                        action=OperationLog.ACTION_DELETE,
                        target_type='user',
                        target_id=user_id,
                        detail=f'批量删除用户: {username}',
                        ip_address=get_real_ip()
                    )
                    success_count += 1
                    
            except Exception as e:
                db.session.rollback()
                failed_count += 1
                failed_users.append({
                    'id': user_id,
                    'username': user.username if user else '未知',
                    'reason': f'操作失败: {str(e)}'
                })
        
        # 构建响应消息
        action_text = {'ban': '封禁', 'sleep': '沉睡', 'delete': '删除'}.get(action, '操作')
        if failed_count == 0:
            message = f'批量{action_text}成功，共处理 {success_count} 个用户'
        else:
            message = f'批量{action_text}完成，成功 {success_count} 个，失败 {failed_count} 个'
        
        return jsonify({
            'code': 200,
            'message': message,
            'data': {
                'success_count': success_count,
                'failed_count': failed_count,
                'failed_users': failed_users
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'message': f'操作失败: {str(e)}'}), 500
