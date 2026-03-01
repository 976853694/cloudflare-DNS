"""
数据库备份与恢复 API
提供备份创建、列表、下载、恢复和删除功能
"""
import os
import sys
import tempfile
import logging
from pathlib import Path
from datetime import datetime
from flask import Blueprint, jsonify, request, send_file, current_app

# 添加项目根目录到路径以导入 DatabaseBackup
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from scripts.backup import DatabaseBackup

from .decorators import admin_required, demo_forbidden
from app import db

backup_bp = Blueprint('admin_backup', __name__, url_prefix='/api/admin/backup')
logger = logging.getLogger(__name__)


def is_valid_backup_format(filename):
    """
    验证文件格式是否为有效的备份格式
    
    Args:
        filename: 文件名
        
    Returns:
        bool: 是否为有效格式 (.sql 或 .sql.gz)
    """
    if not filename:
        return False
    lower_name = filename.lower()
    return lower_name.endswith('.sql') or lower_name.endswith('.sql.gz')


def format_file_size(size_bytes):
    """
    格式化文件大小为人类可读格式
    
    Args:
        size_bytes: 文件大小（字节）
        
    Returns:
        str: 格式化后的大小字符串
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.2f} MB"
    else:
        return f"{size_bytes / 1024 / 1024 / 1024:.2f} GB"


def is_safe_filename(filename):
    """
    验证文件名是否安全（防止路径遍历攻击）
    
    Args:
        filename: 文件名
        
    Returns:
        bool: 是否为安全的文件名
    """
    if not filename:
        return False
    # 禁止路径分隔符和父目录引用
    if '/' in filename or '\\' in filename or '..' in filename:
        return False
    return True


@backup_bp.route('/list', methods=['GET'])
@admin_required
def list_backups():
    """获取备份文件列表"""
    try:
        backup_manager = DatabaseBackup()
        backups = backup_manager.list_backups()
        
        result = []
        for backup in backups:
            result.append({
                'name': backup['name'],
                'size': backup['size'],
                'size_formatted': format_file_size(backup['size']),
                'created': backup['created'].strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return jsonify({
            'code': 200,
            'data': {
                'backups': result,
                'total': len(result)
            }
        })
    except Exception as e:
        logger.error(f'获取备份列表失败: {str(e)}')
        return jsonify({'code': 500, 'message': f'获取备份列表失败: {str(e)}'}), 500


@backup_bp.route('/create', methods=['POST'])
@admin_required
@demo_forbidden
def create_backup():
    """创建数据库备份"""
    try:
        logger.info('开始创建数据库备份')
        backup_manager = DatabaseBackup()
        backup_path = backup_manager.backup()
        
        # 获取备份文件信息
        backup_file = Path(backup_path)
        file_size = backup_file.stat().st_size
        
        logger.info(f'数据库备份创建成功: {backup_file.name}')
        
        return jsonify({
            'code': 200,
            'message': '备份创建成功',
            'data': {
                'filename': backup_file.name,
                'size': file_size,
                'size_formatted': format_file_size(file_size)
            }
        })
    except Exception as e:
        logger.error(f'创建备份失败: {str(e)}')
        return jsonify({'code': 500, 'message': f'备份失败: {str(e)}'}), 500


@backup_bp.route('/download/<filename>', methods=['GET'])
@admin_required
def download_backup(filename):
    """下载备份文件"""
    try:
        # 安全检查
        if not is_safe_filename(filename):
            return jsonify({'code': 400, 'message': '无效的文件名'}), 400
        
        backup_manager = DatabaseBackup()
        backup_path = backup_manager.backup_dir / filename
        
        if not backup_path.exists():
            return jsonify({'code': 404, 'message': '备份文件不存在'}), 404
        
        # 确定 Content-Type
        if filename.endswith('.gz'):
            mimetype = 'application/gzip'
        else:
            mimetype = 'application/sql'
        
        return send_file(
            backup_path,
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f'下载备份失败: {str(e)}')
        return jsonify({'code': 500, 'message': f'下载失败: {str(e)}'}), 500


@backup_bp.route('/restore', methods=['POST'])
@admin_required
@demo_forbidden
def restore_backup():
    """从上传的备份文件恢复数据库"""
    try:
        # 检查是否有文件上传
        if 'file' not in request.files:
            return jsonify({'code': 400, 'message': '请上传备份文件'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'code': 400, 'message': '请上传备份文件'}), 400
        
        # 验证文件格式
        if not is_valid_backup_format(file.filename):
            return jsonify({
                'code': 400, 
                'message': '不支持的文件格式，请上传 .sql 或 .sql.gz 文件'
            }), 400
        
        # 获取强制恢复参数
        force = request.form.get('force', 'false').lower() == 'true'
        mode_text = '强制覆盖' if force else '普通'
        
        logger.info(f'开始恢复数据库: {file.filename} (模式: {mode_text})')
        
        # 保存上传的文件到临时目录
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, file.filename)
        
        try:
            # 流式保存上传文件，避免大文件内存问题
            logger.info(f'开始保存上传文件: {file.filename}')
            with open(temp_path, 'wb') as f:
                while True:
                    chunk = file.stream.read(64 * 1024)  # 64KB 块
                    if not chunk:
                        break
                    f.write(chunk)
            
            file_size = os.path.getsize(temp_path)
            logger.info(f'文件保存完成，大小: {format_file_size(file_size)}')
            
            # 如果是强制恢复，先自动备份当前数据库
            if force:
                try:
                    logger.info('强制恢复模式：正在自动备份当前数据库...')
                    backup_manager = DatabaseBackup()
                    auto_backup_path = backup_manager.backup()
                    logger.info(f'自动备份完成: {auto_backup_path}')
                except Exception as e:
                    logger.warning(f'自动备份失败（继续执行恢复）: {str(e)}')
            
            # 恢复前先关闭当前数据库连接
            logger.info('关闭当前数据库连接...')
            try:
                db.session.remove()
                db.engine.dispose()
            except Exception as e:
                logger.warning(f'关闭连接时出错（可忽略）: {str(e)}')
            
            # 执行恢复
            logger.info(f'开始恢复数据库: {file.filename} (模式: {mode_text})')
            backup_manager = DatabaseBackup()
            result = backup_manager.restore(temp_path, force=force)
            logger.info(f'数据库恢复成功: {result}')
            
            # 恢复后重新初始化连接池
            try:
                # 强制创建新连接测试
                db.session.execute(db.text('SELECT 1'))
                db.session.commit()
                logger.info('数据库连接池已重新初始化')
            except Exception as e:
                logger.warning(f'重新初始化连接池时出错: {str(e)}')
                # 再次尝试重置
                try:
                    db.session.remove()
                    db.engine.dispose()
                except:
                    pass
            
            return jsonify({
                'code': 200,
                'message': f'数据库恢复成功（{mode_text}模式），请刷新页面',
                'data': {
                    'mode': result.get('mode'),
                    'total': result.get('total'),
                    'executed': result.get('executed'),
                    'failed': result.get('failed')
                }
            })
            
        finally:
            # 清理临时文件
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                if os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
            except Exception as e:
                logger.warning(f'清理临时文件时出错: {str(e)}')
                
    except Exception as e:
        logger.error(f'恢复数据库失败: {str(e)}')
        # 尝试重置连接池
        try:
            db.session.remove()
            db.engine.dispose()
        except:
            pass
        return jsonify({'code': 500, 'message': f'恢复失败: {str(e)}'}), 500


@backup_bp.route('/<filename>', methods=['DELETE'])
@admin_required
@demo_forbidden
def delete_backup(filename):
    """删除备份文件"""
    try:
        # 安全检查
        if not is_safe_filename(filename):
            return jsonify({'code': 400, 'message': '无效的文件名'}), 400
        
        backup_manager = DatabaseBackup()
        backup_path = backup_manager.backup_dir / filename
        
        if not backup_path.exists():
            return jsonify({'code': 404, 'message': '备份文件不存在'}), 404
        
        backup_path.unlink()
        logger.info(f'备份文件已删除: {filename}')
        
        return jsonify({
            'code': 200,
            'message': '备份文件已删除'
        })
    except Exception as e:
        logger.error(f'删除备份失败: {str(e)}')
        return jsonify({'code': 500, 'message': f'删除失败: {str(e)}'}), 500
