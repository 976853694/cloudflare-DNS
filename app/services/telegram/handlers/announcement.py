"""
系统公告处理器

处理公告列表、详情等功能
"""

from datetime import datetime
from .base import BaseHandler


class AnnouncementHandler(BaseHandler):
    """系统公告处理器"""
    
    PAGE_SIZE = 5
    
    def handle_callback(self, chat_id: int, message_id: int, telegram_id: int,
                       user_info: dict, data: str):
        """
        处理回调
        
        Args:
            chat_id: 聊天 ID
            message_id: 消息 ID
            telegram_id: Telegram 用户 ID
            user_info: Telegram 用户信息
            data: 回调数据
        """
        parts = data.split(':')
        
        if data == 'announcement:list' or data.startswith('menu:announcements'):
            self._show_announcement_list(chat_id, message_id)
        elif data.startswith('page:announcements:'):
            try:
                page = int(parts[2])
            except:
                page = 1
            self._show_announcement_list(chat_id, message_id, page)
        elif len(parts) >= 2 and parts[0] == 'announcement':
            try:
                ann_id = int(parts[1])
                self._show_announcement_detail(chat_id, message_id, ann_id)
            except:
                text = "❌ 参数错误"
                keyboard = self.make_keyboard([[{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]])
                self.edit_message(chat_id, message_id, text, keyboard)
    
    def _show_announcement_list(self, chat_id: int, message_id: int, page: int = 1):
        """
        显示公告列表
        
        Args:
            chat_id: 聊天 ID
            message_id: 消息 ID
            page: 页码
        """
        try:
            from app.models.announcement import Announcement
            
            # 查询公告，置顶优先，然后按时间倒序
            query = Announcement.query.filter_by(status=1)
            query = query.order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
            
            total = query.count()
            total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            page = max(1, min(page, total_pages))
            
            announcements = query.offset((page - 1) * self.PAGE_SIZE).limit(self.PAGE_SIZE).all()
            
            if total == 0:
                text = "📢 系统公告\n\n暂无公告"
            else:
                text = f"📢 系统公告\n\n共 {total} 条公告"
            
            keyboard = self._build_announcement_list_keyboard(announcements, page, total_pages)
            
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[AnnouncementHandler] List error: {e}')
            text = "📢 系统公告\n\n加载失败"
            keyboard = self.make_keyboard([[{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]])
            self.edit_message(chat_id, message_id, text, keyboard)
    
    def _build_announcement_list_keyboard(self, announcements, page: int, total_pages: int):
        """构建公告列表键盘"""
        buttons = []
        
        for ann in announcements:
            # 置顶图标
            icon = '📌' if ann.is_pinned else '📄'
            title = ann.title[:20] + '...' if len(ann.title) > 20 else ann.title
            
            buttons.append([{'text': f'{icon} {title}', 'callback_data': f'announcement:{ann.id}'}])
        
        # 分页
        if total_pages > 1:
            nav_buttons = []
            if page > 1:
                nav_buttons.append({'text': '◀️ 上一页', 'callback_data': f'page:announcements:{page - 1}'})
            nav_buttons.append({'text': f'{page}/{total_pages}', 'callback_data': 'noop'})
            if page < total_pages:
                nav_buttons.append({'text': '下一页 ▶️', 'callback_data': f'page:announcements:{page + 1}'})
            buttons.append(nav_buttons)
        
        buttons.append([{'text': '🏠 主菜单', 'callback_data': 'menu:main'}])
        
        return self.make_keyboard(buttons)
    
    def _show_announcement_detail(self, chat_id: int, message_id: int, ann_id: int):
        """
        显示公告详情
        
        Args:
            chat_id: 聊天 ID
            message_id: 消息 ID
            ann_id: 公告 ID
        """
        try:
            from app.models.announcement import Announcement
            
            ann = Announcement.query.get(ann_id)
            if not ann or ann.status != 1:
                text = "❌ 公告不存在"
                keyboard = self.make_keyboard([[{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]])
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            date_str = ann.created_at.strftime('%Y-%m-%d %H:%M') if ann.created_at else ''
            
            text = f"📢 {ann.title}\n\n"
            text += f"{ann.content}\n\n"
            text += f"📅 {date_str}"
            
            if ann.is_pinned:
                text += " | 📌 置顶"
            
            keyboard = self.make_keyboard([
                [{'text': '◀️ 返回列表', 'callback_data': 'announcement:list'}],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ])
            
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[AnnouncementHandler] Detail error: {e}')
            text = "❌ 加载失败"
            keyboard = self.make_keyboard([[{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]])
            self.edit_message(chat_id, message_id, text, keyboard)
