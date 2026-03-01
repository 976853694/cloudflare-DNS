from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from app import db
from app.models import EmailCampaign, EmailLog, User
from app.services.email_campaign_service import EmailCampaignService
from app.routes.admin.decorators import admin_required
import json

bp = Blueprint('admin_email_campaigns', __name__, url_prefix='/api/admin/email-campaigns')


@bp.route('', methods=['GET'])
@admin_required
def get_campaigns():
    """获取群发任务列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', '')
    
    query = EmailCampaign.query
    
    # 状态筛选
    if status:
        query = query.filter(EmailCampaign.status == status)
    
    # 分页
    pagination = query.order_by(EmailCampaign.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    campaigns = []
    for campaign in pagination.items:
        campaigns.append(campaign.to_dict())
    
    return jsonify({
        'code': 200,
        'data': {
            'campaigns': campaigns,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    })


@bp.route('', methods=['POST'])
@admin_required
def create_campaign():
    """创建群发任务"""
    data = request.get_json()
    
    name = data.get('name', '').strip()
    subject = data.get('subject', '').strip()
    content = data.get('content', '').strip()
    recipient_filter = data.get('recipient_filter', {})
    scheduled_at = data.get('scheduled_at')
    
    if not name or not subject or not content:
        return jsonify({'code': 400, 'message': '请填写任务名称、邮件主题和内容'}), 400
    
    current_user_id = get_jwt_identity()
    
    try:
        campaign = EmailCampaignService.create_campaign(
            name=name,
            subject=subject,
            content=content,
            recipient_filter=recipient_filter,
            scheduled_at=scheduled_at,
            created_by=current_user_id
        )
        
        return jsonify({
            'code': 200,
            'message': '任务创建成功',
            'data': campaign.to_dict()
        })
    except Exception as e:
        return jsonify({'code': 500, 'message': f'创建失败: {str(e)}'}), 500


@bp.route('/<int:campaign_id>', methods=['GET'])
@admin_required
def get_campaign(campaign_id):
    """获取任务详情"""
    campaign = EmailCampaign.query.get(campaign_id)
    if not campaign:
        return jsonify({'code': 404, 'message': '任务不存在'}), 404
    
    return jsonify({
        'code': 200,
        'data': campaign.to_dict()
    })


@bp.route('/<int:campaign_id>', methods=['PUT'])
@admin_required
def update_campaign(campaign_id):
    """更新任务"""
    campaign = EmailCampaign.query.get(campaign_id)
    if not campaign:
        return jsonify({'code': 404, 'message': '任务不存在'}), 404
    
    if campaign.status != EmailCampaign.STATUS_DRAFT:
        return jsonify({'code': 400, 'message': '只能修改草稿状态的任务'}), 400
    
    data = request.get_json()
    
    if 'name' in data:
        campaign.name = data['name'].strip()
    if 'subject' in data:
        campaign.subject = data['subject'].strip()
    if 'content' in data:
        campaign.content = data['content'].strip()
    if 'recipient_filter' in data:
        campaign.recipient_filter = json.dumps(data['recipient_filter']) if isinstance(data['recipient_filter'], dict) else data['recipient_filter']
    if 'scheduled_at' in data:
        campaign.scheduled_at = data['scheduled_at']
    
    try:
        db.session.commit()
        return jsonify({
            'code': 200,
            'message': '任务更新成功',
            'data': campaign.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'message': f'更新失败: {str(e)}'}), 500


@bp.route('/<int:campaign_id>', methods=['DELETE'])
@admin_required
def delete_campaign(campaign_id):
    """删除任务"""
    campaign = EmailCampaign.query.get(campaign_id)
    if not campaign:
        return jsonify({'code': 404, 'message': '任务不存在'}), 404
    
    if campaign.status == EmailCampaign.STATUS_SENDING:
        return jsonify({'code': 400, 'message': '正在发送的任务不能删除'}), 400
    
    try:
        # 删除相关日志
        EmailLog.query.filter_by(campaign_id=campaign_id).delete()
        db.session.delete(campaign)
        db.session.commit()
        return jsonify({'code': 200, 'message': '任务删除成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'message': f'删除失败: {str(e)}'}), 500


@bp.route('/<int:campaign_id>/send', methods=['POST'])
@admin_required
def send_campaign(campaign_id):
    """发送任务（异步）"""
    campaign = EmailCampaign.query.get(campaign_id)
    if not campaign:
        return jsonify({'code': 404, 'message': '任务不存在'}), 404
    
    try:
        success, message = EmailCampaignService.send_campaign(campaign_id)
        if success:
            return jsonify({'code': 200, 'message': message})
        else:
            return jsonify({'code': 400, 'message': message}), 400
    except Exception as e:
        return jsonify({'code': 500, 'message': f'发送失败: {str(e)}'}), 500


@bp.route('/<int:campaign_id>/progress', methods=['GET'])
@admin_required
def get_campaign_progress(campaign_id):
    """获取任务发送进度"""
    progress = EmailCampaignService.get_campaign_progress(campaign_id)
    if not progress:
        return jsonify({'code': 404, 'message': '任务不存在'}), 404
    
    return jsonify({
        'code': 200,
        'data': progress
    })


@bp.route('/<int:campaign_id>/logs', methods=['GET'])
@admin_required
def get_campaign_logs(campaign_id):
    """获取发送日志"""
    campaign = EmailCampaign.query.get(campaign_id)
    if not campaign:
        return jsonify({'code': 404, 'message': '任务不存在'}), 404
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    status = request.args.get('status', '')
    
    query = EmailLog.query.filter_by(campaign_id=campaign_id)
    
    # 状态筛选
    if status:
        query = query.filter(EmailLog.status == status)
    
    # 分页
    pagination = query.order_by(EmailLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    logs = []
    for log in pagination.items:
        log_dict = log.to_dict()
        # 添加用户信息
        if log.user_id:
            user = User.query.get(log.user_id)
            if user:
                log_dict['user'] = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                }
        logs.append(log_dict)
    
    return jsonify({
        'code': 200,
        'data': {
            'logs': logs,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    })


@bp.route('/preview', methods=['POST'])
@admin_required
def preview_email():
    """预览邮件"""
    data = request.get_json()
    
    subject = data.get('subject', '').strip()
    content = data.get('content', '').strip()
    user_id = data.get('user_id')
    
    if not subject or not content:
        return jsonify({'code': 400, 'message': '请填写邮件主题和内容'}), 400
    
    # 获取预览用户
    if user_id:
        user = User.query.get(user_id)
    else:
        # 使用当前管理员作为预览用户
        user = User.query.get(get_jwt_identity())
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    # 替换变量
    preview_subject = EmailCampaignService.replace_variables(subject, user)
    preview_content = EmailCampaignService.replace_variables(content, user)
    
    return jsonify({
        'code': 200,
        'data': {
            'subject': preview_subject,
            'content': preview_content,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'balance': float(user.balance)
            }
        }
    })
