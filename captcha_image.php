<?php
/**
 * 验证码图片生成接口
 */
session_start();
require_once 'includes/captcha.php';

$captcha = new Captcha();
$captcha->generate();
?>