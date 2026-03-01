"""
侧边栏菜单配置模型
"""
from datetime import datetime
from app import db


class SidebarMenu(db.Model):
    """侧边栏菜单配置"""
    __tablename__ = 'sidebar_menus'
    
    id = db.Column(db.Integer, primary_key=True)
    menu_type = db.Column(db.String(20), nullable=False, comment='菜单类型: admin/user')
    menu_key = db.Column(db.String(50), nullable=False, comment='菜单唯一标识')
    parent_key = db.Column(db.String(50), nullable=True, comment='父菜单标识')
    name_zh = db.Column(db.String(50), nullable=False, comment='中文名称')
    name_en = db.Column(db.String(50), nullable=False, comment='英文名称')
    icon = db.Column(db.Text, nullable=True, comment='图标SVG')
    url = db.Column(db.String(200), nullable=True, comment='链接地址')
    sort_order = db.Column(db.Integer, nullable=False, default=0, comment='排序')
    visible = db.Column(db.SmallInteger, nullable=False, default=1, comment='是否显示')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    __table_args__ = (
        db.UniqueConstraint('menu_type', 'menu_key', name='uk_type_key'),
    )
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'menu_type': self.menu_type,
            'menu_key': self.menu_key,
            'parent_key': self.parent_key,
            'name_zh': self.name_zh,
            'name_en': self.name_en,
            'icon': self.icon,
            'url': self.url,
            'sort_order': self.sort_order,
            'visible': self.visible == 1
        }
    
    @classmethod
    def get_menus_by_type(cls, menu_type):
        """获取指定类型的菜单列表"""
        menus = cls.query.filter_by(menu_type=menu_type).order_by(cls.sort_order).all()
        return [m.to_dict() for m in menus]
    
    @classmethod
    def get_visible_menus_by_type(cls, menu_type):
        """获取指定类型的可见菜单列表"""
        menus = cls.query.filter_by(menu_type=menu_type, visible=1).order_by(cls.sort_order).all()
        return [m.to_dict() for m in menus]
    
    @classmethod
    def get_structured_menus(cls, menu_type, visible_only=True):
        """获取结构化的菜单数据（一级菜单包含子菜单）"""
        query = cls.query.filter_by(menu_type=menu_type)
        if visible_only:
            query = query.filter_by(visible=1)
        menus = query.order_by(cls.sort_order).all()
        
        # 分离一级菜单和子菜单
        parent_menus = []
        child_menus = {}
        
        for menu in menus:
            menu_dict = menu.to_dict()
            if menu.parent_key is None:
                menu_dict['children'] = []
                parent_menus.append(menu_dict)
            else:
                if menu.parent_key not in child_menus:
                    child_menus[menu.parent_key] = []
                child_menus[menu.parent_key].append(menu_dict)
        
        # 将子菜单挂载到父菜单
        for parent in parent_menus:
            parent['children'] = child_menus.get(parent['menu_key'], [])
        
        return parent_menus
    
    @classmethod
    def update_visibility(cls, menu_type, menu_key, visible):
        """更新菜单可见性"""
        menu = cls.query.filter_by(menu_type=menu_type, menu_key=menu_key).first()
        if menu:
            menu.visible = 1 if visible else 0
            db.session.commit()
            return True
        return False
    
    @classmethod
    def update_sort_order(cls, menu_type, menu_orders):
        """批量更新菜单排序
        menu_orders: [{'menu_key': 'xxx', 'sort_order': 1}, ...]
        """
        for item in menu_orders:
            menu = cls.query.filter_by(menu_type=menu_type, menu_key=item['menu_key']).first()
            if menu:
                menu.sort_order = item['sort_order']
        db.session.commit()
        return True
