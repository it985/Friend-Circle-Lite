import logging
import re
from typing import List, Optional
from urllib.parse import urlparse

class SecurityManager:
    """安全管理器"""
    
    # 允许的域名白名单（可根据需要配置）
    ALLOWED_DOMAINS = [
        'github.com',
        'githubusercontent.com',
        'jsdelivr.net',
        'unpkg.com'
    ]
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """验证URL安全性"""
        try:
            parsed = urlparse(url)
            
            # 检查协议
            if parsed.scheme not in ['http', 'https']:
                logging.warning(f"不安全的协议: {url}")
                return False
                
            # 检查是否为本地地址
            if SecurityManager._is_local_address(parsed.netloc):
                logging.warning(f"本地地址不允许: {url}")
                return False
                
            # 检查域名白名单（可选）
            # if not SecurityManager._is_allowed_domain(parsed.netloc):
            #     logging.warning(f"域名不在白名单中: {url}")
            #     return False
                
            return True
            
        except Exception as e:
            logging.error(f"URL验证失败: {url}, 错误: {e}")
            return False
    
    @staticmethod
    def _is_local_address(netloc: str) -> bool:
        """检查是否为本地地址"""
        local_patterns = [
            r'^localhost$',
            r'^127\.\d+\.\d+\.\d+$',
            r'^10\.\d+\.\d+\.\d+$',
            r'^172\.(1[6-9]|2[0-9]|3[0-1])\.\d+\.\d+$',
            r'^192\.168\.\d+\.\d+$'
        ]
        
        for pattern in local_patterns:
            if re.match(pattern, netloc):
                return True
        return False
    
    @staticmethod
    def _is_allowed_domain(netloc: str) -> bool:
        """检查域名是否在白名单中"""
        for domain in SecurityManager.ALLOWED_DOMAINS:
            if netloc.endswith(domain):
                return True
        return False
    
    @staticmethod
    def sanitize_input(input_str: str) -> str:
        """清理用户输入"""
        if not input_str:
            return ""
        
        # 移除潜在的XSS字符
        dangerous_chars = ['<', '>', '"', "'", '&']
        for char in dangerous_chars:
            input_str = input_str.replace(char, '')
            
        return input_str.strip() 