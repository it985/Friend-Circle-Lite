import logging
import re
import requests
from typing import List, Tuple, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import json
from .security import SecurityManager
from .retry_utils import RetryManager

class RSSDetector:
    """增强的RSS检测器，支持多种RSS格式和智能发现"""
    
    # 扩展的RSS路径列表
    RSS_PATHS = [
        # WordPress相关
        ('wordpress_atom', '/feed/'),
        ('wordpress_rss', '/rss/'),
        ('wordpress_rdf', '/rdf/'),
        ('wordpress_atom_alt', '/atom/'),
        ('wordpress_comments', '/comments/feed/'),
        
        # 通用RSS格式
        ('atom', '/atom.xml'),
        ('rss', '/rss.xml'),
        ('rss2', '/rss2.xml'),
        ('rss3', '/rss.php'),
        ('feed', '/feed'),
        ('feed2', '/feed.xml'),
        ('feed3', '/feed/'),
        ('index', '/index.xml'),
        
        # Hexo相关
        ('hexo_atom', '/atom.xml'),
        ('hexo_rss2', '/rss2.xml'),
        ('hexo_rss', '/rss.xml'),
        
        # Hugo相关
        ('hugo_index', '/index.xml'),
        ('hugo_rss', '/rss.xml'),
        ('hugo_feed', '/feed.xml'),
        
        # Jekyll相关
        ('jekyll_feed', '/feed.xml'),
        ('jekyll_atom', '/atom.xml'),
        ('jekyll_rss', '/rss.xml'),
        
        # 博客子目录
        ('blog_feed', '/blog/feed/'),
        ('posts_feed', '/posts/feed/'),
        ('articles_feed', '/articles/feed/'),
        ('news_feed', '/news/feed/'),
        
        # JSON Feed格式
        ('json_feed', '/feed.json'),
        ('json_index', '/index.json'),
        
        # 自定义API
        ('api_feed', '/api/feed'),
        ('api_posts', '/api/posts'),
        ('api_articles', '/api/articles'),
        
        # 备选方案
        ('sitemap', '/sitemap.xml'),
    ]
    
    # 支持的Content-Type
    SUPPORTED_CONTENT_TYPES = [
        'application/atom+xml',
        'application/rss+xml',
        'application/xml',
        'text/xml',
        'application/json',
        'text/json',
        'application/feed+json',
    ]
    
    def __init__(self, session: requests.Session, timeout: Tuple[int, int] = (10, 15)):
        self.session = session
        self.timeout = timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36 "
                "(Friend-Circle-Lite/1.0; +https://github.com/willow-god/Friend-Circle-Lite)"
            ),
            "Accept": "application/atom+xml, application/rss+xml, application/xml, application/feed+json, application/json, text/xml;q=0.9, */*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "X-Friend-Circle": "1.0"
        }
    
    @RetryManager.retry_on_failure(max_retries=2, delay=1.0)
    def detect_feed(self, blog_url: str, custom_paths: List[str] = None) -> Tuple[str, str]:
        """
        智能检测博客的RSS feed
        
        Args:
            blog_url: 博客URL
            custom_paths: 自定义RSS路径列表
            
        Returns:
            Tuple[str, str]: (feed_type, feed_url)
        """
        if not SecurityManager.validate_url(blog_url):
            logging.warning(f"不安全的URL: {blog_url}")
            return ('none', blog_url)
        
        # 1. 首先尝试从HTML页面发现feed链接
        feed_url = self._discover_feed_from_html(blog_url)
        if feed_url:
            feed_type = self._detect_feed_type(feed_url)
            if feed_type != 'none':
                logging.info(f"从HTML页面发现feed: {feed_type} - {feed_url}")
                return (feed_type, feed_url)
        
        # 2. 尝试预定义的RSS路径
        all_paths = self.RSS_PATHS.copy()
        if custom_paths:
            all_paths.extend([(f'custom_{i}', path) for i, path in enumerate(custom_paths)])
        
        for feed_type, path in all_paths:
            feed_url = blog_url.rstrip('/') + path
            if self._is_valid_feed(feed_url):
                logging.info(f"发现有效feed: {feed_type} - {feed_url}")
                return (feed_type, feed_url)
        
        logging.warning(f"无法找到 {blog_url} 的订阅链接")
        return ('none', blog_url)
    
    def _discover_feed_from_html(self, blog_url: str) -> Optional[str]:
        """从HTML页面中自动发现feed链接"""
        try:
            response = self.session.get(blog_url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找link标签中的feed信息
            feed_links = soup.find_all('link', {
                'type': ['application/atom+xml', 'application/rss+xml', 'application/feed+json', 'application/json']
            })
            
            for link in feed_links:
                href = link.get('href')
                if href:
                    feed_url = urljoin(blog_url, href)
                    if self._is_valid_feed(feed_url):
                        return feed_url
            
            # 查找rel属性包含feed的链接
            feed_links = soup.find_all('link', rel=lambda x: x and 'feed' in x.lower())
            for link in feed_links:
                href = link.get('href')
                if href:
                    feed_url = urljoin(blog_url, href)
                    if self._is_valid_feed(feed_url):
                        return feed_url
            
            # 查找alternate类型的feed链接
            alternate_links = soup.find_all('link', rel='alternate')
            for link in alternate_links:
                link_type = link.get('type', '')
                if any(feed_type in link_type for feed_type in ['atom', 'rss', 'json']):
                    href = link.get('href')
                    if href:
                        feed_url = urljoin(blog_url, href)
                        if self._is_valid_feed(feed_url):
                            return feed_url
            
            return None
            
        except Exception as e:
            logging.debug(f"从HTML页面发现feed失败: {blog_url}, 错误: {e}")
            return None
    
    def _is_valid_feed(self, feed_url: str) -> bool:
        """检查URL是否为有效的feed"""
        try:
            response = self.session.head(feed_url, headers=self.headers, timeout=self.timeout)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                return any(supported_type in content_type for supported_type in self.SUPPORTED_CONTENT_TYPES)
            return False
        except Exception:
            return False
    
    def _detect_feed_type(self, feed_url: str) -> str:
        """检测feed的类型"""
        try:
            response = self.session.head(feed_url, headers=self.headers, timeout=self.timeout)
            content_type = response.headers.get('content-type', '').lower()
            
            if 'application/feed+json' in content_type or 'application/json' in content_type:
                return 'json_feed'
            elif 'application/atom+xml' in content_type:
                return 'atom'
            elif 'application/rss+xml' in content_type or 'text/xml' in content_type:
                return 'rss'
            else:
                # 根据URL路径推测类型
                if feed_url.endswith('.json'):
                    return 'json_feed'
                elif 'atom' in feed_url:
                    return 'atom'
                elif 'rss' in feed_url:
                    return 'rss'
                else:
                    return 'unknown'
        except Exception:
            return 'unknown'
    
    def get_feed_info(self, feed_url: str) -> Dict[str, Any]:
        """获取feed的基本信息"""
        try:
            response = self.session.get(feed_url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            
            return {
                'url': feed_url,
                'content_type': response.headers.get('content-type', ''),
                'content_length': response.headers.get('content-length', ''),
                'last_modified': response.headers.get('last-modified', ''),
                'etag': response.headers.get('etag', ''),
            }
        except Exception as e:
            logging.error(f"获取feed信息失败: {feed_url}, 错误: {e}")
            return {} 