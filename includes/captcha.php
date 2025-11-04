<?php
/**
 * 验证码功能类
 */

class Captcha {
    private $width = 120;
    private $height = 40;
    private $length = 4;
    private $font_size = 16;
    
    /**
     * 生成验证码
     */
    public function generate() {
        // 生成随机验证码
        $code = $this->generateCode();
        
        // 存储到session
        $_SESSION['captcha_code'] = strtolower($code);
        $_SESSION['captcha_time'] = time();
        
        // 创建图像
        $image = imagecreate($this->width, $this->height);
        
        // 设置颜色
        $bg_color = imagecolorallocate($image, 240, 240, 240);
        $text_color = imagecolorallocate($image, 50, 50, 50);
        $line_color = imagecolorallocate($image, 200, 200, 200);
        $noise_color = imagecolorallocate($image, 180, 180, 180);
        
        // 填充背景
        imagefill($image, 0, 0, $bg_color);
        
        // 添加干扰线
        for ($i = 0; $i < 5; $i++) {
            imageline($image, 
                rand(0, $this->width), rand(0, $this->height),
                rand(0, $this->width), rand(0, $this->height),
                $line_color
            );
        }
        
        // 添加噪点
        for ($i = 0; $i < 50; $i++) {
            imagesetpixel($image, 
                rand(0, $this->width), rand(0, $this->height),
                $noise_color
            );
        }
        
        // 添加验证码文字
        $x = 10;
        for ($i = 0; $i < strlen($code); $i++) {
            $char = $code[$i];
            $angle = rand(-15, 15);
            $y = rand(25, 35);
            
            // 使用内置字体
            imagestring($image, 5, $x, $y - 20, $char, $text_color);
            $x += 25;
        }
        
        // 输出图像
        header('Content-Type: image/png');
        header('Cache-Control: no-cache, no-store, must-revalidate');
        header('Pragma: no-cache');
        header('Expires: 0');
        
        imagepng($image);
        imagedestroy($image);
    }
    
    /**
     * 验证验证码
     */
    public function verify($input_code) {
        if (!isset($_SESSION['captcha_code']) || !isset($_SESSION['captcha_time'])) {
            return false;
        }
        
        // 检查验证码是否过期（10分钟）
        if (time() - $_SESSION['captcha_time'] > 600) {
            unset($_SESSION['captcha_code']);
            unset($_SESSION['captcha_time']);
            return false;
        }
        
        $result = strtolower($input_code) === $_SESSION['captcha_code'];
        
        // 只在验证成功时清除验证码，失败时保留以便重试
        if ($result) {
            unset($_SESSION['captcha_code']);
            unset($_SESSION['captcha_time']);
        }
        
        return $result;
    }
    
    /**
     * 生成随机验证码字符串
     */
    private function generateCode() {
        $chars = '123456789'; // 排除容易混淆的字符
        $code = '';
        for ($i = 0; $i < $this->length; $i++) {
            $code .= $chars[rand(0, strlen($chars) - 1)];
        }
        return $code;
    }
    
    /**
     * 获取验证码图片URL
     */
    public static function getImageUrl() {
        return 'captcha_image.php?t=' . time();
    }
}
?>