<?php

require_once '../config/database.php';
require_once 'functions.php';
require_once 'PHPMailer/PHPMailer.php';
require_once 'PHPMailer/Exception.php';
require_once 'PHPMailer/SMTP.php';

use PHPMailer\PHPMailer\PHPMailer;
use PHPMailer\PHPMailer\Exception;
use PHPMailer\PHPMailer\SMTP;

/**
 * 邮箱验证 BY Senvinn
 */

// 发送验证码请求处理
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['send_email_verifycode'])) {
    $email = getPost('email');
    $mail_verify = new captcha_mail();
    $db = Database::getInstance()->getConnection();
    $timezone = new DateTimeZone('UTC'); // 数据库时间是UTC+0时区

    $email_exists = $db->querySingle("SELECT COUNT(*) FROM users WHERE email = '$email'");
    if ($email_exists) {
        echo '{"code": "-1","msg":"邮箱已被注册！"}';
        return;
    } else {
        if (!$email || !isValidEmail($email)) {
            echo '{"code": "-1","msg":"请正确填写邮箱！"}';
            return;
        } else {
            // 禁止一分钟内多次发送验证码
            $is_exist = $db->querySingle("SELECT COUNT(*) FROM email_verify WHERE email_address = '$email'");
            if ($is_exist) {
                $create_time = $mail_verify->getCodeCreatedTime($email);
                $now_time = new DateTime('now', $timezone);
                $had_created_time = abs($now_time->getTimestamp() - $create_time->getTimestamp());
                if ($had_created_time < 60 + 2) {
                    echo '{"code": "-1","msg":"请勿在1分钟内重复发送验证码！"}';
                    return;
                } else {
                    // 发送验证码
                    $email_verify = new captcha_mail();
                    $flag = $email_verify->sendCodeAndSave($email);
                    if (!$flag) {
                        echo '{"code": "-1","msg":"验证码发送失败，请联系管理员"}';
                        return;
                    }
                    echo '{"code": "0","msg":"验证码已发送，若未收到请检查垃圾箱。"}';
                    return;
                }
            }

            // 发送验证码
            $email_verify = new captcha_mail();
            $flag = $email_verify->sendCodeAndSave($email);
            if (!$flag) {
                echo '{"code": "-1","msg":"验证码发送失败，请联系管理员"}';
                return;
            }
            echo '{"code": "0","msg":"验证码已发送，若未收到请检查垃圾箱。"}';
            return;
        }
    }

    return;
}

class captcha_mail
{

    private $length_mail = 6;
    private $mail = null;

    private $smtp_host = null;
    private $smtp_username = null;
    private $smtp_password = null;
    private $mail_username = null;
    private $mail_subject = null;
    private $mail_body = null;

    private $timezone = null;

    /**
     * 初始化PHPMailer
     */
    public function __construct()
    {
        $this->timezone = new DateTimeZone('UTC'); // 数据库时间是UTC+0时区

        $this->mail = new PHPMailer(true);

        $this->smtp_host = getSetting('smtp_host');
        $this->smtp_username = getSetting('smtp_username');
        $this->smtp_password = getSetting('smtp_password');
        $this->mail_username = getSetting('mail_username');
        $this->mail_subject = getSetting('mail_subject');
        $this->mail_body = getSetting('mail_body');

        try {
            // 配置SMTP服务器
            $this->mail->isSMTP();
            $this->mail->Host = $this->smtp_host;
            $this->mail->SMTPAuth = true;
            $this->mail->Username = $this->smtp_username; // 邮箱账号
            $this->mail->Password = $this->smtp_password; // 邮箱授权码
            $this->mail->SMTPSecure = 'ssl';
            $this->mail->CharSet = 'UTF-8';
            $this->mail->Port = 465;
            $this->mail->setFrom($this->smtp_username, $this->mail_username);
        } catch (Exception $e) {
            echo "邮件发送错误: {$e}";
        }
    }

    /**
     * 发送邮箱验证码函数
     */
    public function sendCodeAndSave($to_email_address)
    {
        $code = $this->generateCodeForEmail();

        $realbody = str_replace('{code}', $code, $this->mail_body);

        try {
            // 邮件内容设置
            $this->mail->isHTML(true);

            $this->mail->Subject = $this->mail_subject;
            $this->mail->Body = $realbody;

            // 添加收件人并发送
            $this->mail->addAddress($to_email_address);
            if (!$this->mail->send()) {
                // 邮件发送失败
                return false;
            } else {
                // 邮件发送成功 将需要验证的邮箱和对应验证码存入数据库
                $db = Database::getInstance()->getConnection();
                $verify_email_exists = $db->querySingle("SELECT COUNT(*) FROM email_verify WHERE email_address = '$to_email_address'");
                if ($verify_email_exists) {
                    $update_verify = $db->exec("UPDATE email_verify SET email_verify_code = '$code', verify_code_created_at = datetime() WHERE email_address = '$to_email_address'");
                    if (!$update_verify) {
                        return false;
                    }
                    return true;
                } else {
                    $temp = $db->prepare('insert into email_verify(email_address, email_verify_code,isVerified) values (? ,? ,?)');
                    $temp->bindValue(1, $to_email_address, SQLITE3_TEXT);
                    $temp->bindValue(2, $code, SQLITE3_TEXT);
                    $temp->bindValue(3, 0, SQLITE3_INTEGER);
                    $temp->execute();
                    if (!$temp) {
                        return false;
                    }
                    return true;
                }
            }

            $this->mail->clearAddresses(); // 清除地址 
        } catch (Exception $e) {
            // 邮件发送错误
            return false;
        }
    }


    /**
     * 验证邮箱验证码函数
     */
    public function checkCode($input_code, $email_address)
    {
        $code = $this->getVerifyCode($email_address);

        $db = Database::getInstance()->getConnection();
        $create_time = $this->getCodeCreatedTime($email_address);
        $now_time = new DateTime('now', $this->timezone);
        $had_created_time = abs($now_time->getTimestamp() - $create_time->getTimestamp());

        $code_exists = $db->querySingle("SELECT COUNT(*) FROM email_verify WHERE email_address = '$email_address'");

        if (!$code_exists) {
            return 1; // 验证码错误(不存在)
        }

        if (!($input_code == $code)) {
            return 1; // 验证码错误
        }

        // 验证码五分钟过期
        if ($had_created_time > 60 * 5) {
            return -1; // 验证码已过期
        }

        $update = $db->exec("UPDATE email_verify SET isVerified = 1 WHERE email_address = '$email_address'");

        if (!$update) {
            return -2; // 数据库错误/未知错误
        }

        return 0; // 验证码正确
    }

    public function getVerifyCode($verify_email)
    {
        $db = Database::getInstance()->getConnection();
        $value = $db->querySingle("SELECT email_verify_code FROM email_verify WHERE email_address = '$verify_email'");
        return $value;
    }

    public function getCodeCreatedTime($verify_email)
    {
        $db = Database::getInstance()->getConnection();
        $dateString = $db->querySingle("SELECT verify_code_created_at FROM email_verify WHERE email_address = '$verify_email'");
        $dateObject = new DateTime($dateString, $this->timezone);

        return $dateObject;
    }

    /**
     * 生成随机验证码字符串
     */
    private function generateCodeForEmail()
    {
        $chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890';
        $code = '';
        for ($i = 0; $i < $this->length_mail; $i++) {
            $code .= $chars[rand(0, strlen($chars) - 1)];
        }
        return $code;
    }
}
