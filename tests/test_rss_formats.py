import unittest
import requests
from friend_circle_lite.rss_detector import RSSDetector
from friend_circle_lite.feed_parsers import RSSParser, JSONFeedParser, FeedParserFactory

class TestRSSFormats(unittest.TestCase):
    
    def setUp(self):
        self.session = requests.Session()
        self.detector = RSSDetector(self.session)
    
    def test_rss_detection(self):
        """测试RSS检测功能"""
        # 测试常见的RSS路径
        test_urls = [
            "https://example.com",
            "https://blog.example.com",
            "https://wordpress.example.com",
        ]
        
        for url in test_urls:
            feed_type, feed_url = self.detector.detect_feed(url)
            print(f"URL: {url} -> Type: {feed_type}, URL: {feed_url}")
    
    def test_feed_parsing(self):
        """测试feed解析功能"""
        # 测试RSS解析
        rss_parser = RSSParser()
        # 这里可以添加实际的RSS URL进行测试
        
        # 测试JSON Feed解析
        json_parser = JSONFeedParser()
        # 这里可以添加实际的JSON Feed URL进行测试
    
    def test_parser_factory(self):
        """测试解析器工厂"""
        rss_parser = FeedParserFactory.get_parser('rss')
        atom_parser = FeedParserFactory.get_parser('atom')
        json_parser = FeedParserFactory.get_parser('json_feed')
        
        self.assertIsInstance(rss_parser, RSSParser)
        self.assertIsInstance(atom_parser, RSSParser)
        self.assertIsInstance(json_parser, JSONFeedParser)

if __name__ == '__main__':
    unittest.main() 