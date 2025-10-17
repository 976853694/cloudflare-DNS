<?php
session_start();
require_once '../config/database.php';
require_once '../config/cloudflare.php';
require_once '../config/dns_manager.php';
require_once '../includes/functions.php';

// 确保数据库连接可用
if (!isset($db)) {
    $db = Database::getInstance()->getConnection();
}

checkAdminLogin();

$db = Database::getInstance()->getConnection();
$action = getGet('action', 'list');
$messages = getMessages();

// 确保Cloudflare账户表存在
$db->exec("CREATE TABLE IF NOT EXISTS cloudflare_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    api_key TEXT NOT NULL,
    status INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)");

// 处理添加Cloudflare账户
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['add_account'])) {
    $name = getPost('name');
    $email = getPost('email');
    $api_key = getPost('api_key');
    
    if ($name && $email && $api_key) {
        // 验证Cloudflare API
        try {
            $cf = new CloudflareAPI($api_key, $email);
            
            // 获取详细验证信息
            $details = $cf->getVerificationDetails();
            
            if ($details['api_token_valid'] || $details['global_key_valid']) {
                $stmt = $db->prepare("INSERT INTO cloudflare_accounts (name, email, api_key) VALUES (?, ?, ?)");
                $stmt->bindValue(1, $name, SQLITE3_TEXT);
                $stmt->bindValue(2, $email, SQLITE3_TEXT);
                $stmt->bindValue(3, $api_key, SQLITE3_TEXT);
                
                if ($stmt->execute()) {
                    $auth_type = $details['api_token_valid'] ? 'API Token' : 'Global API Key';
                    logAction('admin', $_SESSION['admin_id'], 'add_cf_account', "添加Cloudflare账户: $name (使用 $auth_type)");
                    showSuccess("Cloudflare账户添加成功！(验证方式: $auth_type)");
                } else {
                    showError('账户添加失败！');
                }
            } else {
                $error_msg = 'Cloudflare API验证失败！';
                if ($details['error_message']) {
                    $error_msg .= ' 详细信息: ' . $details['error_message'];
                }
                $error_msg .= ' 请检查：1) 邮箱是否正确 2) API密钥是否有效 3) 网络连接是否正常';
                showError($error_msg);
            }
        } catch (Exception $e) {
            showError('API连接错误: ' . $e->getMessage() . ' 请检查网络连接或API密钥格式');
        }
    } else {
        showError('请填写完整信息！');
    }
    redirect('domains.php');
}

// 处理删除Cloudflare账户
if ($action === 'delete_account' && getGet('id')) {
    $id = (int)getGet('id');
    $account = $db->querySingle("SELECT name FROM cloudflare_accounts WHERE id = $id", true);
    
    if ($account) {
        $db->exec("DELETE FROM cloudflare_accounts WHERE id = $id");
        logAction('admin', $_SESSION['admin_id'], 'delete_cf_account', "删除Cloudflare账户: {$account['name']}");
        showSuccess('Cloudflare账户删除成功！');
    } else {
        showError('账户不存在！');
    }
    redirect('domains.php');
}

// 处理添加彩虹DNS域名
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['add_rainbow_domain'])) {
    $domain_name = getPost('domain_name');
    $api_key = getPost('api_key');
    $provider_uid = getPost('provider_uid');
    $api_base_url = getPost('api_base_url');
    $zone_id = getPost('zone_id');
    
    if ($domain_name && $api_key && $provider_uid && $api_base_url && $zone_id) {
        try {
            // 验证彩虹DNS API
            $rainbow_api = new RainbowDNSAPI($provider_uid, $api_key, $api_base_url);
            if ($rainbow_api->verifyCredentials()) {
                // 获取域名到期时间
                $expiration_time = getDomainExpirationTime($domain_name);
                
                $stmt = $db->prepare("INSERT INTO domains (domain_name, api_key, email, zone_id, proxied_default, provider_type, provider_uid, api_base_url, expiration_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)");
                $stmt->bindValue(1, $domain_name, SQLITE3_TEXT);
                $stmt->bindValue(2, $api_key, SQLITE3_TEXT);
                $stmt->bindValue(3, '', SQLITE3_TEXT); // 彩虹DNS不需要email
                $stmt->bindValue(4, $zone_id, SQLITE3_TEXT);
                $stmt->bindValue(5, 0, SQLITE3_INTEGER); // 彩虹DNS不支持代理
                $stmt->bindValue(6, 'rainbow', SQLITE3_TEXT);
                $stmt->bindValue(7, $provider_uid, SQLITE3_TEXT);
                $stmt->bindValue(8, $api_base_url, SQLITE3_TEXT);
                $stmt->bindValue(9, $expiration_time, SQLITE3_TEXT);
                
                if ($stmt->execute()) {
                    logAction('admin', $_SESSION['admin_id'], 'add_rainbow_domain', "添加彩虹DNS域名: $domain_name");
                    showSuccess('彩虹DNS域名添加成功！');
                } else {
                    showError('域名添加失败，可能已存在！');
                }
            } else {
                showError('彩虹DNS API验证失败，请检查配置！');
            }
        } catch (Exception $e) {
            showError('彩虹DNS API错误: ' . $e->getMessage());
        }
    } else {
        showError('请填写完整的彩虹DNS配置信息！');
    }
    redirect('domains.php');
}

// 处理从彩虹DNS账户获取域名列表
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['fetch_rainbow_domains_from_account'])) {
    $rainbow_account_id = getPost('rainbow_account_id');
    
    if ($rainbow_account_id) {
        $account = $db->querySingle("SELECT * FROM rainbow_accounts WHERE id = $rainbow_account_id", true);
        if ($account) {
            try {
                $rainbow_api = new RainbowDNSAPI($account['provider_uid'], $account['api_key'], $account['api_base_url']);
                $domains_response = $rainbow_api->getDomains(0, 100);
                
                if (isset($domains_response['rows'])) {
                    $_SESSION['fetched_rainbow_domains'] = $domains_response['rows'];
                    $_SESSION['rainbow_config'] = [
                        'api_key' => $account['api_key'],
                        'provider_uid' => $account['provider_uid'],
                        'api_base_url' => $account['api_base_url']
                    ];
                    
                    showSuccess("成功获取到 " . count($domains_response['rows']) . " 个彩虹DNS域名，请选择要添加的域名！");
                    redirect('domains.php?action=select_rainbow_domains');
                } else {
                    showError('未获取到域名列表！');
                }
            } catch (Exception $e) {
                showError('获取彩虹DNS域名失败: ' . $e->getMessage());
            }
        } else {
            showError('彩虹DNS账户不存在！');
        }
    } else {
        showError('请选择彩虹DNS账户！');
    }
    redirect('domains.php');
}

// 处理从DNSPod账户获取域名列表
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['fetch_dnspod_domains_from_account'])) {
    $dnspod_account_id = getPost('dnspod_account_id');
    
    if ($dnspod_account_id) {
        $account = $db->querySingle("SELECT * FROM dnspod_accounts WHERE id = $dnspod_account_id", true);
        if ($account) {
            try {
                require_once '../config/dns_providers.php';
                
                // 直接创建DNSPod配置，不经过转换
                $config = [
                    'ak' => $account['secret_id'],
                    'sk' => $account['secret_key'], 
                    'domain' => '',
                    'proxy' => false
                ];
                
                $dnspod_api = DNSProviderFactory::create('dnspod', $config);
                $domains_response = $dnspod_api->getDomainList();
                
                if ($domains_response && isset($domains_response['list'])) {
                    $_SESSION['fetched_dnspod_domains'] = $domains_response['list'];
                    $_SESSION['dnspod_config'] = [
                        'secret_id' => $account['secret_id'],
                        'secret_key' => $account['secret_key']
                    ];
                    
                    showSuccess("成功获取到 " . count($domains_response['list']) . " 个DNSPod域名，请选择要添加的域名！");
                    redirect('domains.php?action=select_dnspod_domains');
                } else {
                    showError('未获取到DNSPod域名列表！返回数据: ' . json_encode($domains_response));
                }
            } catch (Exception $e) {
                showError('获取DNSPod域名失败: ' . $e->getMessage() . ' 在文件: ' . $e->getFile() . ' 第 ' . $e->getLine() . ' 行');
            }
        } else {
            showError('DNSPod账户不存在！');
        }
    } else {
        showError('请选择DNSPod账户！');
    }
    redirect('domains.php');
}

// 处理从PowerDNS账户获取域名列表
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['fetch_powerdns_domains_from_account'])) {
    $powerdns_account_id = getPost('powerdns_account_id');
    
    if ($powerdns_account_id) {
        $account = $db->querySingle("SELECT * FROM powerdns_accounts WHERE id = $powerdns_account_id", true);
        if ($account) {
            try {
                require_once '../config/dns_providers.php';
                $config = DNSProviderFactory::convertConfig('powerdns', [
                    'api_url' => $account['api_url'],
                    'api_key' => $account['api_key'],
                    'domain' => '', // 获取域名列表时不需要指定域名
                    'domain_id' => '' // 获取域名列表时不需要指定域名ID
                ]);
                
                $powerdns_api = DNSProviderFactory::create('powerdns', $config);
                $domains_response = $powerdns_api->getDomainList();
                
                if ($domains_response && isset($domains_response['list'])) {
                    $_SESSION['fetched_powerdns_domains'] = $domains_response['list'];
                    $_SESSION['powerdns_config'] = [
                        'api_url' => $account['api_url'],
                        'api_key' => $account['api_key'],
                        'server_id' => $account['server_id']
                    ];
                    
                    showSuccess("成功获取到 " . count($domains_response['list']) . " 个PowerDNS域名，请选择要添加的域名！");
                    redirect('domains.php?action=select_powerdns_domains');
                } else {
                    showError('未获取到PowerDNS域名列表！');
                }
            } catch (Exception $e) {
                showError('获取PowerDNS域名失败: ' . $e->getMessage());
            }
        } else {
            showError('PowerDNS账户不存在！');
        }
    } else {
        showError('请选择PowerDNS账户！');
    }
    redirect('domains.php');
}

// 处理批量添加彩虹DNS域名
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['add_selected_rainbow_domains'])) {
    $selected_domains = isset($_POST['selected_domains']) ? $_POST['selected_domains'] : [];
    
    if (!empty($selected_domains) && isset($_SESSION['rainbow_config'])) {
        $config = $_SESSION['rainbow_config'];
        $domains = $_SESSION['fetched_rainbow_domains'];
        
        $added_count = 0;
        foreach ($selected_domains as $domain_id) {
            // 找到对应的域名信息
            $domain_info = null;
            foreach ($domains as $domain) {
                if ($domain['id'] == $domain_id) {
                    $domain_info = $domain;
                    break;
                }
            }
            
            if ($domain_info) {
                // 检查域名是否已存在
                $exists = $db->querySingle("SELECT COUNT(*) FROM domains WHERE domain_name = '{$domain_info['name']}'");
                if (!$exists) {
                    // 获取域名到期时间
                    $expiration_time = getDomainExpirationTime($domain_info['name']);
                    
                    $stmt = $db->prepare("INSERT INTO domains (domain_name, api_key, email, zone_id, proxied_default, provider_type, provider_uid, api_base_url, expiration_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)");
                    $stmt->bindValue(1, $domain_info['name'], SQLITE3_TEXT);
                    $stmt->bindValue(2, $config['api_key'], SQLITE3_TEXT);
                    $stmt->bindValue(3, '', SQLITE3_TEXT);
                    $stmt->bindValue(4, $domain_info['thirdid'], SQLITE3_TEXT); // 使用thirdid作为zone_id
                    $stmt->bindValue(5, 0, SQLITE3_INTEGER);
                    $stmt->bindValue(6, 'rainbow', SQLITE3_TEXT);
                    $stmt->bindValue(7, $config['provider_uid'], SQLITE3_TEXT);
                    $stmt->bindValue(8, $config['api_base_url'], SQLITE3_TEXT);
                    $stmt->bindValue(9, $expiration_time, SQLITE3_TEXT);
                    
                    if ($stmt->execute()) {
                        $added_count++;
                    }
                }
            }
        }
        
        // 清除session数据
        unset($_SESSION['fetched_rainbow_domains']);
        unset($_SESSION['rainbow_config']);
        
        logAction('admin', $_SESSION['admin_id'], 'batch_add_rainbow_domains', "批量添加彩虹DNS域名，成功添加了 $added_count 个域名");
        showSuccess("成功添加 $added_count 个彩虹DNS域名！");
    } else {
        if (empty($selected_domains)) {
            showError('请至少选择一个域名进行添加！');
        } else {
            showError('会话已过期，请重新获取域名列表！');
        }
    }
    redirect('domains.php');
}

// 处理批量添加DNSPod域名
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['add_selected_dnspod_domains'])) {
    $selected_domains = isset($_POST['selected_domains']) ? $_POST['selected_domains'] : [];
    
    if (!empty($selected_domains) && isset($_SESSION['dnspod_config'])) {
        $config = $_SESSION['dnspod_config'];
        $domains = $_SESSION['fetched_dnspod_domains'];
        
        $added_count = 0;
        foreach ($selected_domains as $domain_id) {
            // 找到对应的域名信息
            $domain_info = null;
            foreach ($domains as $domain) {
                if ($domain['DomainId'] == $domain_id) {
                    $domain_info = $domain;
                    break;
                }
            }
            
            if ($domain_info) {
                // 检查域名是否已存在
                $exists = $db->querySingle("SELECT COUNT(*) FROM domains WHERE domain_name = '{$domain_info['Domain']}'");
                if (!$exists) {
                    // 获取域名到期时间
                    $expiration_time = getDomainExpirationTime($domain_info['Domain']);
                    
                    $stmt = $db->prepare("INSERT INTO domains (domain_name, api_key, email, zone_id, proxied_default, provider_type, provider_uid, api_base_url, expiration_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)");
                    $stmt->bindValue(1, $domain_info['Domain'], SQLITE3_TEXT);
                    $stmt->bindValue(2, $config['secret_id'], SQLITE3_TEXT);
                    $stmt->bindValue(3, '', SQLITE3_TEXT); // DNSPod不需要email
                    $stmt->bindValue(4, $domain_info['DomainId'], SQLITE3_TEXT);
                    $stmt->bindValue(5, 0, SQLITE3_INTEGER); // DNSPod不支持代理
                    $stmt->bindValue(6, 'dnspod', SQLITE3_TEXT);
                    $stmt->bindValue(7, $config['secret_key'], SQLITE3_TEXT);
                    $stmt->bindValue(8, '', SQLITE3_TEXT); // DNSPod不需要api_base_url
                    $stmt->bindValue(9, $expiration_time, SQLITE3_TEXT);
                    
                    if ($stmt->execute()) {
                        $added_count++;
                    }
                }
            }
        }
        
        // 清除session数据
        unset($_SESSION['fetched_dnspod_domains']);
        unset($_SESSION['dnspod_config']);
        
        logAction('admin', $_SESSION['admin_id'], 'batch_add_dnspod_domains', "批量添加DNSPod域名，成功添加了 $added_count 个域名");
        showSuccess("成功添加 $added_count 个DNSPod域名！");
    } else {
        if (empty($selected_domains)) {
            showError('请至少选择一个域名进行添加！');
        } else {
            showError('会话已过期，请重新获取域名列表！');
        }
    }
    redirect('domains.php');
}

// 处理批量添加PowerDNS域名
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['add_selected_powerdns_domains'])) {
    $selected_domains = isset($_POST['selected_domains']) ? $_POST['selected_domains'] : [];
    
    if (!empty($selected_domains) && isset($_SESSION['powerdns_config'])) {
        $config = $_SESSION['powerdns_config'];
        $domains = $_SESSION['fetched_powerdns_domains'];
        
        $added_count = 0;
        foreach ($selected_domains as $domain_id) {
            // 找到对应的域名信息
            $domain_info = null;
            foreach ($domains as $domain) {
                if ($domain['DomainId'] == $domain_id) {
                    $domain_info = $domain;
                    break;
                }
            }
            
            if ($domain_info) {
                // 检查域名是否已存在
                $exists = $db->querySingle("SELECT COUNT(*) FROM domains WHERE domain_name = '{$domain_info['Domain']}'");
                if (!$exists) {
                    // 获取域名到期时间
                    $expiration_time = getDomainExpirationTime($domain_info['Domain']);
                    
                    $stmt = $db->prepare("INSERT INTO domains (domain_name, api_key, email, zone_id, proxied_default, provider_type, provider_uid, api_base_url, expiration_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)");
                    $stmt->bindValue(1, $domain_info['Domain'], SQLITE3_TEXT);
                    $stmt->bindValue(2, $config['api_key'], SQLITE3_TEXT);
                    $stmt->bindValue(3, '', SQLITE3_TEXT); // PowerDNS不需要email
                    $stmt->bindValue(4, $domain_info['DomainId'], SQLITE3_TEXT);
                    $stmt->bindValue(5, 0, SQLITE3_INTEGER); // PowerDNS不支持代理
                    $stmt->bindValue(6, 'powerdns', SQLITE3_TEXT);
                    $stmt->bindValue(7, $config['server_id'], SQLITE3_TEXT);
                    $stmt->bindValue(8, $config['api_url'], SQLITE3_TEXT);
                    $stmt->bindValue(9, $expiration_time, SQLITE3_TEXT);
                    
                    if ($stmt->execute()) {
                        $added_count++;
                    }
                }
            }
        }
        
        // 清除session数据
        unset($_SESSION['fetched_powerdns_domains']);
        unset($_SESSION['powerdns_config']);
        
        logAction('admin', $_SESSION['admin_id'], 'batch_add_powerdns_domains', "批量添加PowerDNS域名，成功添加了 $added_count 个域名");
        showSuccess("成功添加 $added_count 个PowerDNS域名！");
    } else {
        if (empty($selected_domains)) {
            showError('请至少选择一个域名进行添加！');
        } else {
            showError('会话已过期，请重新获取域名列表！');
        }
    }
    redirect('domains.php');
}

// 处理添加域名
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['add_domain'])) {
    $account_id = getPost('account_id');
    $domain_name = getPost('domain_name');
    $zone_id = getPost('zone_id');
    $proxied_default = getPost('proxied_default', 0);
    
    if ($account_id && $domain_name && $zone_id) {
        // 获取账户信息
        $account = $db->querySingle("SELECT * FROM cloudflare_accounts WHERE id = $account_id", true);
        if ($account) {
            // 获取域名到期时间
            $expiration_time = getDomainExpirationTime($domain_name);
            
            $stmt = $db->prepare("INSERT INTO domains (domain_name, api_key, email, zone_id, proxied_default, expiration_time) VALUES (?, ?, ?, ?, ?, ?)");
            $stmt->bindValue(1, $domain_name, SQLITE3_TEXT);
            $stmt->bindValue(2, $account['api_key'], SQLITE3_TEXT);
            $stmt->bindValue(3, $account['email'], SQLITE3_TEXT);
            $stmt->bindValue(4, $zone_id, SQLITE3_TEXT);
            $stmt->bindValue(5, $proxied_default, SQLITE3_INTEGER);
            $stmt->bindValue(6, $expiration_time, SQLITE3_TEXT);
            
            if ($stmt->execute()) {
                logAction('admin', $_SESSION['admin_id'], 'add_domain', "添加域名: $domain_name");
                showSuccess('域名添加成功！');
            } else {
                showError('域名添加失败，可能已存在！');
            }
        } else {
            showError('Cloudflare账户不存在！');
        }
    } else {
        showError('请填写完整信息！');
    }
    redirect('domains.php');
}

// 处理获取域名列表（第一步）
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['fetch_domains'])) {
    $account_id = getPost('account_id');
    
    if ($account_id) {
        $account = $db->querySingle("SELECT * FROM cloudflare_accounts WHERE id = $account_id", true);
        if ($account) {
            try {
                $cf = new CloudflareAPI($account['api_key'], $account['email']);
                $zones = $cf->getZones();
                
                // 将域名列表存储在session中，用于选择
                $_SESSION['fetched_zones'] = $zones;
                $_SESSION['selected_account'] = $account;
                
                showSuccess("成功获取到 " . count($zones) . " 个域名，请选择要添加的域名！");
            } catch (Exception $e) {
                showError('获取域名失败: ' . $e->getMessage());
            }
        } else {
            showError('Cloudflare账户不存在！');
        }
    } else {
        showError('请选择Cloudflare账户！');
    }
    redirect('domains.php?action=select_domains');
}

// 处理批量添加选中的域名
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['add_selected_domains'])) {
    $selected_domains = isset($_POST['selected_domains']) ? $_POST['selected_domains'] : [];
    $proxied_default = getPost('proxied_default', 0);
    
    if (!empty($selected_domains) && isset($_SESSION['selected_account'])) {
        $account = $_SESSION['selected_account'];
        $zones = $_SESSION['fetched_zones'];
        
        $added_count = 0;
        foreach ($selected_domains as $zone_id) {
            // 找到对应的域名信息
            $zone_info = null;
            foreach ($zones as $zone) {
                if ($zone['id'] === $zone_id) {
                    $zone_info = $zone;
                    break;
                }
            }
            
            if ($zone_info) {
                // 检查域名是否已存在
                $exists = $db->querySingle("SELECT COUNT(*) FROM domains WHERE domain_name = '{$zone_info['name']}'");
                if (!$exists) {
                    // 获取域名到期时间
                    $expiration_time = getDomainExpirationTime($zone_info['name']);
                    
                    $stmt = $db->prepare("INSERT INTO domains (domain_name, api_key, email, zone_id, proxied_default, expiration_time) VALUES (?, ?, ?, ?, ?, ?)");
                    $stmt->bindValue(1, $zone_info['name'], SQLITE3_TEXT);
                    $stmt->bindValue(2, $account['api_key'], SQLITE3_TEXT);
                    $stmt->bindValue(3, $account['email'], SQLITE3_TEXT);
                    $stmt->bindValue(4, $zone_info['id'], SQLITE3_TEXT);
                    $stmt->bindValue(5, $proxied_default, SQLITE3_INTEGER);
                    $stmt->bindValue(6, $expiration_time, SQLITE3_TEXT);
                    
                    if ($stmt->execute()) {
                        $added_count++;
                    }
                }
            }
        }
        
        // 清除session数据
        unset($_SESSION['fetched_zones']);
        unset($_SESSION['selected_account']);
        
        logAction('admin', $_SESSION['admin_id'], 'batch_add_domains', "批量添加域名，成功添加了 $added_count 个域名");
        showSuccess("成功添加 $added_count 个域名！");
    } else {
        // 提供更详细的错误信息
        if (empty($selected_domains)) {
            showError('请至少选择一个域名进行添加！');
        } elseif (!isset($_SESSION['selected_account'])) {
            showError('会话已过期，请重新获取域名列表！');
        } else {
            showError('请选择要添加的域名！');
        }
    }
    redirect('domains.php');
}

// 处理获取DNS记录数量（AJAX endpoint）
if ($action === 'get_dns_count' && getGet('domain_id')) {
    $domain_id = (int)getGet('domain_id');
    $record_count = $db->querySingle("SELECT COUNT(*) FROM dns_records WHERE domain_id = $domain_id");
    header('Content-Type: application/json');
    echo json_encode(['record_count' => $record_count]);
    exit;
}

// 处理更新域名到期时间
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['update_expiration'])) {
    $domain_id = getPost('domain_id');
    
    if ($domain_id) {
        $domain = $db->querySingle("SELECT * FROM domains WHERE id = $domain_id", true);
        if ($domain) {
            $expiration_time = getDomainExpirationTime($domain['domain_name']);
            
            $stmt = $db->prepare("UPDATE domains SET expiration_time = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?");
            $stmt->bindValue(1, $expiration_time, SQLITE3_TEXT);
            $stmt->bindValue(2, $domain_id, SQLITE3_INTEGER);
            
            if ($stmt->execute()) {
                if ($expiration_time) {
                    logAction('admin', $_SESSION['admin_id'], 'update_expiration', "更新域名到期时间: {$domain['domain_name']} -> $expiration_time");
                    echo json_encode(['success' => true, 'message' => '域名到期时间更新成功！', 'expiration_time' => $expiration_time]);
                } else {
                    echo json_encode(['success' => true, 'message' => '该域名为永久域名或无法获取到期时间', 'expiration_time' => null]);
                }
            } else {
                echo json_encode(['success' => false, 'message' => '更新失败！']);
            }
        } else {
            echo json_encode(['success' => false, 'message' => '域名不存在！']);
        }
    } else {
        echo json_encode(['success' => false, 'message' => '缺少域名ID！']);
    }
    exit;
}

// 处理删除域名
if ($action === 'delete' && getGet('id')) {
    $id = (int)getGet('id');
    $domain = $db->querySingle("SELECT * FROM domains WHERE id = $id", true);
    
    if ($domain) {
        $deleted_count = 0;
        $skipped_count = 0;
        $error_count = 0;
        $provider_errors = [];
        
        try {
            // 第一步：获取该域名下的所有DNS记录
            $dns_records = [];
            $result = $db->query("SELECT * FROM dns_records WHERE domain_id = $id");
            while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
                $dns_records[] = $row;
            }
            
            $total_records = count($dns_records);
            
            // 第二步：尝试从DNS提供商删除记录
            if ($total_records > 0) {
                $provider_type = $domain['provider_type'] ?? 'cloudflare';
                
                if ($provider_type === 'cloudflare') {
                    // 处理Cloudflare记录
                    try {
                        $cf = new CloudflareAPI($domain['api_key'], $domain['email']);
                        
                        foreach ($dns_records as $record) {
                            if (!empty($record['cloudflare_id'])) {
                                try {
                                    // 尝试从Cloudflare删除
                                    $cf->deleteDNSRecord($domain['zone_id'], $record['cloudflare_id']);
                                    $deleted_count++;
                                } catch (Exception $e) {
                                    // 记录提供商删除失败的错误，但继续处理
                                    $provider_errors[] = "记录 {$record['subdomain']}.{$domain['domain_name']} 删除失败: " . $e->getMessage();
                                    $error_count++;
                                }
                            } else {
                                // 没有cloudflare_id的记录直接跳过
                                $skipped_count++;
                            }
                        }
                    } catch (Exception $e) {
                        // API连接失败，记录错误但继续删除本地记录
                        $provider_errors[] = "无法连接到Cloudflare API: " . $e->getMessage();
                        $error_count = $total_records;
                    }
                } elseif ($provider_type === 'rainbow') {
                    // 处理彩虹DNS记录
                    try {
                        require_once '../config/rainbow_dns.php';
                        $rainbow = new RainbowDNSAPI($domain['provider_uid'], $domain['api_key'], $domain['api_base_url']);
                        
                        foreach ($dns_records as $record) {
                            if (!empty($record['cloudflare_id'])) { // 在彩虹DNS中也使用这个字段存储记录ID
                                try {
                                    // 尝试从彩虹DNS删除（需要domain_id和record_id）
                                    $rainbow->deleteDNSRecord($domain['zone_id'], $record['cloudflare_id']);
                                    $deleted_count++;
                                } catch (Exception $e) {
                                    $provider_errors[] = "记录 {$record['subdomain']}.{$domain['domain_name']} 删除失败: " . $e->getMessage();
                                    $error_count++;
                                }
                            } else {
                                $skipped_count++;
                            }
                        }
                    } catch (Exception $e) {
                        $provider_errors[] = "无法连接到彩虹DNS API: " . $e->getMessage();
                        $error_count = $total_records;
                    }
                } else {
                    // 自定义或其他类型的DNS记录，跳过提供商删除
                    $skipped_count = $total_records;
                }
            }
            
            // 第三步：删除所有本地DNS记录（无论提供商删除是否成功）
            $db->exec("DELETE FROM dns_records WHERE domain_id = $id");
            
            // 第四步：删除域名本身
            $db->exec("DELETE FROM domains WHERE id = $id");
            
            // 记录日志
            logAction('admin', $_SESSION['admin_id'], 'delete_domain', "删除域名: {$domain['domain_name']} (记录总数: $total_records, 成功删除: $deleted_count, 跳过: $skipped_count, 错误: $error_count)");
            
            // 生成详细的成功消息
            $message = "域名 {$domain['domain_name']} 删除成功！";
            if ($total_records > 0) {
                $message .= " 共处理 $total_records 条DNS记录";
                if ($deleted_count > 0) {
                    $message .= "，成功从DNS提供商删除 $deleted_count 条";
                }
                if ($skipped_count > 0) {
                    $message .= "，跳过 $skipped_count 条";
                }
                if ($error_count > 0) {
                    $message .= "，$error_count 条删除失败但已从本地清除";
                }
            }
            
            showSuccess($message);
            
            // 如果有提供商删除错误，显示详细信息
            if (!empty($provider_errors)) {
                $error_detail = "DNS提供商删除过程中的详细错误：\\n" . implode("\\n", array_slice($provider_errors, 0, 5));
                if (count($provider_errors) > 5) {
                    $error_detail .= "\\n... 还有 " . (count($provider_errors) - 5) . " 个错误";
                }
                showWarning("部分DNS记录无法从提供商删除，但域名和本地记录已清理完成。详细信息：" . $error_detail);
            }
            
        } catch (Exception $e) {
            // 如果删除过程中出现严重错误，尝试至少删除本地记录
            try {
                $db->exec("DELETE FROM dns_records WHERE domain_id = $id");
                $db->exec("DELETE FROM domains WHERE id = $id");
                logAction('admin', $_SESSION['admin_id'], 'delete_domain', "强制删除域名: {$domain['domain_name']} (遇到错误: {$e->getMessage()})");
                showWarning("域名删除完成，但删除过程中遇到错误：" . $e->getMessage());
            } catch (Exception $cleanup_error) {
                logAction('admin', $_SESSION['admin_id'], 'delete_domain_failed', "删除域名失败: {$domain['domain_name']} (错误: {$cleanup_error->getMessage()})");
                showError('域名删除失败：' . $cleanup_error->getMessage());
            }
        }
    } else {
        showError('域名不存在！');
    }
    redirect('domains.php');
}

// 获取Cloudflare账户列表
$cf_accounts = [];
$result = $db->query("SELECT * FROM cloudflare_accounts ORDER BY created_at DESC");
while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $cf_accounts[] = $row;
}

// 获取域名列表
$domains = [];
$result = $db->query("SELECT * FROM domains ORDER BY created_at DESC");
while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $domains[] = $row;
}

$page_title = '域名管理';
include 'includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <?php include 'includes/sidebar.php'; ?>
        
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="main-content">
            <!-- 页面标题和操作按钮 -->
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3" style="border-bottom: 1px solid rgba(255, 255, 255, 0.2);">
                <h1 class="h2">域名管理</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <div class="btn-group me-2">
                        <!--<button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addDomainModal">-->
                        <!--    <i class="fas fa-plus me-1"></i>手动添加域名-->
                        <!--</button>-->
                        <div class="btn-group">
                            <button type="button" class="btn btn-success dropdown-toggle" data-bs-toggle="dropdown">
                                <i class="fas fa-download me-1"></i>获取域名
                            </button>
                            <ul class="dropdown-menu">
                                <li><a class="dropdown-item" href="#" data-bs-toggle="modal" data-bs-target="#fetchDomainsModal">
                                    <i class="fab fa-cloudflare me-2"></i>从Cloudflare获取
                                </a></li>
                                <li><a class="dropdown-item" href="#" data-bs-toggle="modal" data-bs-target="#fetchRainbowDomainsModal">
                                    <i class="fas fa-rainbow me-2"></i>从彩虹DNS获取
                                </a></li>
                                <li><a class="dropdown-item" href="#" data-bs-toggle="modal" data-bs-target="#fetchDnspodDomainsModal">
                                    <i class="fas fa-cloud me-2"></i>从DNSPod获取
                                </a></li>
                                <li><a class="dropdown-item" href="#" data-bs-toggle="modal" data-bs-target="#fetchPowerdnsDomainsModal">
                                    <i class="fas fa-server me-2"></i>从PowerDNS获取
                                </a></li>
                            </ul>
                        </div>
                    </div>
                    <div class="btn-group">
                        <a href="channels_management.php" class="btn btn-outline-info">
                            <i class="fas fa-plug me-1"></i>渠道管理
                        </a>
                    </div>
                </div>
            </div>
            
            <?php if ($action === 'select_domains' && isset($_SESSION['fetched_zones'])): ?>
            <!-- 选择域名界面 -->
            <div class="card shadow">
                <div class="card-header">
                    <h6 class="m-0 font-weight-bold text-primary">选择要添加的域名</h6>
                    <small class="text-muted">从Cloudflare账户: <?php echo htmlspecialchars($_SESSION['selected_account']['name']); ?></small>
                </div>
                <div class="card-body">
                    <form method="post" action="domains.php" onsubmit="return validateSelection()">
                        <div class="mb-3">
                            <label class="form-check-label">
                                <input type="checkbox" id="selectAll" onchange="toggleAll(this)"> 全选/取消全选
                            </label>
                        </div>
                        <div class="table-responsive">
                            <table class="table table-bordered">
                                <thead>
                                    <tr>
                                        <th width="50">选择</th>
                                        <th>域名</th>
                                        <th>Zone ID</th>
                                        <th>状态</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <?php foreach ($_SESSION['fetched_zones'] as $zone): ?>
                                    <tr>
                                        <td>
                                            <input type="checkbox" class="form-check-input domain-checkbox" 
                                                   name="selected_domains[]" value="<?php echo htmlspecialchars($zone['id']); ?>">
                                        </td>
                                        <td><?php echo htmlspecialchars($zone['name']); ?></td>
                                        <td><code><?php echo htmlspecialchars($zone['id']); ?></code></td>
                                        <td>
                                            <span class="badge <?php echo $zone['status'] === 'active' ? 'bg-success' : 'bg-warning'; ?>">
                                                <?php echo $zone['status']; ?>
                                            </span>
                                        </td>
                                    </tr>
                                    <?php endforeach; ?>
                                </tbody>
                            </table>
                        </div>
                        <div class="mt-3">
                            <button type="submit" name="add_selected_domains" class="btn btn-primary">
                                <i class="fas fa-plus me-1"></i>添加选中的域名
                            </button>
                            <a href="domains.php" class="btn btn-secondary">
                                <i class="fas fa-arrow-left me-1"></i>返回域名列表
                            </a>
                        </div>
                    </form>
                </div>
            </div>
            <?php elseif ($action === 'select_dnspod_domains' && isset($_SESSION['fetched_dnspod_domains'])): ?>
            <!-- 选择DNSPod域名界面 -->
            <div class="card shadow">
                <div class="card-header">
                    <h6 class="m-0 font-weight-bold text-primary">选择要添加的DNSPod域名</h6>
                </div>
                <div class="card-body">
                    <form method="post" action="domains.php" onsubmit="return validateDnspodSelection()">
                        <div class="mb-3">
                            <label class="form-check-label">
                                <input type="checkbox" id="selectAllDnspod" onchange="toggleAllDnspod(this)"> 全选/取消全选
                            </label>
                        </div>
                        <div class="table-responsive">
                            <table class="table table-bordered">
                                <thead>
                                    <tr>
                                        <th width="50">选择</th>
                                        <th>域名</th>
                                        <th>域名ID</th>
                                        <th>记录数</th>
                                        <th>状态</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <?php foreach ($_SESSION['fetched_dnspod_domains'] as $domain): ?>
                                    <tr>
                                        <td>
                                            <input type="checkbox" class="form-check-input dnspod-domain-checkbox" 
                                                   name="selected_domains[]" value="<?php echo htmlspecialchars($domain['DomainId']); ?>">
                                        </td>
                                        <td><?php echo htmlspecialchars($domain['Domain']); ?></td>
                                        <td><code><?php echo htmlspecialchars($domain['DomainId']); ?></code></td>
                                        <td><?php echo $domain['RecordCount'] ?? 0; ?></td>
                                        <td>
                                            <span class="badge bg-success">DNSPod</span>
                                        </td>
                                    </tr>
                                    <?php endforeach; ?>
                                </tbody>
                            </table>
                        </div>
                        <div class="mt-3">
                            <button type="submit" name="add_selected_dnspod_domains" class="btn btn-primary">
                                <i class="fas fa-plus me-1"></i>添加选中的域名
                            </button>
                            <a href="domains.php" class="btn btn-secondary">
                                <i class="fas fa-arrow-left me-1"></i>返回域名列表
                            </a>
                        </div>
                    </form>
                </div>
            </div>
            <?php elseif ($action === 'select_powerdns_domains' && isset($_SESSION['fetched_powerdns_domains'])): ?>
            <!-- 选择PowerDNS域名界面 -->
            <div class="card shadow">
                <div class="card-header">
                    <h6 class="m-0 font-weight-bold text-primary">选择要添加的PowerDNS域名</h6>
                </div>
                <div class="card-body">
                    <form method="post" action="domains.php" onsubmit="return validatePowerdnsSelection()">
                        <div class="mb-3">
                            <label class="form-check-label">
                                <input type="checkbox" id="selectAllPowerdns" onchange="toggleAllPowerdns(this)"> 全选/取消全选
                            </label>
                        </div>
                        <div class="table-responsive">
                            <table class="table table-bordered">
                                <thead>
                                    <tr>
                                        <th width="50">选择</th>
                                        <th>域名</th>
                                        <th>域名ID</th>
                                        <th>状态</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <?php foreach ($_SESSION['fetched_powerdns_domains'] as $domain): ?>
                                    <tr>
                                        <td>
                                            <input type="checkbox" class="form-check-input powerdns-domain-checkbox" 
                                                   name="selected_domains[]" value="<?php echo htmlspecialchars($domain['DomainId']); ?>">
                                        </td>
                                        <td><?php echo htmlspecialchars($domain['Domain']); ?></td>
                                        <td><code><?php echo htmlspecialchars($domain['DomainId']); ?></code></td>
                                        <td>
                                            <span class="badge bg-primary">PowerDNS</span>
                                        </td>
                                    </tr>
                                    <?php endforeach; ?>
                                </tbody>
                            </table>
                        </div>
                        <div class="mt-3">
                            <button type="submit" name="add_selected_powerdns_domains" class="btn btn-primary">
                                <i class="fas fa-plus me-1"></i>添加选中的域名
                            </button>
                            <a href="domains.php" class="btn btn-secondary">
                                <i class="fas fa-arrow-left me-1"></i>返回域名列表
                            </a>
                        </div>
                    </form>
                </div>
            </div>
            <?php elseif ($action === 'select_rainbow_domains' && isset($_SESSION['fetched_rainbow_domains'])): ?>
            <!-- 选择彩虹DNS域名界面 -->
            <div class="card shadow">
                <div class="card-header">
                    <h6 class="m-0 font-weight-bold text-primary">选择要添加的彩虹DNS域名</h6>
                </div>
                <div class="card-body">
                    <form method="post" action="domains.php" onsubmit="return validateRainbowSelection()">
                        <div class="mb-3">
                            <label class="form-check-label">
                                <input type="checkbox" id="selectAllRainbow" onchange="toggleAllRainbow(this)"> 全选/取消全选
                            </label>
                        </div>
                        <div class="table-responsive">
                            <table class="table table-bordered">
                                <thead>
                                    <tr>
                                        <th width="50">选择</th>
                                        <th>域名</th>
                                        <th>Zone ID</th>
                                        <th>状态</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <?php foreach ($_SESSION['fetched_rainbow_domains'] as $domain): ?>
                                    <tr>
                                        <td>
                                            <input type="checkbox" class="form-check-input rainbow-domain-checkbox" 
                                                   name="selected_domains[]" value="<?php echo htmlspecialchars($domain['id']); ?>">
                                        </td>
                                        <td><?php echo htmlspecialchars($domain['name']); ?></td>
                                        <td><code><?php echo htmlspecialchars($domain['thirdid']); ?></code></td>
                                        <td>
                                            <span class="badge bg-info">彩虹DNS</span>
                                        </td>
                                    </tr>
                                    <?php endforeach; ?>
                                </tbody>
                            </table>
                        </div>
                        <div class="mt-3">
                            <button type="submit" name="add_selected_rainbow_domains" class="btn btn-primary">
                                <i class="fas fa-plus me-1"></i>添加选中的域名
                            </button>
                            <a href="domains.php" class="btn btn-secondary">
                                <i class="fas fa-arrow-left me-1"></i>返回域名列表
                            </a>
                        </div>
                    </form>
                </div>
            </div>
            <?php else: ?>
            <!-- 域名列表 -->
            <div class="card shadow">
                <div class="card-header">
                    <h6 class="m-0 font-weight-bold text-primary">域名列表</h6>
                </div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-bordered" id="domainsTable">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>域名</th>
                                    <th>DNS提供商</th>
                                    <th>邮箱</th>
                                    <th>Zone ID</th>
                                    <th>默认代理</th>
                                    <th>状态</th>
                                    <th>到期时间</th>
                                    <th>创建时间</th>
                                    <th>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                <?php foreach ($domains as $domain): ?>
                                <?php 
                                    // 确保provider_type字段存在
                                    $provider_type = $domain['provider_type'] ?? 'cloudflare';
                                    $provider_configs = [
                                        'cloudflare' => ['name' => 'Cloudflare', 'class' => 'bg-info'],
                                        'rainbow' => ['name' => '彩虹DNS', 'class' => 'bg-warning'],
                                        'dnspod' => ['name' => 'DNSPod', 'class' => 'bg-success'],
                                        'powerdns' => ['name' => 'PowerDNS', 'class' => 'bg-primary'],
                                        'custom' => ['name' => '自定义', 'class' => 'bg-secondary']
                                    ];
                                    $provider_config = $provider_configs[$provider_type] ?? $provider_configs['cloudflare'];
                                    $provider_name = $provider_config['name'];
                                    $provider_class = $provider_config['class'];
                                ?>
                                <tr>
                                    <td><?php echo $domain['id']; ?></td>
                                    <td>
                                        <strong><?php echo htmlspecialchars($domain['domain_name']); ?></strong>
                                    </td>
                                    <td>
                                        <span class="badge <?php echo $provider_class; ?>"><?php echo $provider_name; ?></span>
                                    </td>
                                    <td><?php echo htmlspecialchars($domain['email']); ?></td>
                                    <td><code><?php echo htmlspecialchars($domain['zone_id']); ?></code></td>
                                    <td>
                                        <?php if ($provider_type === 'rainbow'): ?>
                                            <span class="badge bg-secondary">不支持</span>
                                        <?php elseif ($domain['proxied_default']): ?>
                                            <span class="badge bg-success">是</span>
                                        <?php else: ?>
                                            <span class="badge bg-secondary">否</span>
                                        <?php endif; ?>
                                    </td>
                                    <td>
                                        <?php if ($domain['status']): ?>
                                            <span class="badge bg-success">正常</span>
                                        <?php else: ?>
                                            <span class="badge bg-danger">禁用</span>
                                        <?php endif; ?>
                                    </td>
                                    <td>
                                        <span id="expiration-<?php echo $domain['id']; ?>">
                                            <?php if (!empty($domain['expiration_time'])): ?>
                                                <?php echo htmlspecialchars($domain['expiration_time']); ?>
                                            <?php else: ?>
                                                <span class="text-muted">未获取</span>
                                            <?php endif; ?>
                                        </span>
                                        <button type="button" 
                                                class="btn btn-sm btn-info ms-1" 
                                                onclick="fetchExpiration(<?php echo $domain['id']; ?>)"
                                                id="fetch-btn-<?php echo $domain['id']; ?>"
                                                title="获取到期时间">
                                            <i class="fas fa-sync-alt"></i>
                                        </button>
                                    </td>
                                    <td><?php echo formatTime($domain['created_at']); ?></td>
                                    <td>
                                        <a href="domain_dns.php?domain_id=<?php echo $domain['id']; ?>" 
                                           class="btn btn-sm btn-primary me-1" 
                                           title="管理DNS记录">
                                            <i class="fas fa-cog"></i>
                                        </a>
                                        <a href="?action=delete&id=<?php echo $domain['id']; ?>" 
                                           class="btn btn-sm btn-danger" 
                                           onclick="return confirmDomainDelete('<?php echo htmlspecialchars($domain['domain_name']); ?>', <?php echo $domain['id']; ?>)">
                                            <i class="fas fa-trash"></i>
                                        </a>
                                    </td>
                                </tr>
                                <?php endforeach; ?>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            <?php endif; ?>
            </div>
        </main>
    </div>
</div>


<!-- 手动添加域名模态框 -->
<div class="modal fade" id="addDomainModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">手动添加域名</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST">
                <div class="modal-body">
                    <div class="mb-3">
                        <label for="account_id" class="form-label">选择Cloudflare账户</label>
                        <select class="form-control" id="account_id" name="account_id" required>
                            <option value="">请选择账户</option>
                            <?php foreach ($cf_accounts as $account): ?>
                            <option value="<?php echo $account['id']; ?>">
                                <?php echo htmlspecialchars($account['name']); ?> (<?php echo htmlspecialchars($account['email']); ?>)
                            </option>
                            <?php endforeach; ?>
                        </select>
                    </div>
                    <div class="mb-3">
                        <label for="domain_name" class="form-label">域名</label>
                        <input type="text" class="form-control" id="domain_name" name="domain_name" placeholder="example.com" required>
                    </div>
                    <div class="mb-3">
                        <label for="zone_id" class="form-label">Zone ID</label>
                        <input type="text" class="form-control" id="zone_id" name="zone_id" required>
                    </div>
                    <div class="mb-3">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="domain_proxied_default" name="proxied_default" value="1" checked>
                            <label class="form-check-label" for="domain_proxied_default">
                                默认启用Cloudflare代理
                            </label>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="add_domain" class="btn btn-primary">添加域名</button>
                </div>
            </form>
        </div>
    </div>
</div>

<!-- 获取域名列表模态框 -->
<div class="modal fade" id="fetchDomainsModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">获取域名列表</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST">
                <div class="modal-body">
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i>
                        系统将从选择的Cloudflare账户获取所有域名，然后您可以选择要添加的域名。
                    </div>
                    <div class="mb-3">
                        <label for="fetch_account_id" class="form-label">选择Cloudflare账户</label>
                        <select class="form-control" id="fetch_account_id" name="account_id" required>
                            <option value="">请选择账户</option>
                            <?php foreach ($cf_accounts as $account): ?>
                            <option value="<?php echo $account['id']; ?>">
                                <?php echo htmlspecialchars($account['name']); ?> (<?php echo htmlspecialchars($account['email']); ?>)
                            </option>
                            <?php endforeach; ?>
                        </select>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="fetch_domains" class="btn btn-success">获取域名列表</button>
                </div>
            </form>
        </div>
    </div>
</div>


<!-- 获取彩虹DNS域名列表模态框 -->
<div class="modal fade" id="fetchRainbowDomainsModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">获取彩虹DNS域名列表</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST">
                <div class="modal-body">
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i>
                        系统将从选择的彩虹DNS账户获取域名列表，然后您可以选择要添加的域名。
                    </div>
                    <div class="mb-3">
                        <label for="fetch_rainbow_account_id" class="form-label">选择彩虹DNS账户</label>
                        <select class="form-control" id="fetch_rainbow_account_id" name="rainbow_account_id" required>
                            <option value="">请选择账户</option>
                            <?php 
                            // 获取彩虹DNS账户列表
                            $rainbow_accounts_result = $db->query("SELECT * FROM rainbow_accounts WHERE status = 1 ORDER BY name");
                            while ($rainbow_account = $rainbow_accounts_result->fetchArray(SQLITE3_ASSOC)): 
                            ?>
                            <option value="<?php echo $rainbow_account['id']; ?>">
                                <?php echo htmlspecialchars($rainbow_account['name']); ?> (<?php echo htmlspecialchars($rainbow_account['provider_uid']); ?>)
                            </option>
                            <?php endwhile; ?>
                        </select>
                        <div class="form-text">
                            如果没有可选账户，请先到 
                            <a href="channels_management.php" target="_blank">渠道管理</a> 
                            添加彩虹DNS账户
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="fetch_rainbow_domains_from_account" class="btn btn-warning">获取域名列表</button>
                </div>
            </form>
        </div>
    </div>
</div>

<!-- 获取DNSPod域名列表模态框 -->
<div class="modal fade" id="fetchDnspodDomainsModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">获取DNSPod域名列表</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST">
                <div class="modal-body">
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i>
                        系统将从选择的DNSPod账户获取域名列表，然后您可以选择要添加的域名。
                    </div>
                    <div class="mb-3">
                        <label for="fetch_dnspod_account_id" class="form-label">选择DNSPod账户</label>
                        <select class="form-control" id="fetch_dnspod_account_id" name="dnspod_account_id" required>
                            <option value="">请选择账户</option>
                            <?php 
                            // 获取DNSPod账户列表
                            $dnspod_accounts_result = $db->query("SELECT * FROM dnspod_accounts WHERE status = 1 ORDER BY name");
                            while ($dnspod_account = $dnspod_accounts_result->fetchArray(SQLITE3_ASSOC)): 
                            ?>
                            <option value="<?php echo $dnspod_account['id']; ?>">
                                <?php echo htmlspecialchars($dnspod_account['name']); ?> (<?php echo htmlspecialchars($dnspod_account['secret_id']); ?>)
                            </option>
                            <?php endwhile; ?>
                        </select>
                        <div class="form-text">
                            如果没有可选账户，请先到 
                            <a href="channels_management.php" target="_blank">渠道管理</a> 
                            添加DNSPod账户
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="fetch_dnspod_domains_from_account" class="btn btn-success">获取域名列表</button>
                </div>
            </form>
        </div>
    </div>
</div>

<!-- 获取PowerDNS域名列表模态框 -->
<div class="modal fade" id="fetchPowerdnsDomainsModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">获取PowerDNS域名列表</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST">
                <div class="modal-body">
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i>
                        系统将从选择的PowerDNS账户获取域名列表，然后您可以选择要添加的域名。
                    </div>
                    <div class="mb-3">
                        <label for="fetch_powerdns_account_id" class="form-label">选择PowerDNS账户</label>
                        <select class="form-control" id="fetch_powerdns_account_id" name="powerdns_account_id" required>
                            <option value="">请选择账户</option>
                            <?php 
                            // 获取PowerDNS账户列表
                            $powerdns_accounts_result = $db->query("SELECT * FROM powerdns_accounts WHERE status = 1 ORDER BY name");
                            while ($powerdns_account = $powerdns_accounts_result->fetchArray(SQLITE3_ASSOC)): 
                            ?>
                            <option value="<?php echo $powerdns_account['id']; ?>">
                                <?php echo htmlspecialchars($powerdns_account['name']); ?> (<?php echo htmlspecialchars($powerdns_account['api_url']); ?>)
                            </option>
                            <?php endwhile; ?>
                        </select>
                        <div class="form-text">
                            如果没有可选账户，请先到 
                            <a href="channels_management.php" target="_blank">渠道管理</a> 
                            添加PowerDNS账户
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="fetch_powerdns_domains_from_account" class="btn btn-primary">获取域名列表</button>
                </div>
            </form>
        </div>
    </div>
</div>

<script>
function confirmDelete(message) {
    return confirm(message);
}

function toggleAll(source) {
    const checkboxes = document.querySelectorAll('.domain-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = source.checked;
    });
}

function toggleAllRainbow(source) {
    const checkboxes = document.querySelectorAll('.rainbow-domain-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = source.checked;
    });
}

function validateSelection() {
    const checkboxes = document.querySelectorAll('.domain-checkbox:checked');
    if (checkboxes.length === 0) {
        alert('请至少选择一个域名进行添加！');
        return false;
    }
    return true;
}

function toggleAllRainbow(source) {
    const checkboxes = document.querySelectorAll('.rainbow-domain-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = source.checked;
    });
}

function validateRainbowSelection() {
    const checkboxes = document.querySelectorAll('.rainbow-domain-checkbox:checked');
    if (checkboxes.length === 0) {
        alert('请至少选择一个彩虹DNS域名进行添加！');
        return false;
    }
    return true;
}

function toggleAllDnspod(source) {
    const checkboxes = document.querySelectorAll('.dnspod-domain-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = source.checked;
    });
}

function validateDnspodSelection() {
    const checkboxes = document.querySelectorAll('.dnspod-domain-checkbox:checked');
    if (checkboxes.length === 0) {
        alert('请至少选择一个DNSPod域名进行添加！');
        return false;
    }
    return true;
}

function toggleAllPowerdns(source) {
    const checkboxes = document.querySelectorAll('.powerdns-domain-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = source.checked;
    });
}

function validatePowerdnsSelection() {
    const checkboxes = document.querySelectorAll('.powerdns-domain-checkbox:checked');
    if (checkboxes.length === 0) {
        alert('请至少选择一个PowerDNS域名进行添加！');
        return false;
    }
    return true;
}

function confirmDomainDelete(domainName, domainId) {
    // 获取DNS记录数量（通过AJAX）
    fetch('?action=get_dns_count&domain_id=' + domainId)
        .then(response => response.json())
        .then(data => {
            let message = `确定要删除域名 "${domainName}" 吗？\n\n`;
            message += `删除过程将包括：\n`;
            message += `1. 尝试从DNS提供商删除 ${data.record_count} 条DNS记录\n`;
            message += `2. 清除所有本地DNS记录\n`;
            message += `3. 删除域名配置\n\n`;
            message += `注意：\n`;
            message += `- 如果DNS提供商删除失败，本地记录仍会被清除\n`;
            message += `- 此操作不可恢复\n\n`;
            message += `是否继续？`;
            
            if (confirm(message)) {
                window.location.href = '?action=delete&id=' + domainId;
            }
        })
        .catch(error => {
            // 如果AJAX失败，使用简单确认
            if (confirm(`确定要删除域名 "${domainName}" 及其所有DNS记录吗？\n\n此操作不可恢复！`)) {
                window.location.href = '?action=delete&id=' + domainId;
            }
        });
    
    return false; // 阻止直接跳转
}

// 获取域名到期时间
function fetchExpiration(domainId) {
    const btn = document.getElementById('fetch-btn-' + domainId);
    const expirationSpan = document.getElementById('expiration-' + domainId);
    const originalBtnHtml = btn.innerHTML;
    
    // 禁用按钮并显示加载状态
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    
    // 发送AJAX请求
    fetch('domains.php', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: 'update_expiration=1&domain_id=' + domainId
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // 更新显示的到期时间
            if (data.expiration_time) {
                expirationSpan.innerHTML = data.expiration_time;
            } else {
                expirationSpan.innerHTML = '<span class="text-muted">永久域名</span>';
            }
            
            // 显示成功消息
            alert(data.message);
        } else {
            alert('错误: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('请求失败，请检查网络连接！');
    })
    .finally(() => {
        // 恢复按钮状态
        btn.disabled = false;
        btn.innerHTML = originalBtnHtml;
    });
}
</script>

<?php include 'includes/footer.php'; ?>