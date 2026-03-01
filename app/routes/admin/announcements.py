"""
管理员公告管理路由
"""
from flask import request, jsonify
from app import db
from app.models import Announcement, AnnouncementRead
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden


@admin_bp.route('/announcements', methods=['GET'])
@admin_required
def get_announcements():
    """获取公告列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', type=int)
    
    query = Announcement.query
    if status is not None:
        query = query.filter_by(status=status)
    
    pagination = query.order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'announcements': [a.to_dict() for a in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        }
    })


@admin_bp.route('/announcements', methods=['POST'])
@admin_required
@demo_forbidden
def create_announcement():
    """创建公告"""
    data = request.get_json()
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    ann_type = data.get('type', 'info')
    is_pinned = data.get('is_pinned', False)
    status = data.get('status', 1)
    is_popup = data.get('is_popup', False)
    
    if not title or not content:
        return jsonify({'code': 400, 'message': '请输入标题和内容'}), 400
    
    announcement = Announcement(
        title=title,
        content=content,
        type=ann_type,
        is_pinned=is_pinned,
        is_popup=is_popup,
        status=status
    )
    db.session.add(announcement)
    db.session.commit()
    
    return jsonify({
        'code': 201,
        'message': '公告创建成功',
        'data': {'announcement': announcement.to_dict()}
    }), 201


@admin_bp.route('/announcements/<int:ann_id>', methods=['PUT'])
@admin_required
@demo_forbidden
def update_announcement(ann_id):
    """更新公告"""
    announcement = Announcement.query.get(ann_id)
    if not announcement:
        return jsonify({'code': 404, 'message': '公告不存在'}), 404
    
    data = request.get_json()
    if 'title' in data:
        announcement.title = data['title'].strip()
    if 'content' in data:
        announcement.content = data['content'].strip()
    if 'type' in data:
        announcement.type = data['type']
    if 'is_pinned' in data:
        announcement.is_pinned = data['is_pinned']
    if 'is_popup' in data:
        announcement.is_popup = data['is_popup']
    if 'status' in data:
        announcement.status = data['status']
    
    db.session.commit()
    return jsonify({
        'code': 200,
        'message': '公告更新成功',
        'data': {'announcement': announcement.to_dict()}
    })


@admin_bp.route('/announcements/<int:ann_id>', methods=['DELETE'])
@admin_required
@demo_forbidden
def delete_announcement(ann_id):
    """删除公告"""
    announcement = Announcement.query.get(ann_id)
    if not announcement:
        return jsonify({'code': 404, 'message': '公告不存在'}), 404
    
    AnnouncementRead.query.filter_by(announcement_id=ann_id).delete()
    db.session.delete(announcement)
    db.session.commit()
    return jsonify({'code': 200, 'message': '公告删除成功'})
