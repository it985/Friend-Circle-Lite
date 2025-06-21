import logging
import feedparser
import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
from datetime import datetime
from dateutil import parser
from zoneinfo import ZoneInfo
from .security import SecurityManager

class BaseFeedParser:
    """Feed解析器基类"""
    
    def __init__(self):
        self.timeout = (10, 15)
    
    def parse(self, url: str, session, count: int = 5, blog_url: str = '') -> Dict[str, Any]:
        """解析feed的通用接口"""
        raise NotImplementedError
    
    def format_time(self, time_str: str) -> str:
        """格式化时间字符串"""
        if not time_str:
            return ''
        
        try:
            parsed_time = parser.parse(time_str, fuzzy=True)
        except (ValueError, parser.ParserError):
            # 扩展的时间格式支持
            time_formats = [
                '%a, %d %b %Y %H:%M:%S %z',  # Mon, 11 Mar 2024 14:08:32 +0000
                '%a, %d %b %Y %H:%M:%S GMT',   # Wed, 19 Jun 2024 09:43:53 GMT
                '%Y-%m-%dT%H:%M:%S%z',         # 2024-03-11T14:08:32+00:00
                '%Y-%m-%dT%H:%M:%SZ',          # 2024-03-11T14:08:32Z
                '%Y-%m-%d %H:%M:%S',           # 2024-03-11 14:08:32
                '%Y-%m-%d',                    # 2024-03-11
                '%d %b %Y %H:%M:%S',           # 11 Mar 2024 14:08:32
                '%Y年%m月%d日',                 # 2024年03月11日
                '%Y/%m/%d %H:%M:%S',           # 2024/03/11 14:08:32
                '%Y.%m.%d %H:%M:%S',           # 2024.03.11 14:08:32
            ]
            
            for fmt in time_formats:
                try:
                    parsed_time = datetime.strptime(time_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                logging.warning(f"无法解析时间字符串：{time_str}")
                return ''
        
        # 处理时区转换
        if parsed_time.tzinfo is None:
            parsed_time = parsed_time.replace(tzinfo=ZoneInfo("UTC"))
        
        shanghai_time = parsed_time.astimezone(ZoneInfo("Asia/Shanghai"))
        return shanghai_time.strftime('%Y-%m-%d %H:%M')
    
    def sanitize_content(self, content: str) -> str:
        """清理内容"""
        if not content:
            return ''
        
        # 移除HTML标签
        import re
        content = re.sub(r'<[^>]+>', '', content)
        
        # 清理多余空白
        content = re.sub(r'\s+', ' ', content).strip()
        
        return SecurityManager.sanitize_input(content)

class RSSParser(BaseFeedParser):
    """RSS格式解析器"""
    
    def parse(self, url: str, session, count: int = 5, blog_url: str = '') -> Dict[str, Any]:
        """解析RSS feed"""
        try:
            response = session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or 'utf-8'
            
            feed = feedparser.parse(response.text)
            
            result = {
                'website_name': self.sanitize_content(feed.feed.title if 'title' in feed.feed else ''),
                'author': self.sanitize_content(feed.feed.author if 'author' in feed.feed else ''),
                'link': feed.feed.link if 'link' in feed.feed else '',
                'articles': []
            }
            
            for entry in feed.entries:
                article = self._parse_entry(entry, blog_url)
                if article:
                    result['articles'].append(article)
            
            # 排序并限制数量
            result['articles'] = sorted(
                result['articles'],
                key=lambda x: datetime.strptime(x['published'], '%Y-%m-%d %H:%M') if x['published'] else datetime.min,
                reverse=True
            )[:count]
            
            return result
            
        except Exception as e:
            logging.error(f"解析RSS失败: {url}, 错误: {e}")
            return self._empty_result()
    
    def _parse_entry(self, entry, blog_url: str) -> Optional[Dict[str, Any]]:
        """解析单个条目"""
        try:
            # 时间处理
            published = ''
            if 'published' in entry:
                published = self.format_time(entry.published)
            elif 'updated' in entry:
                published = self.format_time(entry.updated)
            elif 'pubDate' in entry:
                published = self.format_time(entry.pubDate)
            
            if not published:
                logging.warning(f"文章 {entry.title} 未包含时间信息")
                published = datetime.now(ZoneInfo("Asia/Shanghai")).strftime('%Y-%m-%d %H:%M')
            
            # 链接处理
            article_link = entry.link if 'link' in entry else ''
            if article_link and blog_url:
                from .get_info import replace_non_domain
                article_link = replace_non_domain(article_link, blog_url)
            
            # 内容处理
            summary = ''
            if 'summary' in entry:
                summary = self.sanitize_content(entry.summary)
            elif 'description' in entry:
                summary = self.sanitize_content(entry.description)
            
            content = ''
            if 'content' in entry and entry.content:
                content = self.sanitize_content(entry.content[0].value)
            elif 'description' in entry:
                content = self.sanitize_content(entry.description)
            
            return {
                'title': self.sanitize_content(entry.title if 'title' in entry else ''),
                'author': self.sanitize_content(entry.author if 'author' in entry else ''),
                'link': article_link,
                'published': published,
                'summary': summary,
                'content': content
            }
            
        except Exception as e:
            logging.error(f"解析条目失败: {e}")
            return None
    
    def _empty_result(self) -> Dict[str, Any]:
        return {
            'website_name': '',
            'author': '',
            'link': '',
            'articles': []
        }

class JSONFeedParser(BaseFeedParser):
    """JSON Feed格式解析器"""
    
    def parse(self, url: str, session, count: int = 5, blog_url: str = '') -> Dict[str, Any]:
        """解析JSON Feed"""
        try:
            response = session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            feed_data = response.json()
            
            result = {
                'website_name': self.sanitize_content(feed_data.get('title', '')),
                'author': self.sanitize_content(feed_data.get('author', {}).get('name', '')),
                'link': feed_data.get('home_page_url', ''),
                'articles': []
            }
            
            items = feed_data.get('items', [])
            for item in items[:count]:
                article = self._parse_json_item(item, blog_url)
                if article:
                    result['articles'].append(article)
            
            return result
            
        except Exception as e:
            logging.error(f"解析JSON Feed失败: {url}, 错误: {e}")
            return self._empty_result()
    
    def _parse_json_item(self, item: Dict[str, Any], blog_url: str) -> Optional[Dict[str, Any]]:
        """解析JSON Feed条目"""
        try:
            # 时间处理
            published = ''
            if 'date_published' in item:
                published = self.format_time(item['date_published'])
            elif 'date_modified' in item:
                published = self.format_time(item['date_modified'])
            
            if not published:
                published = datetime.now(ZoneInfo("Asia/Shanghai")).strftime('%Y-%m-%d %H:%M')
            
            # 链接处理
            article_link = item.get('url', '')
            if article_link and blog_url:
                from .get_info import replace_non_domain
                article_link = replace_non_domain(article_link, blog_url)
            
            # 内容处理
            summary = ''
            if 'summary' in item:
                summary = self.sanitize_content(item['summary'])
            elif 'content_text' in item:
                summary = self.sanitize_content(item['content_text'])
            
            content = ''
            if 'content_html' in item:
                content = self.sanitize_content(item['content_html'])
            elif 'content_text' in item:
                content = self.sanitize_content(item['content_text'])
            
            return {
                'title': self.sanitize_content(item.get('title', '')),
                'author': self.sanitize_content(item.get('authors', [{}])[0].get('name', '') if item.get('authors') else ''),
                'link': article_link,
                'published': published,
                'summary': summary,
                'content': content
            }
            
        except Exception as e:
            logging.error(f"解析JSON Feed条目失败: {e}")
            return None
    
    def _empty_result(self) -> Dict[str, Any]:
        return {
            'website_name': '',
            'author': '',
            'link': '',
            'articles': []
        }

class FeedParserFactory:
    """Feed解析器工厂"""
    
    @staticmethod
    def get_parser(feed_type: str) -> BaseFeedParser:
        """根据feed类型获取对应的解析器"""
        if feed_type == 'json_feed':
            return JSONFeedParser()
        else:
            return RSSParser()  # RSS和Atom都使用RSSParser 