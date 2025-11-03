<?php
/**
 * 邮件服务类 - 支持用户注册、找回密码、修改密码、更换邮箱验证
 */

use PHPMailer\PHPMailer\PHPMailer;
use PHPMailer\PHPMailer\Exception;

require_once __DIR__ . '/smtp/Exception.php';
require_once __DIR__ . '/smtp/PHPMailer.php';
require_once __DIR__ . '/smtp/SMTP.php';
require_once __DIR__ . '/database.php';

class EmailService {
    private $mail;
    private $db;
    
    // 邮件配置（从数据库加载）
    private $smtp_host;
    private $smtp_username;
    private $smtp_password;
    private $smtp_port;
    private $smtp_secure;
    private $from_name;
    private $smtp_enabled;
    private $smtp_debug;
    
    public function __construct() {
        $this->db = Database::getInstance()->getConnection();
        $this->loadSMTPConfig();
        $this->initMailer();
    }
    
    /**
     * 从数据库加载SMTP配置
     */
    private function loadSMTPConfig() {
        // 完全从数据库读取SMTP配置，不使用任何硬编码值
        $this->smtp_enabled = $this->getSetting('smtp_enabled', '0');
        $this->smtp_host = $this->getSetting('smtp_host', '');
        $this->smtp_port = (int)$this->getSetting('smtp_port', '587');
        $this->smtp_username = $this->getSetting('smtp_username', '');
        $this->smtp_password = $this->getSetting('smtp_password', '');
        $this->smtp_secure = $this->getSetting('smtp_secure', 'tls');
        $this->from_name = $this->getSetting('smtp_from_name', 'System');
        $this->smtp_debug = (int)$this->getSetting('smtp_debug', '0');
        
        // 调试模式下记录配置加载信息
        if ($this->smtp_debug > 0) {
            error_log("SMTP Config Loaded - Host: {$this->smtp_host}, Port: {$this->smtp_port}, User: {$this->smtp_username}, Enabled: {$this->smtp_enabled}");
        }
    }
    
    /**
     * 重新加载SMTP配置（用于配置更新后刷新）
     */
    public function reloadConfig() {
        $this->loadSMTPConfig();
        // 重新初始化邮件发送器
        if ($this->smtp_enabled && $this->smtp_enabled !== '0') {
            $this->initMailer();
        }
    }
    
    /**
     * 获取设置值
     */
    private function getSetting($key, $default = '') {
        try {
            $stmt = $this->db->prepare("SELECT setting_value FROM settings WHERE setting_key = ?");
            $stmt->bindValue(1, $key, SQLITE3_TEXT);
            $result = $stmt->execute();
            $row = $result->fetchArray(SQLITE3_ASSOC);
            
            if ($row && isset($row['setting_value'])) {
                return $row['setting_value'];
            }
            
            return $default;
        } catch (Exception $e) {
            error_log("SMTP Setting read error for $key: " . $e->getMessage());
            return $default;
        }
    }
    
    /**
     * 初始化邮件发送器
     */
    private function initMailer() {
        // 检查SMTP是否启用
        if (!$this->smtp_enabled || $this->smtp_enabled === '0') {
            throw new Exception('SMTP邮件发送功能已禁用，请在后台SMTP设置中启用');
        }
        
        // 验证必要的SMTP配置
        if (empty($this->smtp_host)) {
            throw new Exception('SMTP服务器地址未配置，请在后台SMTP设置中配置');
        }
        
        if (empty($this->smtp_username)) {
            throw new Exception('SMTP用户名未配置，请在后台SMTP设置中配置');
        }
        
        if (empty($this->smtp_password)) {
            throw new Exception('SMTP密码未配置，请在后台SMTP设置中配置');
        }
        
        // 验证SMTP用户名是否为有效邮箱格式
        if (!filter_var($this->smtp_username, FILTER_VALIDATE_EMAIL)) {
            throw new Exception('SMTP用户名必须是有效的邮箱地址格式，请在后台SMTP设置中修正');
        }
        
        $this->mail = new PHPMailer(true);
        
        // 服务器配置
        $this->mail->CharSet = "UTF-8";
        $this->mail->SMTPDebug = $this->smtp_debug;
        $this->mail->isSMTP();
        $this->mail->Host = $this->smtp_host;
        $this->mail->SMTPAuth = true;
        $this->mail->Username = $this->smtp_username;
        $this->mail->Password = $this->smtp_password;
        $this->mail->SMTPSecure = $this->smtp_secure;
        $this->mail->Port = $this->smtp_port;
        $this->mail->setFrom($this->smtp_username, $this->from_name);
        $this->mail->addReplyTo($this->smtp_username, $this->from_name);
        $this->mail->isHTML(true);
    }
    
    /**
     * 生成6位数字验证码
     */
    private function generateVerificationCode() {
        return sprintf('%06d', mt_rand(0, 999999));
    }
    
    /**
     * 保存验证码到数据库
     */
    private function saveVerificationCode($email, $code, $type, $user_id = null) {
        // 创建验证码表（如果不存在）
        $this->db->exec("CREATE TABLE IF NOT EXISTS email_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            type TEXT NOT NULL,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            used INTEGER DEFAULT 0
        )");
        
        // 使验证码5分钟后过期
        $expires_at = date('Y-m-d H:i:s', time() + 300);
        
        // 删除该邮箱的旧验证码
        $stmt = $this->db->prepare("DELETE FROM email_verifications WHERE email = ? AND type = ?");
        $stmt->bindValue(1, $email, SQLITE3_TEXT);
        $stmt->bindValue(2, $type, SQLITE3_TEXT);
        $stmt->execute();
        
        // 插入新验证码
        $stmt = $this->db->prepare("INSERT INTO email_verifications (email, code, type, user_id, expires_at) VALUES (?, ?, ?, ?, ?)");
        $stmt->bindValue(1, $email, SQLITE3_TEXT);
        $stmt->bindValue(2, $code, SQLITE3_TEXT);
        $stmt->bindValue(3, $type, SQLITE3_TEXT);
        $stmt->bindValue(4, $user_id, SQLITE3_INTEGER);
        $stmt->bindValue(5, $expires_at, SQLITE3_TEXT);
        
        return $stmt->execute();
    }
    
    /**
     * 验证验证码
     */
    public function verifyCode($email, $code, $type) {
        $stmt = $this->db->prepare("
            SELECT id, user_id FROM email_verifications 
            WHERE email = ? AND code = ? AND type = ? AND used = 0 AND expires_at > datetime('now')
        ");
        $stmt->bindValue(1, $email, SQLITE3_TEXT);
        $stmt->bindValue(2, $code, SQLITE3_TEXT);
        $stmt->bindValue(3, $type, SQLITE3_TEXT);
        
        $result = $stmt->execute();
        $row = $result->fetchArray(SQLITE3_ASSOC);
        
        if ($row) {
            // 标记验证码为已使用
            $update_stmt = $this->db->prepare("UPDATE email_verifications SET used = 1 WHERE id = ?");
            $update_stmt->bindValue(1, $row['id'], SQLITE3_INTEGER);
            $update_stmt->execute();
            
            return [
                'valid' => true,
                'user_id' => $row['user_id']
            ];
        }
        
        return ['valid' => false];
    }
    
    /**
     * 发送注册验证邮件
     */
    public function sendRegistrationVerification($email, $username) {
        $code = $this->generateVerificationCode();
        
        if (!$this->saveVerificationCode($email, $code, 'registration')) {
            return false;
        }
        
        try {
            $this->mail->clearAddresses();
            $this->mail->addAddress($email, $username);
            $this->mail->Subject = $this->getSetting('email_subject_registration', '六趣DNS - 注册验证码');
            
            $this->mail->Body = $this->getRegistrationEmailTemplate($username, $code);
            $this->mail->AltBody = "您的注册验证码是: {$code}，5分钟内有效。";
            
            $this->mail->send();
            return true;
            
        } catch (Exception $e) {
            error_log("Registration email failed: " . $e->getMessage());
            error_log("SMTP Error Details: " . $this->mail->ErrorInfo);
            throw new Exception("注册验证邮件发送失败: " . $e->getMessage());
        }
    }
    
    /**
     * 发送密码重置邮件
     */
    public function sendPasswordReset($email, $username, $user_id) {
        $code = $this->generateVerificationCode();
        
        if (!$this->saveVerificationCode($email, $code, 'password_reset', $user_id)) {
            return false;
        }
        
        try {
            $this->mail->clearAddresses();
            $this->mail->addAddress($email, $username);
            $this->mail->Subject = $this->getSetting('email_subject_password_reset', '六趣DNS - 密码重置验证码');
            
            $this->mail->Body = $this->getPasswordResetEmailTemplate($username, $code);
            $this->mail->AltBody = "您的密码重置验证码是: {$code}，5分钟内有效。";
            
            $this->mail->send();
            return true;
            
        } catch (Exception $e) {
            error_log("Password reset email failed: " . $e->getMessage());
            error_log("SMTP Error Details: " . $this->mail->ErrorInfo);
            throw new Exception("密码重置邮件发送失败: " . $e->getMessage());
        }
    }
    
    /**
     * 发送密码修改通知邮件
     */
    public function sendPasswordChangeNotification($email, $username) {
        try {
            $this->mail->clearAddresses();
            $this->mail->addAddress($email, $username);
            $this->mail->Subject = $this->getSetting('email_subject_password_change', '六趣DNS - 密码修改通知');
            
            $this->mail->Body = $this->getPasswordChangeNotificationTemplate($username);
            $this->mail->AltBody = "您的账户密码已成功修改。如非本人操作，请立即联系客服。";
            
            $this->mail->send();
            return true;
            
        } catch (Exception $e) {
            error_log("Password change notification failed: " . $e->getMessage());
            return false;
        }
    }
    
    /**
     * 发送邮箱更换验证码
     */
    public function sendEmailChangeVerification($new_email, $username, $user_id) {
        $code = $this->generateVerificationCode();
        
        if (!$this->saveVerificationCode($new_email, $code, 'email_change', $user_id)) {
            return false;
        }
        
        try {
            $this->mail->clearAddresses();
            $this->mail->addAddress($new_email, $username);
            $this->mail->Subject = $this->getSetting('email_subject_email_change', '六趣DNS - 邮箱更换验证码');
            
            $this->mail->Body = $this->getEmailChangeVerificationTemplate($username, $code);
            $this->mail->AltBody = "您的邮箱更换验证码是: {$code}，5分钟内有效。";
            
            $this->mail->send();
            return true;
            
        } catch (Exception $e) {
            error_log("Email change verification failed: " . $e->getMessage());
            error_log("SMTP Error Details: " . $this->mail->ErrorInfo);
            throw new Exception("邮箱更换验证邮件发送失败: " . $e->getMessage());
        }
    }
    
    /**
     * 注册验证邮件模板
     */
    private function getRegistrationEmailTemplate($username, $code) {
        $template = $this->getSetting('email_template_registration', '');
        
        // 如果数据库中没有模板，使用默认模板
        if (empty($template)) {
            $template = "
        ";
        }
        
        // 替换变量
        $template = str_replace('{username}', $username, $template);
        $template = str_replace('{code}', $code, $template);
        $template = str_replace('{year}', date('Y'), $template);
        
        return $template;
    }
    
    /**
     * 密码重置邮件模板
     */
    private function getPasswordResetEmailTemplate($username, $code) {
        $template = $this->getSetting('email_template_password_reset', '');
        
        if (empty($template)) {
            $template = "
        ";
        }
        
        $template = str_replace('{username}', $username, $template);
        $template = str_replace('{code}', $code, $template);
        $template = str_replace('{year}', date('Y'), $template);
        
        return $template;
    }
    
    /**
     * 密码修改通知邮件模板
     */
    private function getPasswordChangeNotificationTemplate($username) {
        $change_time = date('Y-m-d H:i:s');
        $template = $this->getSetting('email_template_password_change', '');
        
        if (empty($template)) {
            $template = "
        ";
        }
        
        $template = str_replace('{username}', $username, $template);
        $template = str_replace('{change_time}', $change_time, $template);
        $template = str_replace('{year}', date('Y'), $template);
        
        return $template;
    }
    
    /**
     * 邮箱更换验证邮件模板
     */
    private function getEmailChangeVerificationTemplate($username, $code) {
        $template = $this->getSetting('email_template_email_change', '');
        
        if (empty($template)) {
            $template = "
   ";
        }
        
        $template = str_replace('{username}', $username, $template);
        $template = str_replace('{code}', $code, $template);
        $template = str_replace('{year}', date('Y'), $template);
        
        return $template;
    }
    
    /**
     * 发送测试邮件
     */
    public function sendTestEmail($email) {
        try {
            // 检查SMTP是否启用
            if ($this->smtp_enabled !== '1') {
                throw new Exception('SMTP邮件发送功能未启用');
            }
            
            // 检查必要的配置
            if (empty($this->smtp_host)) {
                throw new Exception('SMTP服务器地址未配置');
            }
            if (empty($this->smtp_username)) {
                throw new Exception('SMTP用户名未配置');
            }
            if (empty($this->smtp_password)) {
                throw new Exception('SMTP密码未配置');
            }
            
            $this->mail->clearAddresses();
            $this->mail->addAddress($email);
            $this->mail->Subject = $this->getSetting('email_subject_test', '六趣DNS - SMTP测试邮件');
            
            $this->mail->Body = $this->getTestEmailTemplate();
            $this->mail->AltBody = "这是一封SMTP配置测试邮件，发送时间：" . date('Y-m-d H:i:s');
            
            // 发送邮件
            $result = $this->mail->send();
            
            if (!$result) {
                throw new Exception('PHPMailer发送失败，但未抛出异常');
            }
            
            return true;
            
        } catch (Exception $e) {
            // 记录详细的错误信息
            $error_details = [
                'message' => $e->getMessage(),
                'smtp_host' => $this->smtp_host,
                'smtp_port' => $this->smtp_port,
                'smtp_username' => $this->smtp_username,
                'smtp_secure' => $this->smtp_secure,
                'smtp_enabled' => $this->smtp_enabled,
                'debug_level' => $this->smtp_debug
            ];
            
            error_log("SMTP Test Email Error Details: " . json_encode($error_details));
            
            throw new Exception("测试邮件发送失败: " . $e->getMessage());
        }
    }
    
    /**
     * 测试邮件模板
     */
    private function getTestEmailTemplate() {
        $test_time = date('Y-m-d H:i:s');
        $template = $this->getSetting('email_template_test', '');
        
        if (empty($template)) {
            $template = "
       ";
        }
        
        $template = str_replace('{test_time}', $test_time, $template);
        $template = str_replace('{year}', date('Y'), $template);
        
        return $template;
    }
}