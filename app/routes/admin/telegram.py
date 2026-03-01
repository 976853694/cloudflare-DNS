"""
Telegram 机器人管理路由
"""
from flask import request, jsonify, render_template
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required
from app import db
import json


@admin_bp.route('/telegram')
@admin_required
def telegram_page():
    """Telegram 机器人管理页面"""
    return render_template('admin/telegram.html')


@admin_bp.route('/telegram/bot', methods=['GET'])
@admin_required
def get_telegram_bot():
    """获取机器人配置"""
    from app.models.telegram import TelegramBot
    
    bot = TelegramBot.query.first()
    if bot:
        return jsonify({
            'code': 0,
            'data': {
                'id': bot.id,
                'name': bot.name,
                'token': bot.token,
                'username': bot.username,
                'is_enabled': bot.is_enabled,
                'api_urls': bot.get_api_urls(),
                'ad_button': bot.ad_button or '',
                'created_at': bot.created_at.strftime('%Y-%m-%d %H:%M:%S') if bot.created_at else None
            }
        })
    
    return jsonify({'code': 0, 'data': None})


@admin_bp.route('/telegram/bot', methods=['POST'])
@admin_required
def save_telegram_bot():
    """保存机器人配置"""
    from app.models.telegram import TelegramBot
    from app.services.telegram_bot import TelegramBotService
    
    data = request.get_json()
    name = data.get('name', '').strip()
    token = data.get('token', '').strip()
    is_enabled = data.get('is_enabled', True)
    api_urls = data.get('api_urls', [])
    ad_button = data.get('ad_button', '').strip()
    
    if not name:
        return jsonify({'code': 1, 'message': '请输入机器人名称'})
    
    if not token:
        return jsonify({'code': 1, 'message': '请输入Bot Token'})
    
    # 验证广告按钮格式（每行一个，格式：文字,链接）
    if ad_button:
        for line in ad_button.split('\n'):
            line = line.strip()
            if not line:
                continue
            parts = line.split(',', 1)
            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                return jsonify({'code': 1, 'message': f'广告按钮格式错误: {line}\n请使用"文字,链接"格式，每行一个'})
    
    # 验证Token（使用第一个API地址或默认地址）
    test_api_url = api_urls[0] if api_urls else None
    success, result = TelegramBotService.test_token(token, test_api_url)
    if not success:
        return jsonify({'code': 1, 'message': f'Token验证失败: {result}'})
    
    username = result.get('username', '')
    
    # 保存配置（只保留一个机器人）
    bot = TelegramBot.query.first()
    if bot:
        bot.name = name
        bot.token = token
        bot.username = username
        bot.is_enabled = is_enabled
        bot.set_api_urls(api_urls)
        bot.ad_button = ad_button if ad_button else None
    else:
        bot = TelegramBot(
            name=name,
            token=token,
            username=username,
            is_enabled=is_enabled,
            ad_button=ad_button if ad_button else None
        )
        bot.set_api_urls(api_urls)
        db.session.add(bot)
    
    db.session.commit()
    
    # 重启机器人
    if is_enabled:
        TelegramBotService.restart()
    else:
        TelegramBotService.stop()
    
    return jsonify({
        'code': 0,
        'message': '保存成功',
        'data': {
            'username': username
        }
    })


@admin_bp.route('/telegram/bot/test', methods=['POST'])
@admin_required
def test_telegram_token():
    """测试Token"""
    from app.services.telegram_bot import TelegramBotService
    
    data = request.get_json()
    token = data.get('token', '').strip()
    api_url = data.get('api_url', '').strip() or None
    
    if not token:
        return jsonify({'code': 1, 'message': '请输入Token'})
    
    success, result = TelegramBotService.test_token(token, api_url)
    
    if success:
        return jsonify({
            'code': 0,
            'message': 'Token有效',
            'data': result
        })
    else:
        return jsonify({
            'code': 1,
            'message': f'Token无效: {result}'
        })


@admin_bp.route('/telegram/api/test', methods=['POST'])
@admin_required
def test_telegram_api_url():
    """测试API地址是否可用"""
    from app.services.telegram_bot import TelegramBotService
    from app.models.telegram import TelegramBot
    
    data = request.get_json()
    api_url = data.get('api_url', '').strip()
    token = data.get('token', '').strip()
    
    if not api_url:
        return jsonify({'code': 1, 'message': '请输入API地址'})
    
    # 如果没有传token，尝试使用已保存的token
    if not token:
        bot = TelegramBot.query.first()
        if bot and bot.token:
            token = bot.token
        else:
            return jsonify({'code': 1, 'message': '请先配置Bot Token'})
    
    success, result = TelegramBotService.test_token(token, api_url)
    
    if success:
        return jsonify({
            'code': 0,
            'message': 'API地址可用',
            'data': {'api_url': api_url}
        })
    else:
        return jsonify({
            'code': 1,
            'message': f'API地址不可用: {result}'
        })


@admin_bp.route('/telegram/bot/toggle', methods=['POST'])
@admin_required
def toggle_telegram_bot():
    """启用/禁用机器人"""
    from app.models.telegram import TelegramBot
    from app.services.telegram_bot import TelegramBotService
    
    bot = TelegramBot.query.first()
    if not bot:
        return jsonify({'code': 1, 'message': '请先配置机器人'})
    
    bot.is_enabled = not bot.is_enabled
    db.session.commit()
    
    if bot.is_enabled:
        TelegramBotService.restart()
        return jsonify({'code': 0, 'message': '机器人已启用', 'data': {'is_enabled': True}})
    else:
        TelegramBotService.stop()
        return jsonify({'code': 0, 'message': '机器人已禁用', 'data': {'is_enabled': False}})


@admin_bp.route('/telegram/users', methods=['GET'])
@admin_required
def get_telegram_users():
    """获取绑定用户列表"""
    from app.models.telegram import TelegramUser
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = TelegramUser.query.order_by(TelegramUser.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'code': 0,
        'data': {
            'items': [u.to_dict() for u in pagination.items],
            'total': pagination.total,
            'page': page,
            'per_page': per_page
        }
    })
