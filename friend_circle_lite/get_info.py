import logging
from datetime import datetime, timedelta, timezone
import re
from urllib.parse import urljoin, urlparse
from dateutil import parser
from zoneinfo import ZoneInfo
import requests
import feedparser
from concurrent.futures import ThreadPoolExecutor, as_completed
from .config_validator import ConfigValidator
from .security import SecurityManager
from .retry_utils import RetryManager
from .performance import PerformanceManager
from .rss_detector import RSSDetector
from .feed_parsers import FeedParserFactory

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

HEADERS_XML = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36 "
        "(Friend-Circle-Lite/1.0; +https://github.com/willow-god/Friend-Circle-Lite)"
    ),
    "Accept": "application/atom+xml, application/rss+xml, application/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "X-Friend-Circle": "1.0"
}

timeout = (10, 15) # 连接超时和读取超时，防止requests接受时间过长

def format_published_time(time_str):
    """
    格式化发布时间为统一格式 YYYY-MM-DD HH:MM

    参数:
    time_str (str): 输入的时间字符串，可能是多种格式。

    返回:
    str: 格式化后的时间字符串，若解析失败返回空字符串。
    """
    # 尝试自动解析输入时间字符串
    try:
        parsed_time = parser.parse(time_str, fuzzy=True)
    except (ValueError, parser.ParserError):
        # 定义支持的时间格式
        time_formats = [
            '%a, %d %b %Y %H:%M:%S %z',  # Mon, 11 Mar 2024 14:08:32 +0000
            '%a, %d %b %Y %H:%M:%S GMT',   # Wed, 19 Jun 2024 09:43:53 GMT
            '%Y-%m-%dT%H:%M:%S%z',         # 2024-03-11T14:08:32+00:00
            '%Y-%m-%dT%H:%M:%SZ',          # 2024-03-11T14:08:32Z
            '%Y-%m-%d %H:%M:%S',           # 2024-03-11 14:08:32
            '%Y-%m-%d'                     # 2024-03-11
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
        parsed_time = parsed_time.replace(tzinfo=timezone.utc)
    shanghai_time = parsed_time.astimezone(timezone(timedelta(hours=8)))
    return shanghai_time.strftime('%Y-%m-%d %H:%M')

def replace_non_domain(link: str, blog_url: str) -> str:
    """
    检测并替换字符串中的非正常域名部分（如 IP 地址或 localhost），替换为 blog_url。
    替换后强制使用 https，且考虑 blog_url 尾部是否有斜杠。

    :param link: 原始地址字符串
    :param blog_url: 替换为的博客地址
    :return: 替换后的地址字符串
    """
    if not link or not blog_url:
        return link
    
    try:
        parsed = urlparse(link)
        if SecurityManager._is_local_address(parsed.netloc):
            # 提取 path + query
            path = parsed.path or '/'
            if parsed.query:
                path += '?' + parsed.query
            return urljoin(blog_url.rstrip('/') + '/', path.lstrip('/'))
        else:
            return link  # 合法域名则返回原链接
    except Exception as e:
        logging.warning(f"替换链接时出错：{link}, error: {e}")
        return link

@RetryManager.retry_on_failure(max_retries=2, delay=1.0)
def check_feed(blog_url, session):
    """
    检查博客的 RSS 或 Atom 订阅链接。
    使用增强的RSS检测器
    """
    detector = RSSDetector(session)
    feed_type, feed_url = detector.detect_feed(blog_url)
    return [feed_type, feed_url]

def parse_feed(url, session, count=5, blog_url=''):
    """
    解析各种格式的feed
    """
    if not SecurityManager.validate_url(url):
        logging.error(f"不安全的feed URL: {url}")
        return {
            'website_name': '',
            'author': '',
            'link': '',
            'articles': []
        }
    
    # 检测feed类型
    detector = RSSDetector(session)
    feed_type = detector._detect_feed_type(url)
    
    # 获取对应的解析器
    parser = FeedParserFactory.get_parser(feed_type)
    
    # 解析feed
    result = parser.parse(url, session, count, blog_url)
    
    return result

def process_friend(friend, session, count, specific_RSS=[]):
    """
    处理单个朋友的博客信息。

    参数：
    friend (list): 包含朋友信息的列表 [name, blog_url, avatar]。
    session (requests.Session): 用于请求的会话对象。
    count (int): 获取每个博客的最大文章数。
    specific_RSS (list): 包含特定 RSS 源的字典列表 [{name, url}]

    返回：
    dict: 包含朋友博客信息的字典。
    """
    name, blog_url, avatar = friend
    
    # 如果 specific_RSS 中有对应的 name，则直接返回 feed_url
    if specific_RSS is None:
        specific_RSS = []
    rss_feed = next((rss['url'] for rss in specific_RSS if rss['name'] == name), None)
    if rss_feed:
        feed_url = rss_feed
        feed_type = 'specific'
        logging.info(f"“{name}”的博客“ {blog_url} ”为特定RSS源“ {feed_url} ”")
    else:
        feed_type, feed_url = check_feed(blog_url, session)
        logging.info(f"“{name}”的博客“ {blog_url} ”的feed类型为“{feed_type}”, feed地址为“ {feed_url} ”")

    if feed_type != 'none':
        feed_info = parse_feed(feed_url, session, count, blog_url)
        articles = [
            {
                'title': article['title'],
                'created': article['published'],
                'link': article['link'],
                'author': name,
                'avatar': avatar
            }
            for article in feed_info['articles']
        ]
        
        for article in articles:
            logging.info(f"{name} 发布了新文章：{article['title']}，时间：{article['created']}，链接：{article['link']}")
        
        return {
            'name': name,
            'status': 'active',
            'articles': articles
        }
    else:
        logging.warning(f"{name} 的博客 {blog_url} 无法访问")
        return {
            'name': name,
            'status': 'error',
            'articles': []
        }

def fetch_and_process_data(json_url, specific_RSS=[], count=5):
    """
    读取 JSON 数据并处理订阅信息，返回统计数据和文章信息。

    参数：
    json_url (str): 包含朋友信息的 JSON 文件的 URL。
    count (int): 获取每个博客的最大文章数。
    specific_RSS (list): 包含特定 RSS 源的字典列表 [{name, url}]

    返回：
    dict: 包含统计数据和文章信息的字典。
    """
    session = requests.Session()
    
    try:
        response = session.get(json_url, headers=HEADERS_JSON, timeout=timeout)
        friends_data = response.json()
    except Exception as e:
        logging.error(f"无法获取链接：{json_url} ：{e}", exc_info=True)
        return None

    total_friends = len(friends_data['friends'])
    active_friends = 0
    error_friends = 0
    total_articles = 0
    article_data = []
    error_friends_info = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_friend = {
            executor.submit(process_friend, friend, session, count, specific_RSS): friend
            for friend in friends_data['friends']
        }
        
        for future in as_completed(future_to_friend):
            friend = future_to_friend[future]
            try:
                result = future.result()
                if result['status'] == 'active':
                    active_friends += 1
                    article_data.extend(result['articles'])
                    total_articles += len(result['articles'])
                else:
                    error_friends += 1
                    error_friends_info.append(friend)
            except Exception as e:
                logging.error(f"处理 {friend} 时发生错误: {e}", exc_info=True)
                error_friends += 1
                error_friends_info.append(friend)

    result = {
        'statistical_data': {
            'friends_num': total_friends,
            'active_num': active_friends,
            'error_num': error_friends,
            'article_num': total_articles,
            'last_updated_time': datetime.now(ZoneInfo("Asia/Shanghai")).strftime('%Y-%m-%d %H:%M:%S')
        },
        'article_data': article_data
    }
    
    logging.info(f"数据处理完成，总共有 {total_friends} 位朋友，其中 {active_friends} 位博客可访问，{error_friends} 位博客无法访问")

    return result, error_friends_info

def sort_articles_by_time(data):
    """
    对文章数据按时间排序

    参数：
    data (dict): 包含文章信息的字典

    返回：
    dict: 按时间排序后的文章信息字典
    """
    # 先确保每个元素存在时间
    for article in data['article_data']:
        if article['created'] == '' or article['created'] == None:
            article['created'] = '2024-01-01 00:00'
            # 输出警告信息
            logging.warning(f"文章 {article['title']} 未包含时间信息，已设置为默认时间 2024-01-01 00:00")
    
    if 'article_data' in data:
        sorted_articles = sorted(
            data['article_data'],
            key=lambda x: datetime.strptime(x['created'], '%Y-%m-%d %H:%M'),
            reverse=True
        )
        data['article_data'] = sorted_articles
    return data

def marge_data_from_json_url(data, marge_json_url):
    """
    从另一个 JSON 文件中获取数据并合并到原数据中。

    参数：
    data (dict): 包含文章信息的字典
    marge_json_url (str): 包含另一个文章信息的 JSON 文件的 URL。

    返回：
    dict: 合并后的文章信息字典，已去重处理
    """
    try:
        response = requests.get(marge_json_url, headers=HEADERS_JSON, timeout=timeout)
        marge_data = response.json()
    except Exception as e:
        logging.error(f"无法获取链接：{marge_json_url}，出现的问题为：{e}", exc_info=True)
        return data
    
    if 'article_data' in marge_data:
        logging.info(f"开始合并数据，原数据共有 {len(data['article_data'])} 篇文章，第三方数据共有 {len(marge_data['article_data'])} 篇文章")
        data['article_data'].extend(marge_data['article_data'])
        data['article_data'] = list({v['link']:v for v in data['article_data']}.values())
        logging.info(f"合并数据完成，现在共有 {len(data['article_data'])} 篇文章")
    return data

import requests

def marge_errors_from_json_url(errors, marge_json_url):
    """
    从另一个网络 JSON 文件中获取错误信息并遍历，删除在errors中，
    不存在于marge_errors中的友链信息。

    参数：
    errors (list): 包含错误信息的列表
    marge_json_url (str): 包含另一个错误信息的 JSON 文件的 URL。

    返回：
    list: 合并后的错误信息列表
    """
    try:
        response = requests.get(marge_json_url, timeout=10)  # 设置请求超时时间
        marge_errors = response.json()
    except Exception as e:
        logging.error(f"无法获取链接：{marge_json_url}，出现的问题为：{e}", exc_info=True)
        return errors

    # 提取 marge_errors 中的 URL
    marge_urls = {item[1] for item in marge_errors}

    # 使用过滤器保留 errors 中在 marge_errors 中出现的 URL
    filtered_errors = [error for error in errors if error[1] in marge_urls]

    logging.info(f"合并错误信息完成，合并后共有 {len(filtered_errors)} 位朋友")
    return filtered_errors

def deal_with_large_data(result):
    """
    处理文章数据，保留前150篇及其作者在后续文章中的出现。
    
    参数：
    result (dict): 包含统计数据和文章数据的字典。
    
    返回：
    dict: 处理后的数据，只包含需要的文章。
    """
    result = sort_articles_by_time(result)
    article_data = result.get("article_data", [])

    # 检查文章数量是否大于 150
    max_articles = 150
    if len(article_data) > max_articles:
        logging.info("数据量较大，开始进行处理...")
        # 获取前 max_articles 篇文章的作者集合
        top_authors = {article["author"] for article in article_data[:max_articles]}

        # 从第 {max_articles + 1} 篇开始过滤，只保留前 max_articles 篇出现过的作者的文章
        filtered_articles = article_data[:max_articles] + [
            article for article in article_data[max_articles:]
            if article["author"] in top_authors
        ]

        # 更新结果中的 article_data
        result["article_data"] = filtered_articles
        # 更新结果中的统计数据
        result["statistical_data"]["article_num"] = len(filtered_articles)
        logging.info(f"数据处理完成，保留 {len(filtered_articles)} 篇文章")

    return result