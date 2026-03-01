"""
DNS 记录处理器

处理 DNS 记录的增删改查
"""

from .base import BaseHandler


class DNSHandler(BaseHandler):
    """DNS 记录处理器"""
    
    PAGE_SIZE = 5
    
    def handle_callback(self, chat_id: int, message_id: int, telegram_id: int,
                       user_info: dict, data: str):
        """处理回调"""
        if not self.require_bind(chat_id, telegram_id, message_id):
            return
        
        user = self.get_user(telegram_id)
        parts = data.split(':')
        action = parts[1] if len(parts) > 1 else ''
        
        if action == 'list' and len(parts) > 2:
            domain_id = int(parts[2])
            page = int(parts[3]) if len(parts) > 3 else 1
            self._show_dns_list(chat_id, message_id, user, telegram_id, domain_id, page)
        elif action == 'add' and len(parts) > 2:
            domain_id = int(parts[2])
            self._show_add_type_select(chat_id, message_id, telegram_id, domain_id)
        elif action == 'type' and len(parts) > 3:
            domain_id = int(parts[2])
            record_type = parts[3]
            self._handle_type_select(chat_id, message_id, telegram_id, domain_id, record_type)
        elif action == 'record' and len(parts) > 2:
            record_id = parts[2]
            domain_id = int(parts[3]) if len(parts) > 3 else 0
            self._show_record_detail(chat_id, message_id, user, telegram_id, record_id, domain_id)
        elif action == 'delete' and len(parts) > 2:
            record_id = parts[2]
            domain_id = int(parts[3]) if len(parts) > 3 else 0
            self._show_delete_confirm(chat_id, message_id, telegram_id, record_id, domain_id)
        elif action == 'delete_confirm' and len(parts) > 2:
            record_id = parts[2]
            domain_id = int(parts[3]) if len(parts) > 3 else 0
            self._do_delete_record(chat_id, message_id, user, telegram_id, record_id, domain_id)
        elif action == 'toggle_proxy' and len(parts) > 2:
            record_id = parts[2]
            domain_id = int(parts[3]) if len(parts) > 3 else 0
            self._toggle_proxy(chat_id, message_id, user, telegram_id, record_id, domain_id)
        elif action == 'proxy' and len(parts) > 3:
            domain_id = int(parts[2])
            proxied = parts[3] == '1'
            self._handle_proxy_select(chat_id, message_id, telegram_id, domain_id, proxied)
        elif action == 'confirm':
            self._handle_confirm(chat_id, message_id, user, telegram_id)
    
    def handle_text_input(self, chat_id: int, telegram_id: int, text: str, session: dict) -> bool:
        """处理文本输入"""
        state = session.get('state', '')
        
        if state == 'dns_add_name':
            return self._handle_name_input(chat_id, telegram_id, text, session)
        elif state == 'dns_add_value':
            return self._handle_value_input(chat_id, telegram_id, text, session)
        elif state == 'dns_edit_value':
            return self._handle_edit_value_input(chat_id, telegram_id, text, session)
        
        return False
    
    def _show_dns_list(self, chat_id: int, message_id: int, user, 
                      telegram_id: int, domain_id: int, page: int = 1):
        """显示 DNS 记录列表"""
        try:
            from app.models.subdomain import Subdomain
            from app.models.record import DnsRecord
            
            domain = Subdomain.query.filter_by(id=domain_id, user_id=user.id).first()
            if not domain:
                text = '❌ 域名不存在'
                buttons = [[{'text': '🏠 返回主菜单', 'callback_data': 'menu:main'}]]
                keyboard = self.make_keyboard(buttons)
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            # 从数据库获取 DNS 记录
            records = DnsRecord.query.filter_by(subdomain_id=domain_id).all()
            
            total = len(records)
            total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            page = max(1, min(page, total_pages))
            
            start = (page - 1) * self.PAGE_SIZE
            end = start + self.PAGE_SIZE
            page_records = records[start:end]
            
            text = f"📝 DNS 记录\n\n"
            text += f"域名：{domain.full_domain}\n"
            text += f"共 {total} 条记录"
            
            if total > 0:
                text += f"（第 {page}/{total_pages} 页）\n\n"
                for r in page_records:
                    proxy_icon = '🟠' if r.proxied else '⚪'
                    text += f"{proxy_icon} {r.type} | {r.name or '@'}\n"
                    value = (r.content or '')[:30]
                    if len(r.content or '') > 30:
                        value += '...'
                    text += f"   → {value}\n"
            
            buttons = []
            
            # 记录按钮
            for r in page_records:
                record_id = r.id
                name = (r.name or '@')[:15]
                buttons.append([{
                    'text': f"{r.type} | {name}",
                    'callback_data': f'dns:record:{record_id}:{domain_id}'
                }])
            
            # 分页
            if total_pages > 1:
                nav = []
                if page > 1:
                    nav.append({'text': '◀️', 'callback_data': f'dns:list:{domain_id}:{page-1}'})
                if page < total_pages:
                    nav.append({'text': '▶️', 'callback_data': f'dns:list:{domain_id}:{page+1}'})
                if nav:
                    buttons.append(nav)
            
            buttons.append([{'text': '➕ 添加记录', 'callback_data': f'dns:add:{domain_id}'}])
            buttons.append([
                {'text': '◀️ 返回域名', 'callback_data': f'domain:{domain_id}'},
                {'text': '🏠 主菜单', 'callback_data': 'menu:main'}
            ])
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[DNSHandler] List error: {e}')
            import traceback
            traceback.print_exc()
            self.handle_error(chat_id, e, message_id, telegram_id=telegram_id)
    
    def _show_add_type_select(self, chat_id: int, message_id: int, 
                             telegram_id: int, domain_id: int):
        """显示记录类型选择"""
        text = "➕ 添加 DNS 记录\n\n请选择记录类型："
        
        buttons = [
            [
                {'text': 'A', 'callback_data': f'dns:type:{domain_id}:A'},
                {'text': 'AAAA', 'callback_data': f'dns:type:{domain_id}:AAAA'},
                {'text': 'CNAME', 'callback_data': f'dns:type:{domain_id}:CNAME'}
            ],
            [
                {'text': 'TXT', 'callback_data': f'dns:type:{domain_id}:TXT'},
                {'text': 'MX', 'callback_data': f'dns:type:{domain_id}:MX'},
                {'text': 'NS', 'callback_data': f'dns:type:{domain_id}:NS'}
            ],
            [{'text': '❌ 取消', 'callback_data': f'dns:list:{domain_id}'}]
        ]
        
        keyboard = self.make_keyboard(buttons)
        self.edit_message(chat_id, message_id, text, keyboard)
    
    def _handle_type_select(self, chat_id: int, message_id: int,
                           telegram_id: int, domain_id: int, record_type: str):
        """处理类型选择"""
        # 设置会话状态
        self.set_session_state(chat_id, 'dns_add_name', {
            'domain_id': domain_id,
            'record_type': record_type,
            'message_id': message_id
        })
        
        text = f"➕ 添加 {record_type} 记录\n\n"
        text += "请输入记录名称：\n"
        text += "（输入 @ 表示根域名，或输入子域名前缀）"
        
        buttons = [[{'text': '❌ 取消', 'callback_data': f'dns:list:{domain_id}'}]]
        keyboard = self.make_keyboard(buttons)
        self.edit_message(chat_id, message_id, text, keyboard)
    
    def _handle_name_input(self, chat_id: int, telegram_id: int, text: str, session: dict) -> bool:
        """处理名称输入"""
        # 从 session['data'] 获取数据
        data = session.get('data', {})
        domain_id = data.get('domain_id')
        record_type = data.get('record_type')
        message_id = data.get('message_id')
        
        name = text.strip()
        
        # 更新会话
        self.set_session_state(chat_id, 'dns_add_value', {
            'domain_id': domain_id,
            'record_type': record_type,
            'record_name': name,
            'message_id': message_id
        })
        
        msg = f"➕ 添加 {record_type} 记录\n\n"
        msg += f"名称：{name}\n\n"
        msg += "请输入记录值："
        
        if record_type == 'A':
            msg += "\n（IPv4 地址，如 1.2.3.4）"
        elif record_type == 'AAAA':
            msg += "\n（IPv6 地址）"
        elif record_type == 'CNAME':
            msg += "\n（目标域名，如 example.com）"
        
        buttons = [[{'text': '❌ 取消', 'callback_data': f'dns:list:{domain_id}'}]]
        keyboard = self.make_keyboard(buttons)
        self.send_message(chat_id, msg, keyboard)
        
        return True
    
    def _handle_value_input(self, chat_id: int, telegram_id: int, text: str, session: dict) -> bool:
        """处理值输入"""
        # 从 session['data'] 获取数据
        data = session.get('data', {})
        domain_id = data.get('domain_id')
        record_type = data.get('record_type')
        record_name = data.get('record_name')
        
        value = text.strip()
        
        # 检查是否支持代理
        if record_type in ['A', 'AAAA', 'CNAME']:
            self.set_session_state(chat_id, 'dns_add_proxy', {
                'domain_id': domain_id,
                'record_type': record_type,
                'record_name': record_name,
                'record_value': value
            })
            
            msg = f"➕ 添加 {record_type} 记录\n\n"
            msg += f"名称：{record_name}\n"
            msg += f"值：{value}\n\n"
            msg += "是否开启 Cloudflare 代理？"
            
            buttons = [
                [
                    {'text': '🟠 开启代理', 'callback_data': f'dns:proxy:{domain_id}:1'},
                    {'text': '⚪ 不代理', 'callback_data': f'dns:proxy:{domain_id}:0'}
                ],
                [{'text': '❌ 取消', 'callback_data': f'dns:list:{domain_id}'}]
            ]
            keyboard = self.make_keyboard(buttons)
            self.send_message(chat_id, msg, keyboard)
        else:
            # 直接创建记录
            self._create_record(chat_id, telegram_id, domain_id, record_type, record_name, value, False)
        
        return True
    
    def _handle_proxy_select(self, chat_id: int, message_id: int,
                            telegram_id: int, domain_id: int, proxied: bool):
        """处理代理选择"""
        session = self.get_session_state(chat_id)
        if not session:
            return
        
        # 从 session['data'] 获取数据
        data = session.get('data', {})
        record_type = data.get('record_type')
        record_name = data.get('record_name')
        record_value = data.get('record_value')
        
        self.clear_session_state(chat_id)
        self._create_record(chat_id, telegram_id, domain_id, record_type, record_name, record_value, proxied)
    
    def _create_record(self, chat_id: int, telegram_id: int, domain_id: int,
                      record_type: str, name: str, value: str, proxied: bool):
        """创建 DNS 记录"""
        try:
            from app.models.subdomain import Subdomain
            from app.services.domain_service import DomainService
            
            user = self.get_user(telegram_id)
            domain = Subdomain.query.filter_by(id=domain_id, user_id=user.id).first()
            if not domain:
                self.send_message(chat_id, '❌ 域名不存在')
                return
            
            # 创建记录
            record = DomainService.create_dns_record(domain, record_type, name, value, proxied=proxied)
            
            if record:
                text = f"✅ 记录添加成功！\n\n"
                text += f"类型：{record_type}\n"
                text += f"名称：{name}\n"
                text += f"值：{value}\n"
                if proxied:
                    text += "代理：🟠 已开启"
            else:
                text = "❌ 添加失败，请稍后重试"
            
            buttons = [
                [{'text': '📝 查看记录', 'callback_data': f'dns:list:{domain_id}'}],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ]
            keyboard = self.make_keyboard(buttons)
            self.send_message(chat_id, text, keyboard)
            
        except ValueError as e:
            self.send_message(chat_id, f'❌ 添加失败：{str(e)}')
        except Exception as e:
            print(f'[DNSHandler] Create error: {e}')
            self.send_message(chat_id, f'❌ 添加失败：{str(e)}')
    
    def _show_record_detail(self, chat_id: int, message_id: int, user,
                           telegram_id: int, record_id: str, domain_id: int):
        """显示记录详情"""
        try:
            from app.models.subdomain import Subdomain
            from app.models.record import DnsRecord
            
            domain = Subdomain.query.filter_by(id=domain_id, user_id=user.id).first()
            if not domain:
                return
            
            record = DnsRecord.query.filter_by(id=record_id, subdomain_id=domain_id).first()
            
            if not record:
                text = '❌ 记录不存在'
                buttons = [[{'text': '◀️ 返回', 'callback_data': f'dns:list:{domain_id}'}]]
                keyboard = self.make_keyboard(buttons)
                self.edit_message(chat_id, message_id, text, keyboard)
                return
            
            proxy_status = '🟠 已开启' if record.proxied else '⚪ 未开启'
            
            text = f"📝 记录详情\n\n"
            text += f"类型：{record.type}\n"
            text += f"名称：{record.name}\n"
            text += f"值：{record.content}\n"
            text += f"TTL：{record.ttl or 'Auto'}\n"
            text += f"代理：{proxy_status}"
            
            buttons = []
            
            # 代理切换按钮
            if record.type in ['A', 'AAAA', 'CNAME']:
                proxy_text = '⚪ 关闭代理' if record.proxied else '🟠 开启代理'
                buttons.append([{'text': proxy_text, 'callback_data': f'dns:toggle_proxy:{record_id}:{domain_id}'}])
            
            buttons.append([{'text': '🗑️ 删除', 'callback_data': f'dns:delete:{record_id}:{domain_id}'}])
            buttons.append([
                {'text': '◀️ 返回列表', 'callback_data': f'dns:list:{domain_id}'},
                {'text': '🏠 主菜单', 'callback_data': 'menu:main'}
            ])
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except Exception as e:
            print(f'[DNSHandler] Detail error: {e}')
    
    def _show_delete_confirm(self, chat_id: int, message_id: int,
                            telegram_id: int, record_id: str, domain_id: int):
        """显示删除确认"""
        text = "⚠️ 确定要删除这条记录吗？\n\n此操作不可恢复"
        
        buttons = [
            [{'text': '✅ 确认删除', 'callback_data': f'dns:delete_confirm:{record_id}:{domain_id}'}],
            [{'text': '❌ 取消', 'callback_data': f'dns:record:{record_id}:{domain_id}'}]
        ]
        
        keyboard = self.make_keyboard(buttons)
        self.edit_message(chat_id, message_id, text, keyboard)
    
    def _do_delete_record(self, chat_id: int, message_id: int, user,
                         telegram_id: int, record_id: str, domain_id: int):
        """执行删除"""
        try:
            from app.models.subdomain import Subdomain
            from app.models.record import DnsRecord
            from app.services.domain_service import DomainService
            
            domain = Subdomain.query.filter_by(id=domain_id, user_id=user.id).first()
            if not domain:
                return
            
            record = DnsRecord.query.filter_by(id=record_id, subdomain_id=domain_id).first()
            if not record:
                text = "❌ 记录不存在"
            else:
                DomainService.delete_dns_record(record)
                text = "✅ 记录已删除"
            
            buttons = [
                [{'text': '📝 查看记录', 'callback_data': f'dns:list:{domain_id}'}],
                [{'text': '🏠 主菜单', 'callback_data': 'menu:main'}]
            ]
            
            keyboard = self.make_keyboard(buttons)
            self.edit_message(chat_id, message_id, text, keyboard)
            
        except ValueError as e:
            self.edit_message(chat_id, message_id, f'❌ 删除失败：{str(e)}')
        except Exception as e:
            print(f'[DNSHandler] Delete error: {e}')
    
    def _toggle_proxy(self, chat_id: int, message_id: int, user,
                     telegram_id: int, record_id: str, domain_id: int):
        """切换代理状态"""
        try:
            from app.models.subdomain import Subdomain
            from app.models.record import DnsRecord
            from app.services.domain_service import DomainService
            
            domain = Subdomain.query.filter_by(id=domain_id, user_id=user.id).first()
            if not domain:
                return
            
            record = DnsRecord.query.filter_by(id=record_id, subdomain_id=domain_id).first()
            if not record:
                return
            
            new_proxied = not record.proxied
            DomainService.update_dns_record(record, proxied=new_proxied)
            
            self._show_record_detail(chat_id, message_id, user, telegram_id, record_id, domain_id)
            
        except ValueError as e:
            self.edit_message(chat_id, message_id, f'❌ 操作失败：{str(e)}')
        except Exception as e:
            print(f'[DNSHandler] Toggle proxy error: {e}')
    
    def _handle_edit_value_input(self, chat_id: int, telegram_id: int, text: str, session: dict) -> bool:
        """处理编辑值输入"""
        # 暂不实现
        return False
    
    def _handle_confirm(self, chat_id: int, message_id: int, user, telegram_id: int):
        """处理确认"""
        # 暂不实现
        pass
