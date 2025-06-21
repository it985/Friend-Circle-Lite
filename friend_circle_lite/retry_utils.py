import time
import logging
from typing import Callable, Any, Optional
from functools import wraps

class RetryManager:
    """重试管理器"""
    
    @staticmethod
    def retry_on_failure(max_retries: int = 3, 
                        delay: float = 1.0,
                        backoff_factor: float = 2.0,
                        exceptions: tuple = (Exception,)):
        """重试装饰器"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                last_exception = None
                current_delay = delay
                
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        if attempt < max_retries:
                            logging.warning(f"第 {attempt + 1} 次尝试失败: {e}, "
                                          f"{current_delay}秒后重试...")
                            time.sleep(current_delay)
                            current_delay *= backoff_factor
                        else:
                            logging.error(f"所有重试都失败了: {e}")
                            raise last_exception
                            
            return wrapper
        return decorator
    
    @staticmethod
    def retry_request(session, url: str, **kwargs) -> Optional[Any]:
        """带重试的请求"""
        @RetryManager.retry_on_failure(max_retries=3, delay=1.0)
        def make_request():
            response = session.get(url, **kwargs)
            response.raise_for_status()
            return response
            
        try:
            return make_request()
        except Exception as e:
            logging.error(f"请求失败: {url}, 错误: {e}")
            return None 