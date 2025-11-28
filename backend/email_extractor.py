from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import asyncio
import logging
import re
from typing import List, Set

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailExtractor:
    # Common fake email prefixes to filter out (from Email Hunter extension)
    # Note: Removed overly strict single-letter prefixes (b, c, g, h, n, o, s, y) 
    # as they filter out valid emails like sales@, support@, etc.
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
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.browser = None
        self.context = None
        self.paused = False
        self.stopped = False
    
    def _extract_emails_from_text(self, text: str, domain: str = None) -> Set[str]:
        """
        Extract and filter emails from text using Email Hunter extension's logic.
        
        Args:
            text: Text content to extract emails from
            domain: Optional domain to filter emails (only include emails from this domain)
        
        Returns:
            Set of valid, filtered email addresses
        """
        if not text:
            return set()
        
        # Clean the text
        text = text.replace('\\n', ' ')
        
        # Email regex pattern from Email Hunter extension
        # Pattern: word chars, dots, hyphens, plus signs @ domain with TLD
        # Note: In character classes, hyphen must be escaped or placed at start/end
        pattern = r'\b[a-z\d\-][_a-z\d\-+]*(?:\.[_a-z\d\-+]*)*@[a-z\d]+[a-z\d\-]*(?:\.[a-z\d\-]+)*(?:\.[a-z]{2,63})\b'
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        if not matches:
            return set()
        
        valid_emails = set()
        filtered_count = 0
        
        for email in matches:
            email = email.lower().strip()
            
            # Skip if already added
            if email in valid_emails:
                continue
            
            # Filter by domain if specified
            if domain and domain not in email:
                logger.debug(f"过滤邮箱 (域名不匹配): {email}")
                filtered_count += 1
                continue
            
            # Filter out image and resource file extensions
            if email.endswith(('.png', '.jpg', '.gif', '.css', '.webp', '.crx1')):
                logger.debug(f"过滤邮箱 (图片/资源文件): {email}")
                filtered_count += 1
                continue
            
            if email.endswith('.js'):
                logger.debug(f"过滤邮箱 (JS文件): {email}")
                filtered_count += 1
                continue
            
            # Clean up prefixes
            original = email
            email = re.sub(r'^(x3|x2|u003|u0022)', '', email, flags=re.IGNORECASE)
            email = re.sub(r'^sx_mrsp_', '', email, flags=re.IGNORECASE)
            email = re.sub(r'^3a', '', email, flags=re.IGNORECASE)
            
            # If email changed but is no longer valid, skip
            if email != original and not re.search(pattern, email, re.IGNORECASE):
                logger.debug(f"过滤邮箱 (清理前缀后无效): {original} -> {email}")
                filtered_count += 1
                continue
            
            # Filter out common spam patterns
            if re.search(r'(no|not)[-|_]*reply', email, re.IGNORECASE):
                logger.debug(f"过滤邮箱 (noreply模式): {email}")
                filtered_count += 1
                continue
            
            if re.search(r'mailer[-|_]*daemon', email, re.IGNORECASE):
                logger.debug(f"过滤邮箱 (mailer-daemon): {email}")
                filtered_count += 1
                continue
            
            if re.search(r'reply.+\d{5,}', email, re.IGNORECASE):
                logger.debug(f"过滤邮箱 (reply+数字): {email}")
                filtered_count += 1
                continue
            
            # Filter out emails with too many consecutive digits
            if re.search(r'\d{13,}', email):
                logger.debug(f"过滤邮箱 (过多连续数字): {email}")
                filtered_count += 1
                continue
            
            # Filter out specific domains and keywords
            spam_keywords = [
                'nondelivery', '@linkedin.com', '@sentry', '@linkedhelper.com',
                'feedback', 'notification'
            ]
            if any(keyword in email for keyword in spam_keywords):
                logger.debug(f"过滤邮箱 (垃圾关键词): {email}")
                filtered_count += 1
                continue
            
            # Filter out fake email prefixes
            email_prefix = email.split('@')[0]
            if email_prefix in self.FAKE_EMAIL_PREFIXES:
                logger.info(f"过滤邮箱 (假邮箱前缀): {email} (前缀: {email_prefix})")
                filtered_count += 1
                continue
            
            # If all filters passed, add to valid emails
            if email:
                logger.info(f"✓ 保留有效邮箱: {email}")
                valid_emails.add(email)
        
        if filtered_count > 0:
            logger.info(f"总共过滤掉 {filtered_count} 个邮箱，保留 {len(valid_emails)} 个有效邮箱")
        
        return valid_emails
        
    async def initialize(self, extension_path: str = None):
        """初始化浏览器和插件"""
        playwright = await async_playwright().start()
        
        # 启动浏览器（可选择加载Email Hunter插件）
        if extension_path:
            self.context = await playwright.chromium.launch_persistent_context(
                user_data_dir='./user_data',
                headless=self.headless,
                args=[
                    f'--disable-extensions-except={extension_path}',
                    f'--load-extension={extension_path}',
                ],
                locale='en-US',
                timezone_id='America/New_York'
            )
            self.browser = self.context.browser
        else:
            self.browser = await playwright.chromium.launch(headless=self.headless)
            self.context = await self.browser.new_context(
                locale='en-US',
                timezone_id='America/New_York'
            )
        
        logger.info("浏览器已启动")
        return self

    async def _find_english_link(self, page) -> str:
        """查找页面上的英文版链接"""
        try:
            # 查找常见的英文语言切换链接
            # 1. 包含 "English" 或 "EN" 文本的链接
            # 2. href 中包含 "/en/" 的链接
            # 3. title 或 aria-label 包含 "English" 的链接
            
            # 使用 JavaScript 查找最可能的英文链接
            english_url = await page.evaluate("""() => {
                const links = Array.from(document.querySelectorAll('a'));
                for (const link of links) {
                    const text = link.innerText.trim().toLowerCase();
                    const href = link.href.toLowerCase();
                    const title = (link.title || '').toLowerCase();
                    const ariaLabel = (link.getAttribute('aria-label') || '').toLowerCase();
                    
                    // 检查文本内容
                    if (text === 'english' || text === 'en' || text.includes('english version')) {
                        return link.href;
                    }
                    
                    // 检查属性
                    if (title.includes('english') || ariaLabel.includes('english')) {
                        return link.href;
                    }
                    
                    // 检查 URL 结构 (作为备选，优先级较低)
                    if (href.includes('/en/') || href.endsWith('/en')) {
                        // 排除当前页面已经是英文版的情况
                        if (!window.location.href.includes('/en/')) {
                            return link.href;
                        }
                    }
                }
                return null;
            }""")
            
            return english_url
        except Exception as e:
            logger.warning(f"查找英文链接时出错: {str(e)}")
            return None

    async def _extract_from_page(self, page) -> Set[str]:
        """从当前页面内容提取邮箱的辅助方法"""
        try:
            # Check if page is ready
            ready_state = await page.evaluate('document.readyState')
            logger.debug(f"页面状态: {ready_state}")
            
            # 获取页面的 HTML 内容和可见文本
            page_html = await page.content()
            page_text = await page.inner_text('body')
            
            logger.debug(f"HTML 长度: {len(page_html)}, 文本长度: {len(page_text)}")
            
            logger.info(f"开始从 HTML 提取邮箱...")
            emails_from_html = self._extract_emails_from_text(page_html)
            
            logger.info(f"开始从可见文本提取邮箱...")
            emails_from_text = self._extract_emails_from_text(page_text)
            
            all_emails = emails_from_html.union(emails_from_text)
            logger.info(f"本次提取共找到 {len(all_emails)} 个邮箱")
            
            return all_emails
        except Exception as e:
            logger.error(f"页面提取失败: {str(e)}", exc_info=True)
            return set()
    
    async def extract_from_url(self, url: str, callback=None) -> Set[str]:
        """从单个URL提取邮箱"""
        emails = set()
        visited_urls = set()
        max_retries = 2  # 最大重试次数
        
        try:
            if callback:
                await callback('log', f"正在访问: {url}", 'info')
            
            page = await self.context.new_page()
            
            # 访问原始 URL，带重试机制
            retry_count = 0
            page_loaded = False
            
            while retry_count < max_retries and not page_loaded:
                try:
                    # 使用更宽松的等待策略和更长的超时时间
                    # domcontentloaded: DOM 加载完成即可，不等待所有资源
                    # 超时从 60s 增加到 90s
                    await page.goto(url, wait_until='domcontentloaded', timeout=90000)
                    visited_urls.add(url)
                    
                    # Wait for network to be mostly idle
                    try:
                        logger.info("等待网络空闲...")
                        await page.wait_for_load_state('networkidle', timeout=10000)
                        logger.info("网络已空闲")
                    except PlaywrightTimeout:
                        logger.warning("网络空闲超时，继续处理")
                    
                    # Additional wait for any delayed scripts
                    await asyncio.sleep(3)
                    page_loaded = True
                    
                    if callback:
                        await callback('log', f"页面加载完成: {url}", 'success')
                        
                except PlaywrightTimeout:
                    retry_count += 1
                    if retry_count < max_retries:
                        if callback:
                            await callback('log', f"超时，正在重试 ({retry_count}/{max_retries})...", 'warning')
                        await asyncio.sleep(3)  # 重试前等待 3 秒
                    else:
                        raise  # 最后一次重试失败，抛出异常
            
            # 1. 从当前页面提取（带重试机制）
            max_extraction_attempts = 3
            previous_emails = set()
            
            for attempt in range(max_extraction_attempts):
                logger.info(f"提取尝试 {attempt + 1}/{max_extraction_attempts}")
                current_emails = await self._extract_from_page(page)
                
                # 如果结果与上次相同且不是第一次，说明结果已稳定
                if current_emails == previous_emails and attempt > 0:
                    logger.info(f"提取结果已稳定，提前结束重试")
                    break
                
                previous_emails = current_emails
                
                # 如果不是最后一次尝试，等待后再试
                if attempt < max_extraction_attempts - 1:
                    logger.info(f"等待2秒后进行下一次提取尝试...")
                    await asyncio.sleep(2)
            
            emails.update(current_emails)
            
            if current_emails:
                if callback:
                    await callback('log', f"从当前页面提取到 {len(current_emails)} 个邮箱", 'success')
                    await callback('email', list(emails))
            else:
                logger.warning(f"未从页面提取到任何邮箱: {url}")
                if callback:
                    await callback('log', f"警告: 未从当前页面提取到邮箱", 'warning')
            
            # 2. 尝试查找并访问英文版页面
            english_url = await self._find_english_link(page)
            
            # 如果找到了英文链接，且该链接未被访问过，且当前页面似乎不是英文版
            if english_url and english_url not in visited_urls:
                # 简单的检查：如果当前 URL 已经包含 /en/，可能不需要跳转
                if '/en/' not in url:
                    logger.info(f"发现英文版链接，尝试跳转: {english_url}")
                    if callback:
                        await callback('log', f"发现英文版页面，正在跳转...", 'info')
                    
                    try:
                        # 英文页面也使用更宽松的策略，但超时时间稍短
                        await page.goto(english_url, wait_until='domcontentloaded', timeout=60000)
                        visited_urls.add(english_url)
                        await asyncio.sleep(2)
                        
                        # 从英文页面提取
                        english_page_emails = await self._extract_from_page(page)
                        new_emails = english_page_emails - emails
                        
                        if new_emails:
                            emails.update(new_emails)
                            logger.info(f"从英文版页面额外提取到 {len(new_emails)} 个邮箱")
                            if callback:
                                await callback('log', f"从英文版页面额外提取到 {len(new_emails)} 个邮箱", 'success')
                                await callback('email', list(emails))
                        else:
                            if callback:
                                await callback('log', "英文版页面未发现新邮箱", 'info')
                                
                    except PlaywrightTimeout:
                        logger.warning(f"访问英文版页面超时: {english_url}")
                        if callback:
                            await callback('log', f"英文版页面加载超时，跳过", 'warning')
                    except Exception as e:
                        logger.warning(f"访问英文版页面失败: {str(e)}")
            
            await page.close()
            
        except PlaywrightTimeout:
            logger.error(f"页面加载超时（已重试 {max_retries} 次）: {url}")
            if callback:
                await callback('log', f"错误: {url} - 页面加载超时（已重试 {max_retries} 次），跳过该网站", 'error')
        except Exception as e:
            logger.error(f"提取 {url} 时出错: {str(e)}")
            if callback:
                await callback('log', f"错误: {url} - {str(e)}", 'error')
        
        return emails
    
    async def extract_from_urls(self, urls: List[str], callback=None) -> List[str]:
        """批量提取邮箱"""
        all_emails = set()
        total = len(urls)
        
        for index, url in enumerate(urls):
            # 检查是否暂停或停止
            while self.paused and not self.stopped:
                await asyncio.sleep(0.5)
            
            if self.stopped:
                if callback:
                    await callback('log', '提取已停止', 'warning')
                break
            
            # 提取邮箱
            emails = await self.extract_from_url(url, callback)
            all_emails.update(emails)
            
            # 更新进度
            progress = int((index + 1) / total * 100)
            if callback:
                await callback('progress', progress)
        
        if callback:
            await callback('log', f"提取完成！共 {len(all_emails)} 个唯一邮箱", 'success')
            await callback('complete', list(all_emails))
        
        print("all_emails:", all_emails)
        return list(all_emails)
    
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
        logger.info("提取已停止")
    
    async def close(self):
        """关闭浏览器"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.info("浏览器已关闭")