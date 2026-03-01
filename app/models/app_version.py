"""
APP版本管理模型
"""
from app import db
from app.utils.timezone import now as beijing_now


class AppVersion(db.Model):
    """APP版本"""
    __tablename__ = 'app_versions'
    
    PLATFORM_ANDROID = 'android'
    PLATFORM_IOS = 'ios'
    
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(20), nullable=False)  # android/ios
    version = db.Column(db.String(20), nullable=False)   # 版本号 1.0.0
    build = db.Column(db.Integer, nullable=False)        # 构建号
    download_url = db.Column(db.String(500), nullable=False)  # 下载地址
    file_size = db.Column(db.String(20))                 # 文件大小
    update_log = db.Column(db.Text)                      # 更新日志
    force_update = db.Column(db.SmallInteger, default=0) # 是否强制更新
    min_version = db.Column(db.String(20))               # 最低支持版本
    status = db.Column(db.SmallInteger, default=1)       # 状态 0禁用 1启用
    download_count = db.Column(db.Integer, default=0)    # 下载次数
    created_at = db.Column(db.DateTime, default=beijing_now)
    
    __table_args__ = (
        db.UniqueConstraint('platform', 'version', name='uk_platform_version'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'platform': self.platform,
            'version': self.version,
            'build': self.build,
            'download_url': self.download_url,
            'file_size': self.file_size,
            'update_log': self.update_log,
            'force_update': self.force_update == 1,
            'min_version': self.min_version,
            'status': self.status,
            'download_count': self.download_count,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }
    
    @classmethod
    def get_latest(cls, platform):
        """获取指定平台的最新版本"""
        return cls.query.filter_by(
            platform=platform,
            status=1
        ).order_by(cls.build.desc()).first()
    
    @staticmethod
    def compare_version(v1, v2):
        """比较版本号，v1 > v2 返回 1，v1 < v2 返回 -1，相等返回 0"""
        def parse(v):
            return [int(x) for x in v.split('.')]
        p1, p2 = parse(v1), parse(v2)
        for i in range(max(len(p1), len(p2))):
            n1 = p1[i] if i < len(p1) else 0
            n2 = p2[i] if i < len(p2) else 0
            if n1 > n2:
                return 1
            elif n1 < n2:
                return -1
        return 0
