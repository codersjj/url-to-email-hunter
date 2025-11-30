"""
免费代理管理器
从免费代理列表中轮换使用代理
"""
import random
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class FreeProxyManager:
    """免费代理管理器"""
    
    # 免费代理列表（从 https://www.proxy-list.download/ 获取）
    # 格式: {"server": "http://ip:port"}
    FREE_PROXIES = [
        {"server": "http://38.252.213.67:999"},       # Peru
        {"server": "http://199.217.99.123:2525"},     # United States
        {"server": "http://195.158.8.123:3128"},      # Uzbekistan
        {"server": "http://35.209.198.222:80"},       # United States
        {"server": "http://156.38.112.11:80"},        # Ghana
        {"server": "http://185.99.70.146:8080"},      # Czech Republic
        {"server": "http://154.65.39.7:80"},          # Senegal
        {"server": "http://138.124.49.149:10808"},    # Sweden
        {"server": "http://35.197.89.213:80"},        # United States
        {"server": "http://162.240.19.30:80"},        # United States
        {"server": "http://210.223.44.230:3128"},     # South Korea
    ]
    
    def __init__(self, use_proxy: bool = True):
        """
        初始化代理管理器
        
        Args:
            use_proxy: 是否使用代理（False 则直连）
        """
        self.use_proxy = use_proxy
        self.current_index = 0
        self.failed_proxies = set()  # 记录失败的代理
        
        if use_proxy:
            logger.info(f"✓ 代理管理器已启用，共 {len(self.FREE_PROXIES)} 个代理")
        else:
            logger.info("⚠ 代理管理器已禁用，使用直连")
    
    def get_next_proxy(self) -> Optional[Dict]:
        """
        获取下一个可用代理
        
        Returns:
            代理配置字典，如果不使用代理则返回 None
        """
        if not self.use_proxy:
            return None
        
        # 过滤掉已失败的代理
        available_proxies = [
            p for p in self.FREE_PROXIES 
            if p["server"] not in self.failed_proxies
        ]
        
        if not available_proxies:
            logger.warning("所有代理都已失败，重置失败列表")
            self.failed_proxies.clear()
            available_proxies = self.FREE_PROXIES
        
        # 轮换选择
        proxy = available_proxies[self.current_index % len(available_proxies)]
        self.current_index += 1
        
        logger.debug(f"使用代理: {proxy['server']}")
        return proxy
    
    def get_random_proxy(self) -> Optional[Dict]:
        """
        随机获取一个可用代理
        
        Returns:
            代理配置字典，如果不使用代理则返回 None
        """
        if not self.use_proxy:
            return None
        
        # 过滤掉已失败的代理
        available_proxies = [
            p for p in self.FREE_PROXIES 
            if p["server"] not in self.failed_proxies
        ]
        
        if not available_proxies:
            logger.warning("所有代理都已失败，重置失败列表")
            self.failed_proxies.clear()
            available_proxies = self.FREE_PROXIES
        
        proxy = random.choice(available_proxies)
        logger.debug(f"随机选择代理: {proxy['server']}")
        return proxy
    
    def mark_proxy_failed(self, proxy_server: str):
        """
        标记代理为失败
        
        Args:
            proxy_server: 代理服务器地址，例如 "http://38.252.213.67:999"
        """
        self.failed_proxies.add(proxy_server)
        logger.warning(f"标记代理失败: {proxy_server} (已失败: {len(self.failed_proxies)}/{len(self.FREE_PROXIES)})")
    
    def reset_failed_proxies(self):
        """重置失败代理列表"""
        count = len(self.failed_proxies)
        self.failed_proxies.clear()
        logger.info(f"已重置 {count} 个失败代理")
    
    def get_stats(self) -> Dict:
        """
        获取代理统计信息
        
        Returns:
            统计信息字典
        """
        total = len(self.FREE_PROXIES)
        failed = len(self.failed_proxies)
        available = total - failed
        
        return {
            "total": total,
            "available": available,
            "failed": failed,
            "success_rate": f"{(available/total*100):.1f}%" if total > 0 else "0%"
        }


# 全局代理管理器实例
_proxy_manager = None

def get_proxy_manager(use_proxy: bool = True) -> FreeProxyManager:
    """
    获取全局代理管理器实例
    
    Args:
        use_proxy: 是否使用代理
    
    Returns:
        代理管理器实例
    """
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = FreeProxyManager(use_proxy=use_proxy)
    return _proxy_manager
