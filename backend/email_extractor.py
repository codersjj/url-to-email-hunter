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
            # 获取页面的 HTML 内容和可见文本
            page_html = await page.content()
            page_text = await page.inner_text('body')
            
            logger.info(f"开始从 HTML 提取邮箱...")
            emails_from_html = self._extract_emails_from_text(page_html)
            
            logger.info(f"开始从可见文本提取邮箱...")
            emails_from_text = self._extract_emails_from_text(page_text)
            
            return emails_from_html.union(emails_from_text)
        except Exception as e:
            logger.error(f"页面提取失败: {str(e)}")
            return set()
    
    async def extract_from_url(self, url: str, callback=None) -> Set[str]:
        """从单个URL提取邮箱"""
        emails = set()
        visited_urls = set()
        
        try:
            if callback:
                await callback('log', f"正在访问: {url}", 'info')
            
            page = await self.context.new_page()
            
            # 访问原始 URL
            await page.goto(url, wait_until='networkidle', timeout=60000)
            visited_urls.add(url)
            await asyncio.sleep(2)
            
            if callback:
                await callback('log', f"页面加载完成: {url}", 'success')
            
            # 1. 从当前页面提取
            current_emails = await self._extract_from_page(page)
            emails.update(current_emails)
            
            if current_emails:
                if callback:
                    await callback('log', f"从当前页面提取到 {len(current_emails)} 个邮箱", 'success')
                    await callback('email', list(emails))
            
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
                        await page.goto(english_url, wait_until='networkidle', timeout=30000)
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
                                
                    except Exception as e:
                        logger.warning(f"访问英文版页面失败: {str(e)}")
            
            await page.close()
            
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