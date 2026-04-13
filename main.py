import asyncio
import os
from src.scraper.dinamalar import DinamalarScraper
from src.nlp.sentiment_analyzer import SentimentAnalyzer
from src.db.supabase_client import SupabaseManager
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_pipeline():
    logger.info("🚀 Initializing TN Election 2026 Analysis Pipeline...")
    
    # Check for credentials
    if not os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_URL") == "your_supabase_url_here":
        logger.warning("⚠️ SUPABASE_URL not set properly in .env. Skipping database operations.")
        db = None
    else:
        try:
            db = SupabaseManager()
        except Exception as e:
            logger.error(f"Failed to connect to Supabase: {e}")
            db = None

    # Initialize NLP & Scraper
    try:
        analyzer = SentimentAnalyzer()
        scraper = DinamalarScraper()
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        return

    # 1. Scrape headlines from Dinamalar
    logger.info("📡 Scraping Dinamalar for election news...")
    mentions = await scraper.get_election_mentions()
    
    if not mentions:
        logger.info("No new mentions found at this time.")
        await scraper.close()
        return

    # 2. Analyze & Store
    for mention in mentions[:10]: # Limit to 10 for initial test
        logger.info(f"Processing: {mention['content'][:50]}...")
        
        # Sentiment Analysis
        sentiment = analyzer.analyze(mention['content'])
        mention['sentiment_label'] = sentiment['label']
        mention['sentiment_score'] = sentiment['score']
        
        # Upsert into Supabase
        if db:
            try:
                db.insert_mention({
                    "content": mention['content'],
                    "source": mention['source'],
                    "url": mention['url'],
                    "sentiment_label": mention['sentiment_label'],
                    "sentiment_score": mention['sentiment_score'],
                    "metadata": mention['metadata']
                })
                logger.info(f"✅ Stored in Supabase: {mention['sentiment_label']}")
            except Exception as e:
                logger.error(f"Supabase Error: {e}")
        else:
            logger.info(f"📊 Result (Local): {mention['sentiment_label']} ({mention['sentiment_score']:.2f})")

    await scraper.close()
    logger.info("🏁 Pipeline run complete.")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
