<?php
/**
 * 邮件模板迁移脚本
 * 将邮件模板从代码文件迁移到数据库
 */

require_once __DIR__ . '/../includes/init.php';


$db_path = __DIR__ . '/../data/cloudflare_dns.db';
$db = new SQLite3($db_path);

echo "<h2>邮件模板数据库迁移</h2>";
echo "<pre>";

// 默认邮件模板
$default_templates = [
    'email_template_registration' => "
        <div style='max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif;'>
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;'>
                <h1 style='color: white; margin: 0; font-size: 28px;'>六趣DNS</h1>
                <p style='color: rgba(255,255,255,0.9); margin: 10px 0 0 0;'>欢迎注册我们的服务</p>
            </div>
            
            <div style='background: white; padding: 40px; border-left: 4px solid #667eea;'>
                <h2 style='color: #333; margin-top: 0;'>Hi {username},</h2>
                <p style='color: #666; line-height: 1.6; font-size: 16px;'>
                    感谢您注册六趣DNS！为了完成注册，请使用以下验证码：
                </p>
                
                <div style='background: #f8f9fa; border: 2px dashed #667eea; padding: 20px; text-align: center; margin: 30px 0;'>
                    <div style='font-size: 32px; font-weight: bold; color: #667eea; letter-spacing: 5px;'>{code}</div>
                    <p style='color: #999; margin: 10px 0 0 0; font-size: 14px;'>验证码5分钟内有效</p>
                </div>
                
                <p style='color: #666; line-height: 1.6;'>
                    如果您没有申请注册，请忽略此邮件。
                </p>
                
                <div style='margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #999; font-size: 14px;'>
                    <p>此邮件由系统自动发送，请勿回复。</p>
                    <p>© {year} 六趣DNS. All rights reserved.</p>
                </div>
            </div>
        </div>",
    
    'email_template_password_reset' => "
        <div style='max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif;'>
            <div style='background: linear-gradient(135deg, #ff6b6b 0%, #ee5a52 100%); padding: 30px; text-align: center;'>
                <h1 style='color: white; margin: 0; font-size: 28px;'>六趣DNS</h1>
                <p style='color: rgba(255,255,255,0.9); margin: 10px 0 0 0;'>密码重置请求</p>
            </div>
            
            <div style='background: white; padding: 40px; border-left: 4px solid #ff6b6b;'>
                <h2 style='color: #333; margin-top: 0;'>Hi {username},</h2>
                <p style='color: #666; line-height: 1.6; font-size: 16px;'>
                    我们收到了您的密码重置请求。请使用以下验证码来重置您的密码：
                </p>
                
                <div style='background: #fff5f5; border: 2px dashed #ff6b6b; padding: 20px; text-align: center; margin: 30px 0;'>
                    <div style='font-size: 32px; font-weight: bold; color: #ff6b6b; letter-spacing: 5px;'>{code}</div>
                    <p style='color: #999; margin: 10px 0 0 0; font-size: 14px;'>验证码5分钟内有效</p>
                </div>
                
                <div style='background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0;'>
                    <p style='color: #856404; margin: 0; font-size: 14px;'>
                        <strong>安全提示：</strong>如果您没有申请密码重置，请立即检查您的账户安全。
                    </p>
                </div>
                
                <div style='margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #999; font-size: 14px;'>
                    <p>此邮件由系统自动发送，请勿回复。</p>
                    <p>© {year} 六趣DNS. All rights reserved.</p>
                </div>
            </div>
        </div>",
    
    'email_template_password_change' => "
        <div style='max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif;'>
            <div style='background: linear-gradient(135deg, #4ecdc4 0%, #44a08d 100%); padding: 30px; text-align: center;'>
                <h1 style='color: white; margin: 0; font-size: 28px;'>六趣DNS</h1>
                <p style='color: rgba(255,255,255,0.9); margin: 10px 0 0 0;'>密码修改成功</p>
            </div>
            
            <div style='background: white; padding: 40px; border-left: 4px solid #4ecdc4;'>
                <h2 style='color: #333; margin-top: 0;'>Hi {username},</h2>
                <p style='color: #666; line-height: 1.6; font-size: 16px;'>
                    您的账户密码已于 <strong>{change_time}</strong> 成功修改。
                </p>
                
                <div style='background: #d4edda; border: 1px solid #c3e6cb; padding: 15px; border-radius: 5px; margin: 20px 0;'>
                    <p style='color: #155724; margin: 0; font-size: 14px;'>
                        ✅ 密码修改成功，您的账户安全性已得到提升。
                    </p>
                </div>
                
                <p style='color: #666; line-height: 1.6;'>
                    如果这不是您本人的操作，请立即：
                </p>
                <ul style='color: #666; line-height: 1.6;'>
                    <li>联系我们的客服支持</li>
                    <li>检查您的账户安全设置</li>
                    <li>考虑启用更强的安全措施</li>
                </ul>
                
                <div style='margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #999; font-size: 14px;'>
                    <p>此邮件由系统自动发送，请勿回复。</p>
                    <p>© {year} 六趣DNS. All rights reserved.</p>
                </div>
            </div>
        </div>",
    
    'email_template_email_change' => "
        <div style='max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif;'>
            <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 30px; text-align: center;'>
                <h1 style='color: white; margin: 0; font-size: 28px;'>六趣DNS</h1>
                <p style='color: rgba(255,255,255,0.9); margin: 10px 0 0 0;'>邮箱更换验证</p>
            </div>
            
            <div style='background: white; padding: 40px; border-left: 4px solid #f093fb;'>
                <h2 style='color: #333; margin-top: 0;'>Hi {username},</h2>
                <p style='color: #666; line-height: 1.6; font-size: 16px;'>
                    您正在更换账户绑定的邮箱地址。请使用以下验证码来确认此操作：
                </p>
                
                <div style='background: #fdf2f8; border: 2px dashed #f093fb; padding: 20px; text-align: center; margin: 30px 0;'>
                    <div style='font-size: 32px; font-weight: bold; color: #f093fb; letter-spacing: 5px;'>{code}</div>
                    <p style='color: #999; margin: 10px 0 0 0; font-size: 14px;'>验证码5分钟内有效</p>
                </div>
                
                <div style='background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0;'>
                    <p style='color: #856404; margin: 0; font-size: 14px;'>
                        <strong>重要提示：</strong>确认后，您将无法再使用旧邮箱接收系统通知。
                    </p>
                </div>
                
                <p style='color: #666; line-height: 1.6;'>
                    如果您没有申请更换邮箱，请忽略此邮件并检查您的账户安全。
                </p>
                
                <div style='margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #999; font-size: 14px;'>
                    <p>此邮件由系统自动发送，请勿回复。</p>
                    <p>© {year} 六趣DNS. All rights reserved.</p>
                </div>
            </div>
        </div>",
    
    'email_template_test' => "
        <div style='max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif;'>
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;'>
                <h1 style='color: white; margin: 0; font-size: 28px;'>六趣DNS</h1>
                <p style='color: rgba(255,255,255,0.9); margin: 10px 0 0 0;'>SMTP配置测试</p>
            </div>
            
            <div style='background: white; padding: 40px; border-left: 4px solid #667eea;'>
                <h2 style='color: #333; margin-top: 0;'>SMTP测试邮件</h2>
                <p style='color: #666; line-height: 1.6; font-size: 16px;'>
                    恭喜！您的SMTP邮件服务配置成功！
                </p>
                
                <div style='background: #d4edda; border: 1px solid #c3e6cb; padding: 20px; border-radius: 5px; margin: 30px 0;'>
                    <p style='color: #155724; margin: 0; font-size: 14px;'>
                        ✅ <strong>测试成功</strong><br>
                        您的邮件服务器已正确配置，可以正常发送邮件。
                    </p>
                </div>
                
                <p style='color: #666; line-height: 1.6;'>
                    <strong>测试信息：</strong>
                </p>
                <ul style='color: #666; line-height: 1.6;'>
                    <li>发送时间：{test_time}</li>
                    <li>邮件服务：六趣DNS系统</li>
                    <li>状态：正常运行</li>
                </ul>
                
                <div style='margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #999; font-size: 14px;'>
                    <p>此邮件由系统自动发送，请勿回复。</p>
                    <p>© {year} 六趣DNS. All rights reserved.</p>
                </div>
            </div>
        </div>"
];

try {
    echo "开始迁移邮件模板到数据库...\n\n";
    
    // 插入或更新模板
    foreach ($default_templates as $key => $template) {
        // 检查是否已存在
        $stmt = $db->prepare("SELECT setting_value FROM settings WHERE setting_key = ?");
        $stmt->bindValue(1, $key, SQLITE3_TEXT);
        $result = $stmt->execute();
        $existing = $result->fetchArray(SQLITE3_ASSOC);
        
        if ($existing) {
            echo "✓ 模板已存在：{$key}，跳过\n";
        } else {
            // 插入新模板
            $stmt = $db->prepare("INSERT INTO settings (setting_key, setting_value) VALUES (?, ?)");
            $stmt->bindValue(1, $key, SQLITE3_TEXT);
            $stmt->bindValue(2, $template, SQLITE3_TEXT);
            $stmt->execute();
            echo "✓ 已添加模板：{$key}\n";
        }
    }
    
    echo "\n迁移完成！\n";
    echo "\n所有邮件模板已成功添加到数据库。\n";
    echo "现在可以通过后台 SMTP 设置页面管理邮件模板。\n";
    
} catch (Exception $e) {
    echo "❌ 错误：" . $e->getMessage() . "\n";
    echo $e->getTraceAsString();
}

echo "</pre>";

// 显示返回链接
echo '<p><a href="../admin/smtp_settings.php">返回 SMTP 设置</a></p>';
?>
