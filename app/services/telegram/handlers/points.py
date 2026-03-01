"""
积分系统处理器

处理积分相关的所有交互：
- 积分中心菜单
- 签到
- 积分兑换
- 积分记录
- 积分续费
"""

from typing import Dict, Any
from .base import BaseHandler
from ..utils.session import SessionManager


class PointsHandler(BaseHandler):
    """积分系统处理器"""
    
    PAGE_SIZE = 5
    
    def handle_callback(self, chat_id: int, message_id: int,
                       telegram_id: int, user_info: Dict, data: str):
        """
        处理回调
        
        Args:
            chat_id: 聊天 ID
            message_id: 消息 ID
            telegram_id: Telegram 用户 ID
            user_info: 用户信息
            data: 回调数据
        """
        # 检查绑定
        if not self.require_bind(chat_id, telegram_id, message_id):
            return
        
        # 解析回调数据
        parts = data.split(':')
        action = parts[1] if len(parts) > 1 else ''
        
        try:
            if action == 'menu':
                self.show_points_menu(chat_id, message_id, telegram_id)
            
            elif action == 'signin':
                self.do_signin(chat_id, message_id, telegram_id)
            
            elif action == 'exchange':
                self.show_exchange_prompt(chat_id, message_id, telegram_id)
            
            elif action == 'exchange_confirm':
                amount = int(parts[2]) if len(parts) > 2 else 0
                self.do_exchange(chat_id, message_id, telegram_id, amount)
            
            elif action == 'history':
                page = int(parts[2]) if len(parts) > 2 else 1
                self.show_points_history(chat_id, message_id, telegram_id, page)
            
            elif action == 'renew':
                domain_id = int(parts[2]) if len(parts) > 2 else 0
                self.show_points_renew(chat_id, message_id, telegram_id, domain_id)
            
            elif action == 'renew_confirm':
                domain_id = int(parts[2]) if len(parts) > 2 else 0
                self.do_points_renew(chat_id, message_id, telegram_id, domain_id)
            
            else:
                self._show_error(chat_id, message_id, telegram_id, '未知操作')
                
        except Exception as e:
            print(f'[PointsHandler] Callback error: {e}')
            import traceback
            traceback.print_exc()
            self._show_error(chat_id, message_id, telegram_id, str(e))
    
    def handle_text_input(self, chat_id: int, telegram_id: int,
                         text: str, session: Dict, chat_type: str = 'private') -> bool:
        """
        处理文本输入
        
        Args:
            chat_id: 聊天 ID
            telegram_id: Telegram 用户 ID
            text: 输入文本
            session: 会话数据
            chat_type: 聊天类型 (private/group/supergroup)
            
        Returns:
            是否已处理
        """
        state = session.get('state', '')
        data = session.get('data', {})
        
        if state == SessionManager.POINTS_INPUT_AMOUNT:
            return self._handle_exchange_input(chat_id, telegram_id, text, data, chat_type)
        
        return False
    
    def show_points_menu(self, chat_id: int, message_id: int, telegram_id: int):
        """显示积分中心菜单"""
        user = self.get_user(telegram_id)
        if not user:
            return
        
        points = getattr(user, 'points', 0) or 0
        
        text = self.get_text('points.title', telegram_id) + "\n\n"
        text += self.get_text('points.balance', telegram_id, points=points)
        
        buttons = [
            [{'text': self.get_text('points.btn_signin', telegram_id),
              'callback_data': 'points:signin'}],
            [{'text': self.get_text('points.btn_exchange', telegram_id),
              'callback_data': 'points:exchange'}],
            [{'text': self.get_text('points.btn_history', telegram_id),
              'callback_data': 'points:history:1'}],
            [{'text': self.get_text('common.main_menu', telegram_id),
              'callback_data': 'menu:main'}]
        ]
        
        self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
    
    def do_signin(self, chat_id: int, message_id: int, telegram_id: int):
        """执行签到"""
        user = self.get_user(telegram_id)
        if not user:
            return
        
        try:
            from app.services.points_service import PointsService
            
            result = PointsService.signin(user.id)
            
            if result.get('already_signed'):
                text = self.get_text('points.signin_already', telegram_id)
            else:
                points = result.get('points', 0)
                text = self.get_text('points.signin_success', telegram_id, points=points)
                
                # 连续签到奖励
                consecutive = result.get('consecutive_days', 0)
                bonus = result.get('bonus', 0)
                if bonus > 0:
                    text += "\n" + self.get_text('points.signin_bonus', telegram_id,
                        days=consecutive, bonus=bonus)
                
                # 累计签到
                total = result.get('total_days', 0)
                text += "\n" + self.get_text('points.signin_total', telegram_id, total=total)
            
            buttons = [
                [{'text': '💰 积分中心', 'callback_data': 'points:menu'}],
                [{'text': self.get_text('common.main_menu', telegram_id),
                  'callback_data': 'menu:main'}]
            ]
            
            self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
            
        except Exception as e:
            print(f'[PointsHandler] Signin error: {e}')
            self._show_error(chat_id, message_id, telegram_id, '签到失败，请稍后重试')

    def show_exchange_prompt(self, chat_id: int, message_id: int, telegram_id: int):
        """显示兑换提示"""
        user = self.get_user(telegram_id)
        if not user:
            return
        
        try:
            from app.models.setting import Setting
            
            # 获取兑换配置
            rate = int(Setting.get('points_exchange_rate', '100'))
            min_amount = int(Setting.get('points_min_exchange', '100'))
            max_amount = int(Setting.get('points_max_daily_exchange', '10000'))
            balance = getattr(user, 'points', 0) or 0
            
            # 设置会话状态
            self.set_session_state(chat_id, SessionManager.POINTS_INPUT_AMOUNT, {
                'rate': rate,
                'min': min_amount,
                'max': max_amount
            })
            
            text = self.get_text('points.exchange_prompt', telegram_id,
                rate=rate, min=min_amount, max=max_amount, balance=balance)
            
            buttons = [
                [{'text': self.get_text('common.cancel', telegram_id),
                  'callback_data': 'points:menu'}]
            ]
            
            self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
            
        except Exception as e:
            print(f'[PointsHandler] Exchange prompt error: {e}')
            self._show_error(chat_id, message_id, telegram_id, '获取配置失败')
    
    def _handle_exchange_input(self, chat_id: int, telegram_id: int,
                              text: str, data: Dict, chat_type: str = 'private') -> bool:
        """处理兑换数量输入"""
        # 检查是否在群聊中
        if chat_type != 'private':
            msg = '⚠️ 为保护您的隐私，积分兑换只能在私聊中进行\n\n请点击机器人头像，在私聊中完成兑换操作'
            self.send_message(chat_id, msg)
            return True
        
        user = self.get_user(telegram_id)
        if not user:
            return True
        
        # 验证输入
        try:
            amount = int(text.strip())
        except ValueError:
            msg = self.get_text('points.exchange_error_invalid', telegram_id)
            buttons = [[{'text': self.get_text('common.cancel', telegram_id),
                        'callback_data': 'points:menu'}]]
            self.send_message(chat_id, msg, self.make_keyboard(buttons))
            return True
        
        rate = data.get('rate', 100)
        min_amount = data.get('min', 100)
        max_amount = data.get('max', 10000)
        balance = getattr(user, 'points', 0) or 0
        
        # 验证最低限制
        if amount < min_amount:
            msg = self.get_text('points.exchange_error_min', telegram_id, min=min_amount)
            buttons = [[{'text': self.get_text('common.cancel', telegram_id),
                        'callback_data': 'points:menu'}]]
            self.send_message(chat_id, msg, self.make_keyboard(buttons))
            return True
        
        # 验证余额
        if amount > balance:
            msg = self.get_text('points.exchange_error_insufficient', telegram_id, balance=balance)
            buttons = [[{'text': self.get_text('common.cancel', telegram_id),
                        'callback_data': 'points:menu'}]]
            self.send_message(chat_id, msg, self.make_keyboard(buttons))
            return True
        
        # 计算兑换金额
        exchange_amount = amount / rate
        
        # 显示确认
        text = self.get_text('points.exchange_confirm', telegram_id,
            points=amount, amount=f'{exchange_amount:.2f}')
        
        buttons = [
            [{'text': self.get_text('common.confirm', telegram_id),
              'callback_data': f'points:exchange_confirm:{amount}'}],
            [{'text': self.get_text('common.cancel', telegram_id),
              'callback_data': 'points:menu'}]
        ]
        
        self.send_message(chat_id, text, self.make_keyboard(buttons))
        return True
    
    def do_exchange(self, chat_id: int, message_id: int,
                   telegram_id: int, amount: int):
        """执行兑换"""
        user = self.get_user(telegram_id)
        if not user:
            return
        
        # 清除会话
        self.clear_session_state(chat_id)
        
        try:
            from app.services.points_service import PointsService
            
            result = PointsService.exchange(user.id, amount)
            
            if result.get('success'):
                text = self.get_text('points.exchange_success', telegram_id,
                    points=amount, amount=f"{result.get('balance_added', 0):.2f}")
            else:
                error = result.get('error', '兑换失败')
                text = f"❌ {error}"
            
            buttons = [
                [{'text': '💰 积分中心', 'callback_data': 'points:menu'}],
                [{'text': self.get_text('common.main_menu', telegram_id),
                  'callback_data': 'menu:main'}]
            ]
            
            self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
            
        except ValueError as e:
            error_msg = str(e)
            if '|' in error_msg:
                error_msg = error_msg.split('|')[1]
            self._show_error(chat_id, message_id, telegram_id, error_msg)
        except Exception as e:
            print(f'[PointsHandler] Exchange error: {e}')
            self._show_error(chat_id, message_id, telegram_id, '兑换失败，请稍后重试')
    
    def show_points_history(self, chat_id: int, message_id: int,
                           telegram_id: int, page: int = 1):
        """显示积分记录"""
        user = self.get_user(telegram_id)
        if not user:
            return
        
        try:
            from app.models.point_record import PointRecord
            
            query = PointRecord.query.filter_by(user_id=user.id)\
                .order_by(PointRecord.created_at.desc())
            
            total = query.count()
            total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            page = max(1, min(page, total_pages))
            
            records = query.offset((page - 1) * self.PAGE_SIZE).limit(self.PAGE_SIZE).all()
            
            text = self.get_text('points.history', telegram_id) + "\n\n"
            
            if not records:
                text += self.get_text('points.history_empty', telegram_id)
            else:
                type_map = {
                    'signin': self.get_text('points.type_signin', telegram_id),
                    'exchange': self.get_text('points.type_exchange', telegram_id),
                    'renew': self.get_text('points.type_renew', telegram_id),
                    'transfer': self.get_text('points.type_transfer', telegram_id),
                    'reward': self.get_text('points.type_reward', telegram_id),
                    'deduct': self.get_text('points.type_deduct', telegram_id)
                }
                
                for record in records:
                    type_text = type_map.get(record.type, record.type)
                    points_str = f"+{record.points}" if record.points > 0 else str(record.points)
                    time_str = record.created_at.strftime('%m-%d %H:%M')
                    
                    text += f"{type_text} {points_str} 积分\n"
                    text += f"  {record.description or ''}\n"
                    text += f"  {time_str}\n\n"
            
            # 分页按钮
            buttons = []
            nav_row = []
            if page > 1:
                nav_row.append({'text': '⬅️', 'callback_data': f'points:history:{page-1}'})
            if total_pages > 0:
                nav_row.append({'text': f'{page}/{total_pages}', 'callback_data': 'noop'})
            if page < total_pages:
                nav_row.append({'text': '➡️', 'callback_data': f'points:history:{page+1}'})
            if nav_row:
                buttons.append(nav_row)
            
            buttons.append([{'text': '💰 积分中心', 'callback_data': 'points:menu'}])
            buttons.append([{'text': self.get_text('common.main_menu', telegram_id),
                           'callback_data': 'menu:main'}])
            
            self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
            
        except Exception as e:
            print(f'[PointsHandler] History error: {e}')
            self._show_error(chat_id, message_id, telegram_id, '获取记录失败')

    def show_points_renew(self, chat_id: int, message_id: int,
                         telegram_id: int, domain_id: int):
        """显示积分续费信息"""
        user = self.get_user(telegram_id)
        if not user:
            return
        
        try:
            from app.models.subdomain import Subdomain
            from app.models.setting import Setting
            
            domain = Subdomain.query.filter_by(id=domain_id, user_id=user.id).first()
            if not domain:
                self._show_error(chat_id, message_id, telegram_id, '域名不存在')
                return
            
            # 检查积分续费是否开启
            enabled = Setting.get('points_renew_enabled', '0') == '1'
            if not enabled:
                text = self.get_text('points.renew_error_disabled', telegram_id)
                buttons = [[{'text': '◀️ 返回', 'callback_data': f'domain:{domain_id}'}]]
                self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
                return
            
            # 获取续费配置
            days = int(Setting.get('points_renew_days', '30'))
            points_needed = int(Setting.get('points_renew_cost', '100'))
            balance = getattr(user, 'points', 0) or 0
            
            text = self.get_text('points.renew_info', telegram_id,
                domain=domain.full_domain,
                days=days,
                points=points_needed,
                balance=balance
            )
            
            buttons = [
                [{'text': self.get_text('common.confirm', telegram_id),
                  'callback_data': f'points:renew_confirm:{domain_id}'}],
                [{'text': self.get_text('common.cancel', telegram_id),
                  'callback_data': f'domain:{domain_id}'}]
            ]
            
            self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
            
        except Exception as e:
            print(f'[PointsHandler] Points renew error: {e}')
            self._show_error(chat_id, message_id, telegram_id, '获取信息失败')
    
    def do_points_renew(self, chat_id: int, message_id: int,
                       telegram_id: int, domain_id: int):
        """执行积分续费"""
        user = self.get_user(telegram_id)
        if not user:
            return
        
        try:
            from app import db
            from app.models.subdomain import Subdomain
            from app.models.setting import Setting
            from app.models.point_record import PointRecord
            from datetime import datetime, timedelta
            
            domain = Subdomain.query.filter_by(id=domain_id, user_id=user.id).first()
            if not domain:
                self._show_error(chat_id, message_id, telegram_id, '域名不存在')
                return
            
            # 获取配置
            days = int(Setting.get('points_renew_days', '30'))
            points_needed = int(Setting.get('points_renew_cost', '100'))
            balance = getattr(user, 'points', 0) or 0
            
            # 验证积分
            if balance < points_needed:
                text = self.get_text('points.renew_error_insufficient', telegram_id,
                    points=points_needed, balance=balance)
                buttons = [
                    [{'text': '💰 积分中心', 'callback_data': 'points:menu'}],
                    [{'text': '◀️ 返回', 'callback_data': f'domain:{domain_id}'}]
                ]
                self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
                return
            
            # 扣除积分
            user.points -= points_needed
            
            # 延长到期时间
            now = datetime.now()
            if domain.expires_at < now:
                domain.expires_at = now + timedelta(days=days)
            else:
                domain.expires_at += timedelta(days=days)
            
            # 记录积分变动
            record = PointRecord(
                user_id=user.id,
                type='renew',
                points=-points_needed,
                balance=user.points,
                description=f'积分续费 ({domain.full_domain})',
                related_id=domain_id
            )
            db.session.add(record)
            db.session.commit()
            
            text = self.get_text('points.renew_success', telegram_id,
                domain=domain.full_domain,
                days=days,
                points=points_needed
            )
            
            buttons = [
                [{'text': '🌐 查看域名', 'callback_data': f'domain:{domain_id}'}],
                [{'text': self.get_text('common.main_menu', telegram_id),
                  'callback_data': 'menu:main'}]
            ]
            
            self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
            
        except Exception as e:
            print(f'[PointsHandler] Points renew execute error: {e}')
            import traceback
            traceback.print_exc()
            self._show_error(chat_id, message_id, telegram_id, '续费失败，请稍后重试')
    
    def _show_error(self, chat_id: int, message_id: int,
                   telegram_id: int, error: str):
        """显示错误消息"""
        text = f"❌ {error}"
        buttons = [[{'text': self.get_text('common.main_menu', telegram_id),
                    'callback_data': 'menu:main'}]]
        self.edit_message(chat_id, message_id, text, self.make_keyboard(buttons))
