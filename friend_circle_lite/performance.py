import logging
import psutil
import gc
from typing import Dict, List, Any
from functools import lru_cache

class PerformanceManager:
    """性能管理器"""
    
    @staticmethod
    def check_memory_usage() -> Dict[str, Any]:
        """检查内存使用情况"""
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            'rss': memory_info.rss,  # 物理内存
            'vms': memory_info.vms,  # 虚拟内存
            'percent': process.memory_percent()
        }
    
    @staticmethod
    def optimize_memory(data: List[Dict[str, Any]], 
                       max_articles: int = 150) -> List[Dict[str, Any]]:
        """优化内存使用"""
        if len(data) <= max_articles:
            return data
            
        logging.info(f"数据量过大({len(data)}篇)，开始优化...")
        
        # 按时间排序并只保留最新的文章
        sorted_data = sorted(data, 
                           key=lambda x: x.get('created', ''), 
                           reverse=True)
        
        optimized_data = sorted_data[:max_articles]
        
        # 强制垃圾回收
        gc.collect()
        
        logging.info(f"内存优化完成，保留 {len(optimized_data)} 篇文章")
        return optimized_data
    
    @staticmethod
    @lru_cache(maxsize=128)
    def get_cached_data(key: str) -> Any:
        """获取缓存数据"""
        # 这里可以实现更复杂的缓存逻辑
        pass
    
    @staticmethod
    def clear_cache():
        """清理缓存"""
        get_cached_data.cache_clear()
        gc.collect() 