"""
代理服务集成示例
如果决定使用代理服务来绕过反爬虫系统，可以参考此文件
"""
import os
from playwright.async_api import async_playwright

# ============================================================================
# 方案 1: 使用环境变量配置代理
# ============================================================================

async def initialize_with_proxy_from_env(self, extension_path: str = None):
    """使用环境变量中的代理配置初始化浏览器"""
    
    # 从环境变量读取代理配置
    proxy_server = os.getenv('PROXY_SERVER')  # 例如: http://proxy.example.com:8080
    proxy_username = os.getenv('PROXY_USERNAME')
    proxy_password = os.getenv('PROXY_PASSWORD')
    
    # 构建代理配置
    proxy_config = None
    if proxy_server:
        proxy_config = {"server": proxy_server}
        if proxy_username and proxy_password:
            proxy_config["username"] = proxy_username
            proxy_config["password"] = proxy_password
        print(f"✓ 使用代理: {proxy_server}")
    else:
        print("⚠ 未配置代理，使用直连")
    
    # 创建浏览器上下文时应用代理
    self.context = await self.browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        locale="en-US",
        timezone_id="America/New_York",
        bypass_csp=True,
        ignore_https_errors=True,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        proxy=proxy_config,  # 应用代理配置
        # ... 其他配置保持不变
    )


# ============================================================================
# 方案 2: 使用代理轮换（多个代理）
# ============================================================================

class ProxyRotator:
    """代理轮换器"""
    
    def __init__(self, proxy_list: list):
        """
        初始化代理轮换器
        
        Args:
            proxy_list: 代理列表，格式:
                [
                    {"server": "http://proxy1.com:8080", "username": "user1", "password": "pass1"},
                    {"server": "http://proxy2.com:8080", "username": "user2", "password": "pass2"},
                ]
        """
        self.proxy_list = proxy_list
        self.current_index = 0
    
    def get_next_proxy(self):
        """获取下一个代理"""
        if not self.proxy_list:
            return None
        
        proxy = self.proxy_list[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxy_list)
        return proxy


# ============================================================================
# 方案 3: 使用 ScraperAPI（推荐给初学者）
# ============================================================================

# ScraperAPI 会自动处理代理轮换、验证码等
# 只需要将 URL 包装一下

def get_scraperapi_url(original_url: str, api_key: str) -> str:
    """
    将原始 URL 转换为 ScraperAPI URL
    
    Args:
        original_url: 原始网站 URL
        api_key: ScraperAPI 的 API Key
    
    Returns:
        ScraperAPI 代理 URL
    """
    import urllib.parse
    encoded_url = urllib.parse.quote(original_url)
    return f"http://api.scraperapi.com?api_key={api_key}&url={encoded_url}"

# 使用示例:
# api_key = os.getenv('SCRAPERAPI_KEY')
# proxy_url = get_scraperapi_url('https://www.emeraldfreight.com/', api_key)
# await page.goto(proxy_url)


# ============================================================================
# 方案 4: 使用 Bright Data (Luminati)
# ============================================================================

def get_brightdata_proxy_config(username: str, password: str, country: str = 'us'):
    """
    获取 Bright Data 代理配置
    
    Args:
        username: Bright Data 用户名
        password: Bright Data 密码
        country: 国家代码 (us, uk, de, etc.)
    
    Returns:
        代理配置字典
    """
    return {
        "server": f"http://brd.superproxy.io:22225",
        "username": f"{username}-country-{country}",
        "password": password
    }


# ============================================================================
# 在 Render 上配置环境变量
# ============================================================================

"""
在 Render Dashboard 中添加以下环境变量:

方案 1 - 简单代理:
- PROXY_SERVER=http://your-proxy.com:8080
- PROXY_USERNAME=your-username
- PROXY_PASSWORD=your-password

方案 2 - ScraperAPI:
- SCRAPERAPI_KEY=your-api-key
- USE_SCRAPERAPI=true

方案 3 - Bright Data:
- BRIGHTDATA_USERNAME=your-username
- BRIGHTDATA_PASSWORD=your-password
- BRIGHTDATA_COUNTRY=us
"""


# ============================================================================
# 成本估算
# ============================================================================

"""
代理服务成本参考 (2024年):

1. ScraperAPI:
   - Hobby: $49/月 (100,000 请求)
   - Startup: $149/月 (1,000,000 请求)
   - 适合: 中小规模爬虫

2. Bright Data:
   - Pay as you go: $500 起步
   - 按流量计费: ~$10/GB
   - 适合: 大规模专业爬虫

3. Smartproxy:
   - Micro: $50/月 (5GB)
   - Starter: $75/月 (10GB)
   - 适合: 性价比选择

4. Oxylabs:
   - Starter: $300/月
   - 适合: 企业级需求

建议:
- 如果每天处理 < 1000 个 URL: ScraperAPI Hobby ($49/月)
- 如果每天处理 1000-10000 个 URL: Smartproxy Starter ($75/月)
- 如果每天处理 > 10000 个 URL: Bright Data 或 Oxylabs
"""


# ============================================================================
# 免费/低成本替代方案
# ============================================================================

"""
1. 免费代理列表 (不推荐用于生产):
   - https://www.proxy-list.download/
   - https://free-proxy-list.net/
   - 问题: 不稳定、慢、可能不安全

2. 自建代理:
   - 在 AWS/DigitalOcean 上创建多个 VPS
   - 使用住宅 ISP (如 Comcast, AT&T)
   - 成本: ~$5-10/月 每个 VPS
   - 问题: 需要技术能力、管理复杂

3. 更换托管服务:
   - 尝试 Railway, Fly.io, Heroku
   - 可能有不同的 IP 段
   - 成本: 免费或 $5-20/月
   - 问题: 不保证有效
"""
