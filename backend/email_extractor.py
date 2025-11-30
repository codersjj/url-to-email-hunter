from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import asyncio
import logging
import re
from typing import List, Set, Optional
import os
import platform
from playwright_stealth import Stealth
import time
from free_proxy_manager import get_proxy_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailExtractor:
    FAKE_EMAIL_PREFIXES = [
        "the", "2", "3", "4", "123", "20info", "aaa", "ab", "abc", "acc", 
        "acc_kaz", "account", "accounts", "accueil", "ad", "adi", "adm", 
        "an", "and", "available", "cc", "com", "domain", "domen", 
        "email", "fb", "foi", "for", "found", "get", "here", 
        "includes", "linkedin", "mailbox", "more", "my_name", "name", 
        "need", "nfo", "ninfo", "now", "online", "post", "sales2", 
        "test", "up", "we", "www", "xxx", "xxxxx", "username", 
        "firstname.lastname", "your.name", "unsubscribe"
    ]
    
    
    def __init__(self, headless: bool = False, use_proxy: bool = False):
        self.headless = headless
        self.use_proxy_fallback = use_proxy  # 改名：失败时才使用代理
        self.proxy_manager = get_proxy_manager(use_proxy=use_proxy) if use_proxy else None
        self.current_proxy = None
        self.playwright_instance = None
        self.browser = None
        self.context = None
        self.paused = False
        self.stopped = False
        self._pages = []  # 跟踪所有打开的页面
        self._failed_urls_needing_proxy = set()  # 记录需要代理的URL
    
    def _extract_emails_from_text(self, text: str, domain: str = None) -> Set[str]:
        """Extract and filter emails from text"""
        if not text:
            return set()
        
        text = text.replace('\\n', ' ')
        pattern = r'\b[a-z\d\-][_a-z\d\-+]*(?:\.[_a-z\d\-+]*)*@[a-z\d]+[a-z\d\-]*(?:\.[a-z\d\-]+)*(?:\.[a-z]{2,63})\b'
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        if not matches:
            return set()
        
        valid_emails = set()
        filtered_count = 0
        
        for email in matches:
            email = email.lower().strip()
            
            if email in valid_emails:
                continue
            
            if domain and domain not in email:
                logger.debug(f"过滤邮箱 (域名不匹配): {email}")
                filtered_count += 1
                continue
            
            if email.endswith(('.png', '.jpg', '.gif', '.css', '.webp', '.crx1', '.js')):
                logger.debug(f"过滤邮箱 (文件后缀): {email}")
                filtered_count += 1
                continue
            
            original = email
            email = re.sub(r'^(x3|x2|u003|u0022|sx_mrsp_|3a)', '', email, flags=re.IGNORECASE)
            
            if email != original and not re.search(pattern, email, re.IGNORECASE):
                logger.debug(f"过滤邮箱 (清理后无效): {original}")
                filtered_count += 1
                continue
            
            if re.search(r'(no|not)[-|_]*reply|mailer[-|_]*daemon|reply.+\d{5,}', email, re.IGNORECASE):
                logger.debug(f"过滤邮箱 (spam模式): {email}")
                filtered_count += 1
                continue
            
            if re.search(r'\d{13,}', email):
                logger.debug(f"过滤邮箱 (过多数字): {email}")
                filtered_count += 1
                continue
            
            spam_keywords = ['nondelivery', '@linkedin.com', '@sentry', '@linkedhelper.com', 'feedback', 'notification']
            if any(keyword in email for keyword in spam_keywords):
                logger.debug(f"过滤邮箱 (垃圾关键词): {email}")
                filtered_count += 1
                continue
            
            email_prefix = email.split('@')[0]
            if email_prefix in self.FAKE_EMAIL_PREFIXES:
                logger.info(f"过滤邮箱 (假前缀): {email}")
                filtered_count += 1
                continue
            
            if email:
                logger.info(f"✓ 有效邮箱: {email}")
                valid_emails.add(email)
        
        if filtered_count > 0:
            logger.info(f"过滤 {filtered_count} 个,保留 {len(valid_emails)} 个有效邮箱")
        
        return valid_emails

    async def _create_context(self, use_proxy: bool = False):
        """创建并配置一个新的浏览器上下文"""
        # 获取代理配置
        proxy_config = None
        if use_proxy and self.proxy_manager:
            proxy = self.proxy_manager.get_random_proxy()
            if proxy:
                proxy_config = proxy
                logger.info(f"✓ 使用代理: {proxy_config['server']}")
            else:
                logger.warning("⚠ 代理管理器未返回代理，使用直连")
        
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            locale="en-US",
            timezone_id="America/New_York",
            bypass_csp=True,
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            permissions=['geolocation'],
            proxy=proxy_config,
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "none",
                "sec-fetch-user": "?1",
                "upgrade-insecure-requests": "1",
            },
        )

        # logger.info("应用 Stealth 插件...")
        await Stealth().apply_stealth_async(context)

        # 额外的 JavaScript 反检测
        # logger.info("注入额外的反检测脚本...")
        await context.add_init_script("""
            // 覆盖 webdriver 属性
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // 覆盖 chrome 对象
            window.chrome = {
                runtime: {}
            };
            
            // 覆盖 permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // 覆盖 plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // 覆盖 languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        """)
        
        return context

    async def initialize(self, extension_path: str = None, use_proxy: bool = False):
        """初始化浏览器"""
        try:
            logger.info("开始初始化 Playwright...")
            self.playwright_instance = await async_playwright().start()
            
            args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-blink-features=AutomationControlled',
                '--no-first-run',
                '--no-zygote',
                '--disable-infobars',
                '--start-maximized',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-site-isolation-trials',
                '--disable-features=BlockInsecurePrivateNetworkRequests',
            ]

            logger.info(f"启动浏览器 (headless={self.headless})...")
            self.browser = await self.playwright_instance.chromium.launch(
                headless=self.headless,
                args=args,
            )

            logger.info("创建主浏览器上下文...")
            self.context = await self._create_context(use_proxy=use_proxy)

            # 验证启动
            test_page = await self.context.new_page()
            await test_page.close()
            
            logger.info(f"浏览器初始化成功 (headless={self.headless})")
            return self
            
        except Exception as e:
            logger.error(f"初始化失败: {e}", exc_info=True)
            await self.close()
            raise

            # 验证启动
            test_page = await self.context.new_page()
            await test_page.close()
            
            logger.info(f"浏览器初始化成功 (headless={self.headless})")
            return self
            
        except Exception as e:
            logger.error(f"初始化失败: {e}", exc_info=True)
            await self.close()
            raise
           # 错误分类辅助方法
    def _categorize_error(self, error_str: str) -> tuple:
        """分类错误类型并返回 (错误类型, 是否可重试, 建议延迟秒数)"""
        error_lower = error_str.lower()
        
        # 网络连接错误 - 可重试
        if any(keyword in error_lower for keyword in [
            'err_socket_not_connected', 'err_connection_refused', 
            'err_connection_reset', 'err_connection_closed',
            'connection refused', 'socket', 'network'
        ]):
            return ('NETWORK_ERROR', True, 3)
        
        # 超时错误 - 可重试
        if any(keyword in error_lower for keyword in [
            'timeout', 'timed out', 'err_timed_out'
        ]):
            return ('TIMEOUT_ERROR', True, 2)
        
        # DNS错误 - 可重试
        if any(keyword in error_lower for keyword in [
            'dns', 'err_name_not_resolved', 'getaddrinfo failed'
        ]):
            return ('DNS_ERROR', True, 5)
        
        # CAPTCHA/反爬虫 - 需要代理
        if any(keyword in error_lower for keyword in [
            'captcha', 'robot', 'challenge', 'cloudflare'
        ]):
            return ('ANTI_SCRAPING', True, 1)
        
        # 服务器错误 - 可重试
        if any(keyword in error_lower for keyword in [
            '500', '502', '503', '504', 'server error'
        ]):
            return ('SERVER_ERROR', True, 5)
        
        # 客户端错误 - 不可重试
        if any(keyword in error_lower for keyword in [
            '400', '401', '403', '404', '405'
        ]):
            return ('CLIENT_ERROR', False, 0)
        
        # 未知错误 - 谨慎重试
        return ('UNKNOWN_ERROR', True, 2)
    
    # 查找英文链接
    async def _find_english_link(self, page) -> str:
        """查找英文链接"""
        try:
            english_url = await page.evaluate("""() => {
                const links = Array.from(document.querySelectorAll('a'));
                for (const link of links) {
                    const text = link.innerText.trim().toLowerCase();
                    const href = link.href.toLowerCase();
                    const title = (link.title || '').toLowerCase();
                    const ariaLabel = (link.getAttribute('aria-label') || '').toLowerCase();
                    
                    if (text === 'english' || text === 'en' || text.includes('english version')) {
                        return link.href;
                    }
                    
                    if (title.includes('english') || ariaLabel.includes('english')) {
                        return link.href;
                    }
                    
                    if ((href.includes('/en/') || href.endsWith('/en')) && !window.location.href.includes('/en/')) {
                        return link.href;
                    }
                }
                return null;
            }""")
            
            return english_url
        except Exception as e:
            logger.warning(f"查找英文链接出错: {str(e)}")
            return None

    async def _extract_from_page(self, page, retry_if_empty: bool = True) -> Set[str]:
        """从当前页面提取邮箱"""
        try:
            ready_state = await page.evaluate('document.readyState')
            logger.debug(f"页面状态: {ready_state}")
            
            page_html = await page.content()
            page_text = await page.inner_text('body')
            
            logger.debug(f"HTML长度: {len(page_html)}, 文本长度: {len(page_text)}")
            
            emails_from_html = self._extract_emails_from_text(page_html)
            emails_from_text = self._extract_emails_from_text(page_text)
            
            all_emails = emails_from_html.union(emails_from_text)
            
            # 如果第一次没找到邮箱，等待一下再试一次（可能是动态加载）
            if len(all_emails) == 0 and retry_if_empty:
                logger.debug("首次未找到邮箱，等待2秒后重试...")
                await asyncio.sleep(2)
                
                # 重新获取内容
                page_html = await page.content()
                page_text = await page.inner_text('body')
                
                emails_from_html = self._extract_emails_from_text(page_html)
                emails_from_text = self._extract_emails_from_text(page_text)
                
                all_emails = emails_from_html.union(emails_from_text)
                if len(all_emails) > 0:
                    logger.info(f"重试后找到 {len(all_emails)} 个邮箱")
            
            logger.info(f"本次提取找到 {len(all_emails)} 个邮箱")
            
            return all_emails
        except Exception as e:
            logger.error(f"页面提取失败: {str(e)}", exc_info=True)
            return set()
    
    # 从单个URL提取邮箱,返回详细结果
    async def extract_from_url(self, url: str, callback=None, max_attempts: int = 3, context=None) -> dict:
        """从单个URL提取邮箱，返回详细结果"""
        emails = set()
        visited_urls = set()
        page = None
        error_message = None
        error_type = None
        success = False
        last_error = None
        
        # 使用传入的 context 或默认 context
        current_context = context or self.context
        
        # 获取重试超时倍数
        retry_timeout_multiplier = float(os.getenv("RETRY_TIMEOUT_MULTIPLIER", "1.5"))

        for attempt in range(max_attempts):
            try:
                # 检查是否停止
                if self.stopped:
                    logger.info("检测到停止信号,终止提取")
                    return {
                        'url': url,
                        'emails': list(emails),
                        'count': len(emails),
                        'success': False,
                        'error': '用户停止',
                        'error_type': 'STOPPED',
                        'attempts': attempt + 1
                    }
                
                # 检查浏览器上下文是否有效
                if not current_context:
                    logger.error("浏览器上下文不存在,无法继续")
                    return {
                        'url': url,
                        'emails': list(emails),
                        'count': 0,
                        'success': False,
                        'error': '浏览器上下文不存在',
                        'error_type': 'BROWSER_CONTEXT_MISSING',
                        'attempts': attempt + 1
                    }
                
                # 显示当前尝试次数
                attempt_msg = f"第 {attempt + 1}/{max_attempts} 次尝试"
                if attempt > 0:
                    attempt_msg = f"重试中 ({attempt_msg})"
                logger.info(f"正在访问: {url} ({attempt_msg})")
                
                page = await current_context.new_page()
                self._pages.append(page)
                
                # 获取超时设置,默认为 60000ms (60秒)
                # 在 Render 等慢速环境中,较长的超时时间可以减少因网络波动导致的失败
                base_timeout = int(os.getenv("PAGE_TIMEOUT", "60000"))
                # 重试时增加超时时间
                page_timeout = int(base_timeout * (retry_timeout_multiplier ** attempt))
                logger.info(f"设置页面超时: {page_timeout}ms (尝试 {attempt + 1}/{max_attempts})")
                page.set_default_timeout(page_timeout)

                # 添加随机延迟
                await asyncio.sleep(0.5 + (hash(url) % 10) / 10)

                # 访问页面 - 使用更宽松的等待策略
                # 移除 asyncio.wait_for,直接使用 Playwright 的 timeout,避免 Future exception was never retrieved 错误
                await page.goto(url, wait_until='domcontentloaded', timeout=page_timeout)
                
                visited_urls.add(url)
                
                # 等待网络空闲 - 确保动态内容加载完成
                try:
                    logger.debug(f"等待网络空闲...")
                    await page.wait_for_load_state('networkidle', timeout=10000)
                    logger.debug(f"网络已空闲")
                except Exception as e:
                    logger.debug(f"网络空闲等待超时(这是正常的): {str(e)}")
                
                # 增加等待时间,让 JavaScript 有足够时间渲染内容
                # 在生产环境中,资源受限可能导致 JS 执行较慢,但 3秒可能太长
                await asyncio.sleep(1)


                if callback:
                    await callback('log', f"📄 页面加载完成: {url}", 'success')
                
                # 记录页面信息用于调试并检测验证码
                try:
                    page_title = await page.title()
                    page_url = page.url
                    logger.info(f"页面标题: {page_title}")
                    logger.info(f"最终URL: {page_url}")
                    
                    # 检测是否被重定向到验证码/机器人检测页面
                    captcha_indicators = [
                        'captcha', 'robot', 'challenge', 'verification',
                        'security check', 'are you human', 'prove you',
                        'sgcaptcha', 'cloudflare', 'recaptcha'
                    ]
                    
                    page_title_lower = page_title.lower()
                    page_url_lower = page_url.lower()
                    
                    is_captcha = any(
                        indicator in page_title_lower or indicator in page_url_lower
                        for indicator in captcha_indicators
                    )
                    
                    if is_captcha:
                        error_message = f"网站启用了反爬虫验证 (CAPTCHA/Robot Challenge)"
                        error_type = 'ANTI_SCRAPING'
                        logger.warning(f"❌ {url} - {error_message}")
                        logger.warning(f"   检测到: 标题='{page_title}', URL包含验证码路径")
                        
                        # 如果启用了代理回退且这是第一次尝试，触发重试
                        if self.use_proxy_fallback and attempt == 0:
                            logger.info(f"🔄 将使用代理重试: {url}")
                            if callback:
                                await callback('log', f"🔄 检测到CAPTCHA，将使用代理重试...", 'warning')
                            # 抛出异常触发重试
                            raise Exception("CAPTCHA_DETECTED_RETRY_WITH_PROXY")
                        else:
                            # 已经用过代理或未启用代理回退，直接失败
                            if callback:
                                await callback('log', f"⚠️ {url} - 被反爬虫系统拦截", 'warning')
                            
                            return {
                                'url': url,
                                'emails': [],
                                'count': 0,
                                'success': False,
                                'error': error_message,
                                'error_type': error_type,
                                'attempts': attempt + 1
                            }
                    
                except Exception as e:
                    logger.debug(f"获取页面信息失败: {e}")

                # 提取邮箱
                current_emails = await self._extract_from_page(page)
                emails.update(current_emails)

                if current_emails and callback:
                    await callback('log', f"📧 从当前页面提取到 {len(current_emails)} 个邮箱", 'success')
                    await callback('email', list(emails))

                # 尝试英文版
                if not self.stopped:
                    english_url = await self._find_english_link(page)
                    if english_url and english_url not in visited_urls and '/en/' not in url:
                        if callback:
                            await callback('log', f"🌐 发现英文版页面,正在跳转...", 'info')
                        try:
                            # 英文版页面跳转超时设为主要超时的一半，但至少 10秒
                            # 注意：这里重新获取 page_timeout 是为了安全，虽然上面已经获取过了，但为了保持局部变量清晰
                            page_timeout = int(os.getenv("PAGE_TIMEOUT", "60000"))
                            english_timeout = max(10000, page_timeout // 2)
                            await page.goto(english_url, wait_until='domcontentloaded', timeout=english_timeout)
                            visited_urls.add(english_url)
                            await asyncio.sleep(2)
                            
                            english_page_emails = await self._extract_from_page(page)
                            new_emails = english_page_emails - emails
                            if new_emails:
                                emails.update(new_emails)
                                if callback:
                                    await callback('log', f"📧 从英文版额外提取到 {len(new_emails)} 个邮箱", 'success')
                                    await callback('email', list(emails))
                        except Exception as e:
                            logger.warning(f"访问英文版失败: {str(e)}")

                # 成功
                success = True
                if attempt > 0 and callback:
                    await callback('log', f"✅ 重试成功 (第 {attempt + 1} 次尝试)", 'success')
                # No break here, the finally block will handle the return on success
            except PlaywrightTimeout as e:
                error_message = f"页面加载超时: {str(e)}"
                last_error = error_message
                error_type, should_retry, retry_delay = self._categorize_error(error_message)
                
                logger.warning(f"⏱️ [{error_type}] {url} - {error_message}")
                logger.info(f"   错误分类: {error_type}, 可重试: {should_retry}, 建议延迟: {retry_delay}秒")
                
                if callback:
                    await callback('log', f"⏱️ {url[:50]}... - 超时 (尝试 {attempt + 1}/{max_attempts})", 'warning')
                
                # 如果还有重试机会且错误可重试
                if attempt < max_attempts - 1 and should_retry:
                    logger.info(f"🔄 将在 {retry_delay} 秒后重试...")
                    if callback:
                        await callback('log', f"🔄 等待 {retry_delay}秒后重试...", 'info')
                    await asyncio.sleep(retry_delay)
                
            except Exception as e:
                error_message = str(e)
                last_error = error_message
                error_type, should_retry, retry_delay = self._categorize_error(error_message)
                
                logger.error(f"❌ [{error_type}] {url} - {error_message}")
                logger.info(f"   错误详情: 类型={error_type}, 可重试={should_retry}, 建议延迟={retry_delay}秒")
                logger.info(f"   当前尝试: {attempt + 1}/{max_attempts}")
                
                if callback:
                    await callback('log', f"❌ 错误: {url[:50]}... - {error_type} (尝试 {attempt + 1}/{max_attempts})", 'error')
                
                # 如果是 CAPTCHA 触发的代理重试
                if "CAPTCHA_DETECTED_RETRY_WITH_PROXY" in error_message and attempt == 0:
                    logger.info(f"🔄 检测到CAPTCHA，准备使用代理重试...")
                    
                    # 创建临时代理上下文
                    proxy_context = None
                    try:
                        proxy_context = await self._create_context(use_proxy=True)
                        logger.info(f"✓ 已创建临时代理上下文，重新尝试...")
                        if callback:
                            await callback('log', f"✓ 已切换到代理模式，重新尝试...", 'info')
                        
                        # 递归调用，使用新的上下文
                        # 注意：这里我们只重试一次 (max_attempts=1)，或者根据需要调整
                        retry_result = await self.extract_from_url(url, callback, max_attempts=max_attempts, context=proxy_context)
                        return retry_result
                        
                    except Exception as retry_error:
                        logger.error(f"使用代理重试失败: {retry_error}")
                        error_message = f"代理重试失败: {str(retry_error)}"
                        error_type = 'PROXY_RETRY_FAILED'
                        break # 代理重试失败，直接跳出
                    finally:
                        # 确保关闭临时上下文
                        if proxy_context:
                            try:
                                await proxy_context.close()
                            except:
                                pass
                
                # 如果还有重试机会且错误可重试
                if attempt < max_attempts - 1 and should_retry:
                    logger.info(f"🔄 将在 {retry_delay} 秒后重试...")
                    if callback:
                        await callback('log', f"🔄 [{error_type}] 等待 {retry_delay}秒后重试...", 'info')
                    await asyncio.sleep(retry_delay)
                elif not should_retry:
                    logger.warning(f"⚠️ 错误类型 {error_type} 不建议重试，跳过剩余尝试")
                    if callback:
                        await callback('log', f"⚠️ {error_type} - 不可重试，跳过", 'warning')
                    break
            
            finally:
                # 关闭页面
                if page:
                    try:
                        await page.close()
                        if page in self._pages:
                            self._pages.remove(page)
                    except:
                        pass
                
                # 如果成功提取到邮箱，立即返回
                if success:
                    logger.info(f"✅ 成功从 {url} 提取到 {len(emails)} 个邮箱 (尝试 {attempt + 1}/{max_attempts})")
                    return {
                        'url': url,
                        'emails': list(emails),
                        'count': len(emails),
                        'success': True,
                        'error': None,
                        'error_type': None,
                        'attempts': attempt + 1
                    }
    
        # 所有尝试都失败了
        final_error = last_error or error_message or '未知错误'
        logger.warning(f"❌ [{error_type or 'UNKNOWN'}] {url} - 所有 {max_attempts} 次尝试均失败")
        logger.warning(f"   最终错误: {final_error}")
        
        if callback:
            await callback('log', f"❌ {url[:50]}... - 失败 [{error_type or 'UNKNOWN'}]: {final_error[:50]}", 'error')
        
        return {
            'url': url,
            'emails': list(emails),
            'count': len(emails),
            'success': False,
            'error': final_error,
            'error_type': error_type or 'UNKNOWN',
            'attempts': max_attempts
        }
    
    async def extract_from_urls(self, urls: List[str], callback=None) -> dict:
        """批量提取邮箱，返回详细统计信息 (并行版)"""
        all_emails = set()
        total = len(urls)
        failed_urls = []
        no_email_urls = []
        
        # 线程安全的锁
        results_lock = asyncio.Lock()
        
        logger.info(f"开始批量提取 {total} 个URL (并行)")
        
        start_time = time.time()
        
        # 限制并发数 - 从环境变量获取，默认为 3 (适合 Render 等容器环境)
        max_concurrency = int(os.getenv("MAX_CONCURRENCY", "3"))
        logger.info(f"并发限制: {max_concurrency}")
        sem = asyncio.Semaphore(max_concurrency)
        
        # 进度计数器
        completed_count = 0
        progress_lock = asyncio.Lock()
        
        async def process_url(index, url):
            nonlocal completed_count
            
            async with sem:
                # 检查暂停/停止
                while self.paused and not self.stopped:
                    await asyncio.sleep(0.5)
                
                if self.stopped:
                    return
                
                logger.info(f"📊 开始处理: {url}")
                if callback:
                    await callback('log', f"🔍 正在处理: {url[:50]}...", 'info')
                
                try:
                    result = await self.extract_from_url(url, callback)
                    
                    async with results_lock:
                        # 更新总邮箱列表
                        all_emails.update(result['emails'])
                        
                        # 跟踪失败和无邮箱的URL
                        if not result['success']:
                            failed_urls.append({
                                'url': url,
                                'error': result['error'] or '未知错误',
                                'timestamp': time.time()
                            })
                        elif result['count'] == 0:
                            no_email_urls.append({
                                'url': url,
                                'timestamp': time.time()
                            })
                except Exception as e:
                    logger.error(f"处理 {url} 时出错: {e}")
                    async with results_lock:
                        failed_urls.append({
                            'url': url,
                            'error': str(e),
                            'timestamp': time.time()
                        })
                    if callback:
                        await callback('log', f"❌ 跳过 {url}: {str(e)}", 'error')
                finally:
                    # 更新进度
                    async with progress_lock:
                        completed_count += 1
                        current_progress = int(completed_count / total * 100)
                    
                    if callback:
                        await callback('progress', current_progress)
                
        # 创建任务列表
        tasks = [process_url(i, url) for i, url in enumerate(urls)]
        
        # 运行所有任务
        await asyncio.gather(*tasks)
        
        # 发送统计信息
        if callback:
            await callback('failed_urls', failed_urls)
            await callback('no_email_urls', no_email_urls)
        
        end_time = time.time()
        duration = end_time - start_time
        duration_str = f"{duration:.2f}秒"
        
        if callback and not self.stopped:
            await callback('log', f"✅ 提取完成!共 {len(all_emails)} 个唯一邮箱", 'success')
            await callback('log', f"📊 统计: 成功 {total - len(failed_urls)} 个, 失败 {len(failed_urls)} 个, 无邮箱 {len(no_email_urls)} 个. 总耗时: {duration_str}", 'info')

        logger.info(f"批量提取完成: {len(all_emails)} 个邮箱, {len(failed_urls)} 个失败, {len(no_email_urls)} 个无邮箱, 耗时: {duration_str}")
        
        return {
            'emails': list(all_emails),
            'failed_urls': failed_urls,
            'no_email_urls': no_email_urls,
            'total_processed': total,
            'total_emails': len(all_emails),
            'duration': duration
        }
    
    def pause(self):
        """暂停提取"""
        self.paused = True
        logger.info("提取已暂停")
    
    def resume(self):
        """继续提取"""
        self.paused = False
        logger.info("提取已继续")
    
    def stop(self):
        """停止提取"""
        self.stopped = True
        self.paused = False
        logger.info("提取已停止")
    
    async def close(self):
        """彻底关闭浏览器"""
        logger.info("开始关闭浏览器资源...")
        
        # 设置停止标志,防止新操作
        self.stopped = True
        
        try:
            # 1. 关闭所有打开的页面
            if self._pages:
                logger.info(f"关闭 {len(self._pages)} 个打开的页面...")
                pages_to_close = self._pages[:]  # 创建副本
                for page in pages_to_close:
                    try:
                        if not page.is_closed():
                            await asyncio.wait_for(page.close(), timeout=5.0)
                            logger.debug(f"页面已关闭")
                    except asyncio.TimeoutError:
                        logger.warning(f"关闭页面超时")
                    except Exception as e:
                        logger.warning(f"关闭页面出错: {e}")
                self._pages.clear()
                logger.info("所有页面已关闭")
            
            # 2. 关闭上下文
            if self.context:
                try:
                    await asyncio.wait_for(self.context.close(), timeout=10.0)
                    logger.info("BrowserContext 已关闭")
                except asyncio.TimeoutError:
                    logger.warning("关闭 context 超时")
                except Exception as e:
                    logger.warning(f"关闭 context 时出错: {e}")
                finally:
                    self.context = None
            
            # 3. 关闭浏览器
            if self.browser:
                try:
                    await asyncio.wait_for(self.browser.close(), timeout=10.0)
                    logger.info("Browser 已关闭")
                except asyncio.TimeoutError:
                    logger.warning("关闭 browser 超时")
                except Exception as e:
                    logger.warning(f"关闭 browser 时出错: {e}")
                finally:
                    self.browser = None
            
            # 4. 停止 Playwright
            if self.playwright_instance:
                try:
                    await asyncio.wait_for(self.playwright_instance.stop(), timeout=10.0)
                    logger.info("Playwright 已停止")
                except asyncio.TimeoutError:
                    logger.warning("停止 playwright 超时")
                except Exception as e:
                    logger.warning(f"停止 playwright 时出错: {e}")
                finally:
                    self.playwright_instance = None
            
            # 5. 重置状态
            self.stopped = False
            self.paused = False
            
            # 6. 等待资源完全释放
            await asyncio.sleep(1.0)  # 增加到1秒确保完全释放
            
            logger.info("浏览器资源已完全释放")
            
        except Exception as e:
            logger.error(f"关闭浏览器时出错: {e}", exc_info=True)
        
