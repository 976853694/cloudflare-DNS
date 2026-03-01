#!/usr/bin/env python3
"""
数据库备份脚本
支持自动备份MySQL数据库并保留指定天数的备份

使用方法:
    python scripts/backup.py                  # 执行备份
    python scripts/backup.py --cleanup        # 清理过期备份
    python scripts/backup.py --restore <file> # 恢复备份
    
定时任务示例 (crontab):
    0 3 * * * cd /path/to/dns && python scripts/backup.py
"""
import os
import sys
import subprocess
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到路径（提前添加以便导入时区工具）
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from app.utils.timezone import now as beijing_now

load_dotenv()


class DatabaseBackup:
    """数据库备份管理"""
    
    def __init__(self):
        self.db_host = os.getenv('DB_HOST', 'localhost')
        self.db_port = int(os.getenv('DB_PORT', '3306'))  # 转换为整数
        self.db_name = os.getenv('DB_NAME', 'dns_system')
        self.db_user = os.getenv('DB_USER', 'root')
        self.db_password = os.getenv('DB_PASSWORD', '')
        
        # 备份目录
        self.backup_dir = Path(__file__).parent.parent / 'backups'
        self.backup_dir.mkdir(exist_ok=True)
        
        # 保留天数
        self.retention_days = int(os.getenv('BACKUP_RETENTION_DAYS', '7'))
    
    def backup(self):
        """
        执行数据库备份
        
        Returns:
            str: 备份文件路径
        """
        timestamp = beijing_now().strftime('%Y%m%d_%H%M%S')
        backup_file = self.backup_dir / f'{self.db_name}_{timestamp}.sql'
        
        # 构建 mysqldump 命令
        cmd = [
            'mysqldump',
            f'--host={self.db_host}',
            f'--port={self.db_port}',
            f'--user={self.db_user}',
            '--single-transaction',
            '--routines',
            '--triggers',
            self.db_name
        ]
        
        if self.db_password:
            cmd.insert(1, f'--password={self.db_password}')
        
        try:
            print(f'[Backup] 开始备份数据库 {self.db_name}...')
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True
                )
            
            if result.returncode != 0:
                backup_file.unlink(missing_ok=True)
                raise Exception(f'mysqldump 失败: {result.stderr}')
            
            # 压缩备份文件
            compressed_file = self._compress(backup_file)
            
            file_size = compressed_file.stat().st_size / 1024 / 1024  # MB
            print(f'[Backup] 备份完成: {compressed_file.name} ({file_size:.2f} MB)')
            
            return str(compressed_file)
            
        except FileNotFoundError:
            raise Exception('mysqldump 命令未找到，请确保 MySQL 客户端已安装')
        except Exception as e:
            raise Exception(f'备份失败: {str(e)}')
    
    def _compress(self, file_path):
        """压缩备份文件"""
        import gzip
        import shutil
        
        compressed_path = Path(str(file_path) + '.gz')
        
        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # 删除原文件
        file_path.unlink()
        
        return compressed_path
    
    def restore(self, backup_file, force=False):
        """
        从备份恢复数据库（使用 pymysql，兼容 Docker 环境）
        
        Args:
            backup_file: 备份文件路径
            force: 是否强制覆盖（删除并重建数据库）
        
        Returns:
            dict: 恢复结果统计
        """
        backup_path = Path(backup_file)
        
        if not backup_path.exists():
            raise Exception(f'备份文件不存在: {backup_file}')
        
        try:
            mode = '强制覆盖' if force else '普通'
            print(f'[Restore] 开始恢复数据库 {self.db_name} (模式: {mode})...')
            
            # 读取 SQL 文件内容
            if backup_path.suffix == '.gz':
                import gzip
                print('[Restore] 解压 gzip 文件...')
                with gzip.open(backup_path, 'rt', encoding='utf-8') as f:
                    sql_content = f.read()
            else:
                with open(backup_path, 'r', encoding='utf-8') as f:
                    sql_content = f.read()
            
            print(f'[Restore] SQL 文件大小: {len(sql_content)} 字符')
            
            # 根据模式选择恢复方法
            if force:
                result = self._force_restore(sql_content)
            else:
                result = self._normal_restore(sql_content)
            
            print(f'[Restore] 恢复完成')
            return result
            
        except Exception as e:
            raise Exception(f'恢复失败: {str(e)}')
    
    def _force_restore(self, sql_content):
        """
        强制恢复模式：删除并重建数据库
        
        Args:
            sql_content: SQL 文件内容
            
        Returns:
            dict: 恢复结果统计
        """
        import pymysql
        
        # 获取 root 用户凭据（用于删除和创建数据库）
        root_user = os.getenv('MYSQL_ROOT_USER', 'root')
        root_password = os.getenv('MYSQL_ROOT_PASSWORD', self.db_password)
        
        print(f'[Restore] 使用强制覆盖模式，将删除并重建数据库 {self.db_name}')
        
        # 连接到 MySQL（不指定数据库）
        connection = pymysql.connect(
            host=self.db_host,
            port=self.db_port,
            user=root_user,
            password=root_password,
            charset='utf8mb4'
        )
        
        try:
            cursor = connection.cursor()
            
            # 删除现有数据库
            print(f'[Restore] 删除现有数据库 {self.db_name}...')
            cursor.execute(f'DROP DATABASE IF EXISTS `{self.db_name}`')
            
            # 创建新数据库
            print(f'[Restore] 创建新数据库 {self.db_name}...')
            cursor.execute(
                f'CREATE DATABASE `{self.db_name}` '
                f'CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
            )
            
            # 切换到新数据库
            cursor.execute(f'USE `{self.db_name}`')
            connection.commit()
            
            print(f'[Restore] 数据库已重建，开始导入数据...')
            
            # 解析并执行 SQL 语句
            statements = self._parse_sql_statements(sql_content)
            print(f'[Restore] 共 {len(statements)} 条 SQL 语句')
            
            executed = 0
            failed = 0
            
            for i, statement in enumerate(statements, 1):
                try:
                    cursor.execute(statement)
                    executed += 1
                    
                    # 每 1000 条语句提交一次
                    if i % 1000 == 0:
                        connection.commit()
                        print(f'[Restore] 已执行 {i}/{len(statements)} 条语句')
                        
                except Exception as e:
                    failed += 1
                    error_msg = str(e)
                    # 在强制模式下，某些错误仍然可以忽略（如 USE 语句）
                    if 'USE' not in statement.upper()[:10]:
                        print(f'[Restore] 警告: 语句执行失败 (第 {i} 条): {error_msg[:100]}')
            
            # 最后提交
            connection.commit()
            print(f'[Restore] 成功执行 {executed}/{len(statements)} 条语句，失败 {failed} 条')
            
            return {
                'mode': 'force',
                'total': len(statements),
                'executed': executed,
                'failed': failed
            }
            
        finally:
            cursor.close()
            connection.close()
    
    def _normal_restore(self, sql_content):
        """
        普通恢复模式：在现有数据库上执行
        
        Args:
            sql_content: SQL 文件内容
            
        Returns:
            dict: 恢复结果统计
        """
        import pymysql
        
        # 连接到 MySQL
        connection = pymysql.connect(
            host=self.db_host,
            port=self.db_port,
            user=self.db_user,
            password=self.db_password,
            database=self.db_name,
            charset='utf8mb4'
        )
        
        try:
            cursor = connection.cursor()
            
            # 解析并执行 SQL 语句
            statements = self._parse_sql_statements(sql_content)
            print(f'[Restore] 共 {len(statements)} 条 SQL 语句')
            
            executed = 0
            failed = 0
            
            for i, statement in enumerate(statements, 1):
                try:
                    cursor.execute(statement)
                    executed += 1
                    
                    # 每 100 条语句提交一次
                    if i % 100 == 0:
                        connection.commit()
                        print(f'[Restore] 已执行 {i}/{len(statements)} 条语句')
                        
                except Exception as e:
                    failed += 1
                    error_msg = str(e)
                    # 某些语句可能会失败，继续执行
                    if 'already exists' not in error_msg.lower() and 'unknown table' not in error_msg.lower():
                        print(f'[Restore] 警告: 语句执行失败 (第 {i} 条): {error_msg[:100]}')
            
            # 最后提交
            connection.commit()
            print(f'[Restore] 成功执行 {executed}/{len(statements)} 条语句，失败 {failed} 条')
            
            return {
                'mode': 'normal',
                'total': len(statements),
                'executed': executed,
                'failed': failed
            }
            
        finally:
            cursor.close()
            connection.close()
    
    def _parse_sql_statements(self, sql_content):
        """
        解析 SQL 文件内容为语句列表
        
        Args:
            sql_content: SQL 文件内容
            
        Returns:
            list: SQL 语句列表
        """
        statements = []
        current_statement = []
        in_delimiter = False
        
        for line in sql_content.split('\n'):
            # 跳过注释
            line = line.strip()
            if not line or line.startswith('--') or line.startswith('/*'):
                continue
            
            # 检查 DELIMITER 命令
            if line.upper().startswith('DELIMITER'):
                in_delimiter = not in_delimiter
                continue
            
            current_statement.append(line)
            
            # 如果不在 DELIMITER 块中，且行以分号结尾，则认为是一条完整语句
            if not in_delimiter and line.endswith(';'):
                statement = ' '.join(current_statement)
                if statement.strip():
                    statements.append(statement)
                current_statement = []
        
        # 处理最后一条语句（如果没有分号结尾）
        if current_statement:
            statement = ' '.join(current_statement)
            if statement.strip():
                statements.append(statement)
        
        return statements
    
    def cleanup(self):
        """清理过期的备份文件"""
        cutoff_date = beijing_now() - timedelta(days=self.retention_days)
        deleted = 0
        
        print(f'[Cleanup] 清理 {self.retention_days} 天前的备份...')
        
        for backup_file in self.backup_dir.glob('*.sql*'):
            file_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
            if file_mtime < cutoff_date:
                backup_file.unlink()
                print(f'[Cleanup] 删除: {backup_file.name}')
                deleted += 1
        
        print(f'[Cleanup] 清理完成，删除 {deleted} 个文件')
        return deleted
    
    def list_backups(self):
        """列出所有备份文件"""
        backups = []
        
        for backup_file in sorted(self.backup_dir.glob('*.sql*'), reverse=True):
            stat = backup_file.stat()
            backups.append({
                'name': backup_file.name,
                'path': str(backup_file),
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_mtime)
            })
        
        return backups


def main():
    parser = argparse.ArgumentParser(description='数据库备份工具')
    parser.add_argument('--cleanup', action='store_true', help='清理过期备份')
    parser.add_argument('--restore', metavar='FILE', help='从备份恢复')
    parser.add_argument('--force', action='store_true', help='强制覆盖（删除并重建数据库）')
    parser.add_argument('--list', action='store_true', help='列出所有备份')
    
    args = parser.parse_args()
    
    backup_manager = DatabaseBackup()
    
    try:
        if args.cleanup:
            backup_manager.cleanup()
        elif args.restore:
            backup_manager.restore(args.restore, force=args.force)
        elif args.list:
            backups = backup_manager.list_backups()
            if backups:
                print(f'\n找到 {len(backups)} 个备份文件:\n')
                for b in backups:
                    size_mb = b['size'] / 1024 / 1024
                    print(f"  {b['name']} ({size_mb:.2f} MB) - {b['created']}")
            else:
                print('没有找到备份文件')
        else:
            # 默认执行备份
            backup_file = backup_manager.backup()
            # 备份后自动清理
            backup_manager.cleanup()
            
    except Exception as e:
        print(f'[Error] {str(e)}')
        sys.exit(1)


if __name__ == '__main__':
    main()
