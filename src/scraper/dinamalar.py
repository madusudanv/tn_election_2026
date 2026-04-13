import asyncio
from bs4 import BeautifulSoup
from .async_scraper import AsyncScraper
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class DinamalarScraper(AsyncScraper):
    BASE_URL = "https://www.dinamalar.com"
    
    async def get_election_mentions(self) -> List[Dict]:
        """
        Scrapes the main Tamil news page for election-related keywords.
        """
        html = await self.fetch_page(f"{self.BASE_URL}/tamil-news.asp")
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        mentions = []
        
        # Dinamalar structure discovery (Simplified for baseline)
        # Note: In production, we would use more robust selectors or Playwright for dynamic content.
        links = soup.find_all('a', href=True)
        
        election_keywords = ["தேர்தல்", "திமுக", "அதிமுக", "பாஜக", "நாம் தமிழர்", "திராவிட"] 
        # election, DMK, ADMK, BJP, NTK, Dravidian
        
        seen_urls = set()
        
        for link in links:
            text = link.get_text().strip()
            href = link['href']
            
            if any(keyword in text for keyword in election_keywords):
                full_url = href if href.startswith("http") else f"{self.BASE_URL}/{href}"
                
                if full_url not in seen_urls:
                    mentions.append({
                        "content": text,
                        "source": "Dinamalar",
                        "url": full_url,
                        "metadata": {"type": "headline"}
                    })
                    seen_urls.add(full_url)
        
        logger.info(f"Dinamalar: Found {len(mentions)} election-related headlines.")
        return mentions

    async def scrape_article_content(self, url: str) -> str:
        """Fetch full article content for deeper sentiment analysis."""
        html = await self.fetch_page(url)
        if not html:
            return ""
        
        soup = BeautifulSoup(html, 'html.parser')
        # Dinamalar article body usually resides in specific divs
        article_body = soup.find('div', id='news-text') or soup.find('article')
        return article_body.get_text().strip() if article_body else ""
