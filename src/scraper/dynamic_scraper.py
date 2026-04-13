import asyncio
from playwright.async_api import async_playwright
import logging

logger = logging.getLogger(__name__)

class DynamicScraper:
    """
    Playwright-based scraper for JS-heavy news sites or social media.
    """
    async def scrape_url(self, url: str, selector: str = "body"):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Set a common user agent to avoid detection
            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
            })
            
            try:
                logger.info(f"Navigating to {url}...")
                await page.goto(url, wait_until="networkidle", timeout=60000)
                
                # Wait for content to load
                await page.wait_for_selector(selector)
                
                content = await page.content()
                await browser.close()
                return content
            except Exception as e:
                logger.error(f"Playwright error: {e}")
                await browser.close()
                return ""

async def test_dynamic():
    scraper = DynamicScraper()
    content = await scraper.scrape_url("https://www.puthiyathalaimurai.com/")
    print(f"Scraped {len(content)} bytes.")

if __name__ == "__main__":
    asyncio.run(test_dynamic())
