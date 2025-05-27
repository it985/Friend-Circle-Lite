# 引入 check_feed 和 parse_feed 函数
from friend_circle_lite.get_info import fetch_and_process_data, sort_articles_by_time, marge_data_from_json_url, marge_errors_from_json_url, deal_with_large_data
from friend_circle_lite.get_conf import load_config
from rss_subscribe.push_article_update import get_latest_articles_from_link, extract_emails_from_issues
from push_rss_update.send_email import send_emails

import logging
import json
import sys
import os
import argparse
from typing import Dict, Any, Tuple, Optional

# 日志记录
logging.basicConfig(level=logging.INFO, format='😋 %(levelname)s: %(message)s')

def load_and_validate_config(config_path: str = "./conf.yaml") -> Dict[str, Any]:
    """
    加载并验证配置文件
    
    :param config_path: 配置文件路径
    :return: 配置字典
    """
    try:
        config = load_config(config_path)
        # 验证必要的配置项
        required_sections = ["spider_settings", "email_push", "rss_subscribe", "smtp"]
        for section in required_sections:
            if section not in config:
                logging.error(f"配置文件缺少必要的部分: {section}")
                sys.exit(1)
        return config
    except Exception as e:
        logging.error(f"加载配置文件失败: {e}")
        sys.exit(1)

def run_spider(config: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    运行爬虫功能
    
    :param config: 配置字典
    :return: 爬取结果和丢失的友链
    """
    if not config["spider_settings"]["enable"]:
        logging.info("爬虫功能未启用")
        return {}, {}
    
    logging.info("爬虫已启用")
    json_url = config['spider_settings']['json_url']
    article_count = config['spider_settings']['article_count']
    specific_RSS = config['specific_RSS']
    logging.info("正在从 {json_url} 中获取，每个博客获取 {article_count} 篇文章".format(json_url=json_url, article_count=article_count))
    
    result, lost_friends = fetch_and_process_data(json_url=json_url, specific_RSS=specific_RSS, count=article_count)
    
    if config["spider_settings"]["merge_result"]["enable"]:
        marge_json_url = config['spider_settings']["merge_result"]['merge_json_url']
        logging.info("合并数据功能开启，从 {marge_json_url} 中获取境外数据并合并".format(marge_json_url=marge_json_url + "/all.json"))
        result = marge_data_from_json_url(result, marge_json_url + "/all.json")
        lost_friends = marge_errors_from_json_url(lost_friends, marge_json_url + "/errors.json")
    
    logging.info("数据获取完毕，目前共有 {count} 位好友的动态，正在处理数据".format(count=len(result.get("article_data", []))))
    result = deal_with_large_data(result)
    
    # 保存结果到文件
    with open("all.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    with open("errors.json", "w", encoding="utf-8") as f:
        json.dump(lost_friends, f, ensure_ascii=False, indent=2)
    
    return result, lost_friends

def run_email_push(config: Dict[str, Any]) -> None:
    """
    运行邮件推送功能
    
    :param config: 配置字典
    """
    if not config["email_push"]["enable"]:
        logging.info("邮件推送功能未启用")
        return
    
    logging.info("邮件推送已启用")
    logging.info("抱歉，目前暂未实现功能")

def run_rss_subscribe(config: Dict[str, Any]) -> None:
    """
    运行 RSS 订阅功能
    
    :param config: 配置字典
    """
    if not config["rss_subscribe"]["enable"]:
        logging.info("RSS 订阅功能未启用")
        return
    
    logging.info("RSS 订阅推送已启用")
    
    # 获取 GitHub 信息
    fcl_repo = os.getenv('FCL_REPO')
    if fcl_repo:
        github_username, github_repo = fcl_repo.split('/')
    else:
        github_username = str(config["rss_subscribe"]["github_username"]).strip()
        github_repo = str(config["rss_subscribe"]["github_repo"]).strip()
    
    logging.info("github_username: {github_username}".format(github_username=github_username))
    logging.info("github_repo: {github_repo}".format(github_repo=github_repo))
    
    # 获取博客信息
    your_blog_url = config["rss_subscribe"]["your_blog_url"]
    email_template = config["rss_subscribe"]["email_template"]
    website_title = config["rss_subscribe"]["website_info"]["title"]
    
    # 获取最新文章
    latest_articles = get_latest_articles_from_link(
        url=your_blog_url,
        count=5,
        last_articles_path="./rss_subscribe/last_articles.json"
    )
    
    if latest_articles is None:
        logging.info("无未进行推送的新文章")
        return
    
    logging.info("获取到的最新文章为：{latest_articles}".format(latest_articles=latest_articles))
    
    # 获取订阅邮箱
    github_api_url = f"https://api.github.com/repos/{github_username}/{github_repo}/issues?state=closed&label=subscribed&per_page=200"
    logging.info("正在从 {github_api_url} 中获取订阅信息".format(github_api_url=github_api_url))
    
    email_list = extract_emails_from_issues(github_api_url)
    if email_list is None:
        logging.info("无邮箱列表，请检查您的订阅列表是否有订阅者或订阅格式是否正确")
        return
    
    logging.info("获取到的邮箱列表为：{email_list}".format(email_list=email_list))
    
    # 获取 SMTP 配置
    email_settings = config["smtp"]
    email = email_settings["email"]
    server = email_settings["server"]
    port = email_settings["port"]
    use_tls = email_settings["use_tls"]
    password = os.getenv("SMTP_PWD")
    
    if not password:
        logging.error("SMTP 密码未配置，无法发送邮件")
        return
    
    # 发送邮件
    for article in latest_articles:
        template_data = {
            "title": article["title"],
            "summary": article["summary"],
            "published": article["published"],
            "link": article["link"],
            "website_title": website_title,
            "github_issue_url": f"https://github.com/{github_username}/{github_repo}/issues?q=is%3Aissue+is%3Aclosed",
        }
        
        send_emails(
            emails=email_list["emails"],
            sender_email=email,
            smtp_server=server,
            port=port,
            password=password,
            subject=website_title + "の最新文章：" + article["title"],
            body="文章链接：" + article["link"] + "\n" + "文章内容：" + article["summary"] + "\n" + "发布时间：" + article["published"],
            template_path=email_template,
            template_data=template_data,
            use_tls=use_tls
        )

def main():
    """
    主函数
    """
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Friend-Circle-Lite 运行脚本')
    parser.add_argument('--config', type=str, default='./conf.yaml', help='配置文件路径')
    parser.add_argument('--spider-only', action='store_true', help='仅运行爬虫功能')
    parser.add_argument('--email-only', action='store_true', help='仅运行邮件推送功能')
    parser.add_argument('--rss-only', action='store_true', help='仅运行 RSS 订阅功能')
    args = parser.parse_args()
    
    # 加载配置
    config = load_and_validate_config(args.config)
    
    # 根据命令行参数决定运行哪些功能
    if args.spider_only:
        run_spider(config)
    elif args.email_only:
        run_email_push(config)
    elif args.rss_only:
        run_rss_subscribe(config)
    else:
        # 运行所有功能
        run_spider(config)
        run_email_push(config)
        run_rss_subscribe(config)

if __name__ == "__main__":
    main()
