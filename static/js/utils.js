/**
 * 六趣DNS - 前端工具函数
 * 提供通用的API请求、通知提示、表单处理等功能
 */

// API 请求工具
const API = {
    /**
     * 获取认证头
     */
    getAuthHeaders() {
        const token = localStorage.getItem('token');
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    },

    /**
     * 通用请求方法
     * @param {string} url - 请求URL
     * @param {object} options - 请求选项
     * @returns {Promise}
     */
    async request(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                ...this.getAuthHeaders()
            }
        };

        const config = { ...defaultOptions, ...options };
        if (options.headers) {
            config.headers = { ...defaultOptions.headers, ...options.headers };
        }

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            // 处理 401 错误
            if (response.status === 401) {
                localStorage.removeItem('token');
                if (!url.includes('/login') && !url.includes('/register')) {
                    window.location.href = '/login';
                }
            }

            return data;
        } catch (error) {
            console.error('API请求失败:', error);
            throw error;
        }
    },

    /**
     * GET 请求
     */
    async get(url) {
        return this.request(url, { method: 'GET' });
    },

    /**
     * POST 请求
     */
    async post(url, data) {
        return this.request(url, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    /**
     * PUT 请求
     */
    async put(url, data) {
        return this.request(url, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    /**
     * DELETE 请求
     */
    async delete(url) {
        return this.request(url, { method: 'DELETE' });
    }
};


// 通知提示工具
const Toast = {
    container: null,

    /**
     * 初始化容器
     */
    init() {
        if (this.container) return;
        this.container = document.createElement('div');
        this.container.id = 'toast-container';
        this.container.className = 'fixed top-4 right-4 z-50 space-y-2';
        document.body.appendChild(this.container);
    },

    /**
     * 显示提示
     * @param {string} message - 消息内容
     * @param {string} type - 类型: success, error, warning, info
     * @param {number} duration - 显示时长(毫秒)
     */
    show(message, type = 'info', duration = 3000) {
        this.init();

        const colors = {
            success: 'bg-green-500',
            error: 'bg-red-500',
            warning: 'bg-yellow-500',
            info: 'bg-blue-500'
        };

        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };

        const toast = document.createElement('div');
        toast.className = `${colors[type]} text-white px-4 py-3 rounded-lg shadow-lg flex items-center space-x-2 transform translate-x-full transition-transform duration-300`;
        toast.innerHTML = `
            <span class="text-lg">${icons[type]}</span>
            <span>${message}</span>
        `;

        this.container.appendChild(toast);

        // 动画显示
        requestAnimationFrame(() => {
            toast.classList.remove('translate-x-full');
        });

        // 自动关闭
        setTimeout(() => {
            toast.classList.add('translate-x-full');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    },

    success(message, duration) {
        this.show(message, 'success', duration);
    },

    error(message, duration) {
        this.show(message, 'error', duration);
    },

    warning(message, duration) {
        this.show(message, 'warning', duration);
    },

    info(message, duration) {
        this.show(message, 'info', duration);
    }
};


// 按钮加载状态工具
const Button = {
    /**
     * 设置按钮加载状态
     * @param {HTMLElement} button - 按钮元素
     * @param {boolean} loading - 是否加载中
     */
    setLoading(button, loading) {
        if (loading) {
            button.disabled = true;
            button.dataset.originalText = button.innerHTML;
            button.innerHTML = `
                <svg class="animate-spin h-4 w-4 inline-block mr-1" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                处理中...
            `;
        } else {
            button.disabled = false;
            if (button.dataset.originalText) {
                button.innerHTML = button.dataset.originalText;
            }
        }
    }
};


// 表单工具
const Form = {
    /**
     * 序列化表单数据为对象
     * @param {HTMLFormElement} form - 表单元素
     * @returns {object}
     */
    serialize(form) {
        const formData = new FormData(form);
        const data = {};
        for (const [key, value] of formData.entries()) {
            data[key] = value;
        }
        return data;
    },

    /**
     * 重置表单
     * @param {HTMLFormElement} form - 表单元素
     */
    reset(form) {
        form.reset();
        // 清除验证状态
        form.querySelectorAll('.error').forEach(el => el.classList.remove('error'));
        form.querySelectorAll('.error-message').forEach(el => el.remove());
    },

    /**
     * 显示字段错误
     * @param {HTMLElement} field - 字段元素
     * @param {string} message - 错误消息
     */
    showError(field, message) {
        field.classList.add('border-red-500');
        const errorEl = document.createElement('p');
        errorEl.className = 'error-message text-red-500 text-xs mt-1';
        errorEl.textContent = message;
        field.parentNode.appendChild(errorEl);
    },

    /**
     * 清除字段错误
     * @param {HTMLElement} field - 字段元素
     */
    clearError(field) {
        field.classList.remove('border-red-500');
        const errorEl = field.parentNode.querySelector('.error-message');
        if (errorEl) errorEl.remove();
    }
};


// 确认对话框
const Confirm = {
    /**
     * 显示确认对话框
     * @param {string} message - 确认消息
     * @param {object} options - 选项
     * @returns {Promise<boolean>}
     */
    show(message, options = {}) {
        const {
            title = '确认操作',
            confirmText = '确定',
            cancelText = '取消',
            type = 'warning'
        } = options;

        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'fixed inset-0 bg-black/50 z-50 flex items-center justify-center';
            overlay.innerHTML = `
                <div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
                    <h3 class="text-lg font-semibold text-gray-900 mb-2">${title}</h3>
                    <p class="text-gray-600 mb-6">${message}</p>
                    <div class="flex justify-end space-x-3">
                        <button class="cancel-btn px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition">
                            ${cancelText}
                        </button>
                        <button class="confirm-btn px-4 py-2 bg-red-500 text-white hover:bg-red-600 rounded-lg transition">
                            ${confirmText}
                        </button>
                    </div>
                </div>
            `;

            document.body.appendChild(overlay);

            overlay.querySelector('.cancel-btn').onclick = () => {
                overlay.remove();
                resolve(false);
            };

            overlay.querySelector('.confirm-btn').onclick = () => {
                overlay.remove();
                resolve(true);
            };

            overlay.onclick = (e) => {
                if (e.target === overlay) {
                    overlay.remove();
                    resolve(false);
                }
            };
        });
    }
};


// 日期格式化工具
const DateUtil = {
    /**
     * 格式化日期
     * @param {string|Date} date - 日期
     * @param {string} format - 格式
     * @returns {string}
     */
    format(date, format = 'YYYY-MM-DD HH:mm') {
        const d = new Date(date);
        if (isNaN(d.getTime())) return '-';

        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const hours = String(d.getHours()).padStart(2, '0');
        const minutes = String(d.getMinutes()).padStart(2, '0');
        const seconds = String(d.getSeconds()).padStart(2, '0');

        return format
            .replace('YYYY', year)
            .replace('MM', month)
            .replace('DD', day)
            .replace('HH', hours)
            .replace('mm', minutes)
            .replace('ss', seconds);
    },

    /**
     * 相对时间
     * @param {string|Date} date - 日期
     * @returns {string}
     */
    relative(date) {
        const d = new Date(date);
        const now = new Date();
        const diff = now - d;

        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (days > 30) return this.format(date, 'YYYY-MM-DD');
        if (days > 0) return `${days}天前`;
        if (hours > 0) return `${hours}小时前`;
        if (minutes > 0) return `${minutes}分钟前`;
        return '刚刚';
    }
};


// 复制到剪贴板
const Clipboard = {
    /**
     * 复制文本到剪贴板
     * @param {string} text - 文本
     * @returns {Promise<boolean>}
     */
    async copy(text) {
        try {
            await navigator.clipboard.writeText(text);
            Toast.success('已复制到剪贴板');
            return true;
        } catch (error) {
            // 回退方案
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            try {
                document.execCommand('copy');
                Toast.success('已复制到剪贴板');
                return true;
            } catch (e) {
                Toast.error('复制失败');
                return false;
            } finally {
                document.body.removeChild(textarea);
            }
        }
    }
};


// 导出到全局
window.API = API;
window.Toast = Toast;
window.Button = Button;
window.Form = Form;
window.Confirm = Confirm;
window.DateUtil = DateUtil;
window.Clipboard = Clipboard;
