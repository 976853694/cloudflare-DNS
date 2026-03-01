/**
 * 滑块验证码组件
 * 基于 Alpine.js 实现
 * 
 * 使用方式：
 * <div x-data="sliderCaptcha()" x-init="init()">
 *     <!-- 组件内容由模板渲染 -->
 * </div>
 * 
 * 事件：
 * - slider-captcha:success  验证成功时触发，detail 包含 token
 * - slider-captcha:fail     验证失败时触发
 */

function sliderCaptcha(options = {}) {
    return {
        // 配置
        onSuccess: options.onSuccess || null,
        onFail: options.onFail || null,
        
        // 状态
        token: '',
        styleType: '',
        styleParams: {},
        puzzleX: 0,
        puzzleY: 0,
        currentX: 0,
        isDragging: false,
        trajectory: [],
        verified: false,
        loading: false,
        status: 'idle', // idle, dragging, verifying, success, fail
        startX: 0,
        startTime: 0,
        
        // 尺寸配置
        bgWidth: 300,
        bgHeight: 150,
        puzzleSize: 50,
        trackWidth: 0,
        maxSlide: 0,
        
        async init() {
            // 等待 DOM 更新后计算尺寸
            await this.$nextTick();
            
            // 延迟一帧确保元素可见后再计算尺寸
            requestAnimationFrame(() => {
                this.calculateSizes();
            });
            
            await this.refresh();
            
            // 绑定全局事件（使用箭头函数保持 this 上下文）
            this._onDrag = (e) => this.onDrag(e);
            this._endDrag = (e) => this.endDrag(e);
            
            document.addEventListener('mousemove', this._onDrag);
            document.addEventListener('mouseup', this._endDrag);
            document.addEventListener('touchmove', this._onDrag, { passive: false });
            document.addEventListener('touchend', this._endDrag);
        },
        
        calculateSizes() {
            const container = this.$el?.querySelector('.slider-captcha-bg');
            if (container && container.offsetWidth > 0) {
                this.bgWidth = container.offsetWidth;
                this.bgHeight = container.offsetHeight;
            }
            const track = this.$el?.querySelector('.slider-captcha-track');
            if (track && track.offsetWidth > 0) {
                this.trackWidth = track.offsetWidth;
                this.maxSlide = this.trackWidth - 60; // 减去按钮宽度和边距
            }
            
            // 如果尺寸仍然为 0，使用默认值
            if (this.maxSlide <= 0) {
                this.maxSlide = 240; // 默认值：300 - 60
            }
        },
        
        async refresh() {
            this.loading = true;
            this.status = 'idle';
            this.verified = false;
            this.currentX = 0;
            this.trajectory = [];
            
            // 重新计算尺寸（元素可能刚变为可见）
            this.calculateSizes();
            
            try {
                const response = await fetch('/api/auth/slider-captcha');
                const result = await response.json();
                
                if (result.code === 200) {
                    this.token = result.data.token;
                    this.styleType = result.data.style_type;
                    this.styleParams = result.data.style_params;
                    this.puzzleX = result.data.puzzle_x;
                    this.puzzleY = result.data.puzzle_y;
                }
            } catch (error) {
                console.error('Failed to load slider captcha:', error);
            } finally {
                this.loading = false;
            }
        },
        
        reset() {
            // 只重置状态，不重新加载验证码图片
            // 用于关闭弹窗时清除验证状态
            this.status = 'idle';
            this.verified = false;
            this.currentX = 0;
            this.trajectory = [];
            this.isDragging = false;
            
            // 注意：不清除 token，因为 refresh() 会重新获取
            // 如果清除 token，会导致验证码图片无法显示
            
            console.log('[SliderCaptcha] Reset: state cleared, verified=', this.verified);
        },
        
        startDrag(e) {
            if (this.loading || this.verified || this.status === 'verifying') return;
            
            e.preventDefault();
            this.isDragging = true;
            this.status = 'dragging';
            this.trajectory = [];
            this.startTime = Date.now();
            
            const clientX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX;
            this.startX = clientX - this.currentX;
            
            // 记录起始点
            this.recordTrajectory(e);
        },

        onDrag(e) {
            if (!this.isDragging) return;
            
            e.preventDefault();
            
            const clientX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX;
            let newX = clientX - this.startX;
            
            // 限制范围
            newX = Math.max(0, Math.min(newX, this.maxSlide));
            this.currentX = newX;
            
            // 记录轨迹
            this.recordTrajectory(e);
        },
        
        async endDrag(e) {
            if (!this.isDragging) return;
            
            this.isDragging = false;
            
            // 记录最后一个点
            this.recordTrajectory(e);
            
            // 如果滑动距离太短，不验证
            if (this.currentX < 50) {
                this.status = 'idle';
                this.currentX = 0;
                return;
            }
            
            // 发送验证请求
            await this.verify();
        },
        
        recordTrajectory(e) {
            const clientX = e.type.includes('touch') 
                ? (e.touches?.[0]?.clientX || e.changedTouches?.[0]?.clientX || 0)
                : e.clientX;
            const clientY = e.type.includes('touch')
                ? (e.touches?.[0]?.clientY || e.changedTouches?.[0]?.clientY || 0)
                : e.clientY;
            
            this.trajectory.push({
                x: Math.round(clientX - this.startX),
                y: Math.round(clientY),
                t: Date.now() - this.startTime
            });
        },
        
        async verify() {
            this.status = 'verifying';
            this.loading = true;
            
            // 计算实际位置（根据滑动比例映射到背景宽度）
            const position = Math.round((this.currentX / this.maxSlide) * (this.bgWidth - this.puzzleSize));
            
            try {
                const response = await fetch('/api/auth/slider-captcha/verify', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        token: this.token,
                        position: position,
                        trajectory: this.trajectory
                    })
                });
                
                const result = await response.json();
                
                if (result.code === 200 && result.data?.success) {
                    this.status = 'success';
                    this.verified = true;
                    
                    // 触发成功回调
                    if (this.onSuccess) {
                        this.onSuccess(this.token);
                    }
                    
                    // 触发自定义事件
                    this.$el.dispatchEvent(new CustomEvent('slider-captcha:success', {
                        detail: { token: this.token },
                        bubbles: true
                    }));
                } else {
                    this.status = 'fail';
                    
                    // 触发失败回调
                    if (this.onFail) {
                        this.onFail(result.message);
                    }
                    
                    // 触发自定义事件
                    this.$el.dispatchEvent(new CustomEvent('slider-captcha:fail', {
                        detail: { message: result.message },
                        bubbles: true
                    }));
                    
                    // 1.5秒后自动刷新
                    setTimeout(() => {
                        this.refresh();
                    }, 1500);
                }
            } catch (error) {
                console.error('Slider captcha verify failed:', error);
                this.status = 'fail';
                
                setTimeout(() => {
                    this.refresh();
                }, 1500);
            } finally {
                this.loading = false;
            }
        },

        // 计算属性：背景样式
        get bgStyle() {
            if (!this.styleType || !this.styleParams) return '';
            
            const colors = this.styleParams.colors || ['#667eea', '#764ba2', '#f093fb'];
            const angles = this.styleParams.angles || [135, 45, 180];
            
            switch (this.styleType) {
                case 'gradient_overlay':
                    return `background: 
                        linear-gradient(${angles[0]}deg, ${colors[0]} 0%, ${colors[1]} 100%),
                        linear-gradient(${angles[1]}deg, ${colors[1]} 0%, ${colors[2]} 100%),
                        linear-gradient(${angles[2]}deg, ${colors[2]} 0%, ${colors[0]} 100%);
                        background-blend-mode: overlay, multiply, normal;`;
                
                case 'stripe_gradient':
                    const stripeWidth = this.styleParams.stripe_width || 10;
                    return `background: 
                        repeating-linear-gradient(
                            45deg,
                            ${colors[0]},
                            ${colors[0]} ${stripeWidth}px,
                            ${colors[1]} ${stripeWidth}px,
                            ${colors[1]} ${stripeWidth * 2}px
                        ),
                        linear-gradient(to right, ${colors[1]}, ${colors[2]});
                        background-blend-mode: overlay;`;
                
                case 'radial_gradient':
                    const circles = this.styleParams.circles || [
                        {x: 20, y: 80}, {x: 80, y: 20}, {x: 40, y: 40}
                    ];
                    return `background: 
                        radial-gradient(circle at ${circles[0].x}% ${circles[0].y}%, ${colors[0]}cc 0%, transparent 50%),
                        radial-gradient(circle at ${circles[1].x}% ${circles[1].y}%, ${colors[1]}cc 0%, transparent 50%),
                        radial-gradient(circle at ${circles[2].x}% ${circles[2].y}%, ${colors[2]}cc 0%, transparent 50%),
                        linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);`;
                
                case 'grid_pattern':
                    const gridSize = this.styleParams.grid_size || 20;
                    return `background: 
                        linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px),
                        linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px),
                        linear-gradient(${angles[0]}deg, ${colors[0]} 0%, ${colors[1]} 100%);
                        background-size: ${gridSize}px ${gridSize}px, ${gridSize}px ${gridSize}px, 100% 100%;`;
                
                case 'wave_gradient':
                    return `background: linear-gradient(${angles[0]}deg, ${colors[0]} 0%, ${colors[1]} 37%, ${colors[2]} 65%, ${colors[0]} 100%);`;
                
                case 'mosaic_effect':
                    const c4 = this.styleParams.colors[3] || colors[0];
                    return `background: 
                        conic-gradient(from 45deg at 25% 25%, ${colors[0]}, ${colors[1]}, ${colors[2]}, ${colors[0]}),
                        conic-gradient(from 225deg at 75% 75%, ${c4}, ${colors[1]}, ${colors[2]}, ${c4});
                        background-size: 50% 50%;
                        background-blend-mode: multiply;`;
                
                default:
                    return `background: linear-gradient(135deg, ${colors[0]} 0%, ${colors[1]} 100%);`;
            }
        },
        
        // 计算属性：缺口位置样式（固定在服务器返回的位置）
        get puzzleStyle() {
            return `top: ${this.puzzleY}px; left: ${this.puzzleX}px;`;
        },
        
        // 计算属性：滑块按钮位置
        get btnStyle() {
            return `left: ${this.currentX + 5}px;`;
        },
        
        // 计算属性：拼图块样式（跟随滑块移动）
        get pieceStyle() {
            // 拼图块从左边开始，跟随滑块移动
            // 映射滑块位置到背景宽度范围
            const pieceX = (this.currentX / this.maxSlide) * (this.bgWidth - this.puzzleSize);
            return `top: ${this.puzzleY}px; left: ${pieceX}px; ${this.bgStyle}`;
        },
        
        // 计算属性：状态文本
        get statusText() {
            const i18n = window.Alpine?.store?.('i18n');
            const t = (key) => i18n?.t?.(key) || this.defaultTexts[key] || key;
            
            switch (this.status) {
                case 'idle':
                    return t('sliderCaptcha.dragToVerify');
                case 'dragging':
                    return t('sliderCaptcha.dragging');
                case 'verifying':
                    return t('sliderCaptcha.verifying');
                case 'success':
                    return t('sliderCaptcha.success');
                case 'fail':
                    return t('sliderCaptcha.fail');
                default:
                    return t('sliderCaptcha.dragToVerify');
            }
        },
        
        // 默认文本（i18n 未加载时使用）
        defaultTexts: {
            'sliderCaptcha.dragToVerify': '向右拖动滑块完成验证',
            'sliderCaptcha.dragging': '继续拖动...',
            'sliderCaptcha.verifying': '验证中...',
            'sliderCaptcha.success': '验证成功',
            'sliderCaptcha.fail': '验证失败，请重试'
        },
        
        // 计算属性：容器类名
        get containerClass() {
            return {
                'slider-captcha-success': this.status === 'success',
                'slider-captcha-fail': this.status === 'fail',
                'slider-captcha-loading': this.loading && this.status !== 'verifying'
            };
        }
    };
}

// 导出到全局
window.sliderCaptcha = sliderCaptcha;
