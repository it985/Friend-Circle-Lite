import yaml
import logging
from typing import Dict, Any, Optional
import os

class ConfigValidator:
    """配置验证器"""
    
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> bool:
        """验证配置文件格式和内容"""
        try:
            # 验证爬虫设置
            if not ConfigValidator._validate_spider_settings(config.get('spider_settings', {})):
                return False
                
            # 验证邮件设置
            if not ConfigValidator._validate_email_settings(config.get('email_push', {}), 
                                                          config.get('rss_subscribe', {}),
                                                          config.get('smtp', {})):
                return False
                
            # 验证特定RSS设置
            if not ConfigValidator._validate_specific_rss(config.get('specific_RSS', [])):
                return False
                
            return True
            
        except Exception as e:
            logging.error(f"配置验证失败: {e}")
            return False
    
    @staticmethod
    def _validate_spider_settings(settings: Dict[str, Any]) -> bool:
        """验证爬虫设置"""
        required_fields = ['enable', 'json_url', 'article_count']
        for field in required_fields:
            if field not in settings:
                logging.error(f"缺少必需的爬虫配置字段: {field}")
                return False
        
        if not isinstance(settings['enable'], bool):
            logging.error("spider_settings.enable 必须是布尔值")
            return False
            
        if not isinstance(settings['article_count'], int) or settings['article_count'] <= 0:
            logging.error("spider_settings.article_count 必须是正整数")
            return False
            
        return True
    
    @staticmethod
    def _validate_email_settings(email_push: Dict[str, Any], 
                                rss_subscribe: Dict[str, Any],
                                smtp: Dict[str, Any]) -> bool:
        """验证邮件设置"""
        # 如果启用了邮件功能，验证SMTP配置
        if email_push.get('enable') or rss_subscribe.get('enable'):
            required_smtp_fields = ['email', 'server', 'port', 'use_tls']
            for field in required_smtp_fields:
                if field not in smtp:
                    logging.error(f"缺少必需的SMTP配置字段: {field}")
                    return False
                    
            if not isinstance(smtp['port'], int) or smtp['port'] <= 0:
                logging.error("smtp.port 必须是正整数")
                return False
                
        return True
    
    @staticmethod
    def _validate_specific_rss(specific_rss: list) -> bool:
        """验证特定RSS配置"""
        if not isinstance(specific_rss, list):
            logging.error("specific_RSS 必须是列表")
            return False
            
        for rss in specific_rss:
            if not isinstance(rss, dict):
                logging.error("specific_RSS 中的每个元素必须是字典")
                return False
                
            if 'name' not in rss or 'url' not in rss:
                logging.error("specific_RSS 中的每个元素必须包含 name 和 url 字段")
                return False
                
        return True 