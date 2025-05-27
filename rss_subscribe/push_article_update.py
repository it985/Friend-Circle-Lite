import logging
import requests
import re
from friend_circle_lite.get_info import check_feed, parse_feed
import json
import os
import time
from typing import Dict, List, Optional, Any

# 标准化的请求头
HEADERS_JSON = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36 "
        "(Friend-Circle-Lite/1.0; +https://github.com/willow-god/Friend-Circle-Lite)"
    ),
    "X-Friend-Circle": "1.0"
}

# 缓存系统
class Cache:
    def __init__(self, cache_dir: str = "./rss_subscribe/cache", ttl: int = 3600):
        """
        初始化缓存系统
        
        :param cache_dir: 缓存目录
        :param ttl: 缓存生存时间（秒）
        """
        self.cache_dir = cache_dir
        self.ttl = ttl
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        
        # 确保缓存目录存在
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
    
    def _get_cache_path(self, key: str) -> str:
        """
        获取缓存文件路径
        
        :param key: 缓存键
        :return: 缓存文件路径
        """
        return os.path.join(self.cache_dir, f"{key}.json")
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存值
        
        :param key: 缓存键
        :return: 缓存值，如果不存在或已过期则返回 None
        """
        # 先检查内存缓存
        if key in self.memory_cache:
            cache_data = self.memory_cache[key]
            if time.time() - cache_data.get("timestamp", 0) < self.ttl:
                return cache_data.get("data")
        
        # 检查文件缓存
        cache_path = self._get_cache_path(key)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                if time.time() - cache_data.get("timestamp", 0) < self.ttl:
                    # 更新内存缓存
                    self.memory_cache[key] = cache_data
                    return cache_data.get("data")
            except (json.JSONDecodeError, IOError) as e:
                logging.warning(f"读取缓存文件失败: {e}")
        
        return None
    
    def set(self, key: str, data: Dict[str, Any]) -> None:
        """
        设置缓存值
        
        :param key: 缓存键
        :param data: 缓存数据
        """
        cache_data = {
            "timestamp": time.time(),
            "data": data
        }
        
        # 更新内存缓存
        self.memory_cache[key] = cache_data
        
        # 更新文件缓存
        try:
            with open(self._get_cache_path(key), 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logging.warning(f"写入缓存文件失败: {e}")

# 创建全局缓存实例
cache = Cache()

def extract_emails_from_issues(api_url):
    """
    从 GitHub issues API 中提取以 [e-mail] 开头的 title 中的邮箱地址。

    参数：
    api_url (str): GitHub issues API 的 URL。

    返回：
    dict: 包含所有提取的邮箱地址的字典。
    {
        "emails": [
            "3162475700@qq.com"
        ]
    }
    """
    # 检查缓存
    cache_key = f"emails_{api_url}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
    
    try:
        response = requests.get(api_url, headers=HEADERS_JSON, timeout=10)
        response.raise_for_status()
        issues = response.json()
    except Exception as e:
        logging.error(f"无法获取 GitHub issues 数据，错误信息：{e}")
        return None

    email_pattern = re.compile(r'^\[邮箱订阅\](.+)$')
    emails = []

    for issue in issues:
        title = issue.get("title", "")
        match = email_pattern.match(title)
        if match:
            email = match.group(1).strip()
            emails.append(email)
    
    result = {"emails": emails}
    
    # 更新缓存
    cache.set(cache_key, result)
    
    return result

def get_latest_articles_from_link(url, count=5, last_articles_path="./rss_subscribe/last_articles.json"):
    """
    从指定链接获取最新的文章数据并与本地存储的上次的文章数据进行对比。

    参数：
    url (str): 用于获取文章数据的链接。
    count (int): 获取文章数的最大数。如果小于则全部获取，如果文章数大于则只取前 count 篇文章。

    返回：
    list: 更新的文章列表，如果没有更新的文章则返回 None。
    """
    # 检查缓存
    cache_key = f"articles_{url}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data.get("updated_articles")
    
    # 检查和解析 feed
    session = requests.Session()
    feed_type, feed_url = check_feed(url, session)
    if feed_type == 'none':
        logging.error(f"无法获取 {url} 的文章数据")
        return None

    # 获取最新的文章数据
    latest_data = parse_feed(feed_url, session, count)
    latest_articles = latest_data['articles']
    
    # 读取本地存储的上次的文章数据
    if os.path.exists(last_articles_path):
        with open(last_articles_path, 'r', encoding='utf-8') as file:
            last_data = json.load(file)
    else:
        last_data = {'articles': []}
    
    last_articles = last_data['articles']

    # 找到更新的文章
    updated_articles = []
    last_titles = {article['link'] for article in last_articles}

    for article in latest_articles:
        if article['link'] not in last_titles:
            updated_articles.append(article)
    
    logging.info(f"从 {url} 获取到 {len(latest_articles)} 篇文章，其中 {len(updated_articles)} 篇为新文章")

    # 更新本地存储的文章数据
    with open(last_articles_path, 'w', encoding='utf-8') as file:
        json.dump({'articles': latest_articles}, file, ensure_ascii=False, indent=4)
    
    # 更新缓存
    cache.set(cache_key, {"updated_articles": updated_articles if updated_articles else None})
    
    # 如果有更新的文章，返回这些文章，否则返回 None
    return updated_articles if updated_articles else None

