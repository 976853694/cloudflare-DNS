    <!-- Bootstrap JS -->
    <script src="../assets/js/bootstrap.bundle.min.js"></script>
    
    <!-- 自定义JS -->
    <script>
        // 自动隐藏提示消息（仅关闭带有 alert-dismissible 类的提示）
        setTimeout(function() {
            var alerts = document.querySelectorAll('.alert.alert-dismissible');
            alerts.forEach(function(alert) {
                var bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            });
        }, 5000);
        
        // 确认删除
        function confirmDelete(message) {
            return confirm(message || '确定要删除吗？此操作不可恢复！');
        }
        
        // 复制到剪贴板
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(function() {
                // 显示复制成功提示
                var toast = document.createElement('div');
                toast.className = 'toast align-items-center text-white bg-success border-0 position-fixed top-0 end-0 m-3';
                toast.style.zIndex = '9999';
                toast.innerHTML = `
                    <div class="d-flex">
                        <div class="toast-body">
                            <i class="fas fa-check me-2"></i>已复制到剪贴板
                        </div>
                        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                    </div>
                `;
                document.body.appendChild(toast);
                var bsToast = new bootstrap.Toast(toast);
                bsToast.show();
                
                // 3秒后自动移除
                setTimeout(function() {
                    document.body.removeChild(toast);
                }, 3000);
            });
        }
        
        // 表单验证
        (function() {
            'use strict';
            window.addEventListener('load', function() {
                var forms = document.getElementsByClassName('needs-validation');
                var validation = Array.prototype.filter.call(forms, function(form) {
                    form.addEventListener('submit', function(event) {
                        if (form.checkValidity() === false) {
                            event.preventDefault();
                            event.stopPropagation();
                        }
                        form.classList.add('was-validated');
                    }, false);
                });
            }, false);
        })();
    </script>
</body>
</html>