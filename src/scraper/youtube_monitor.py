import asyncio
import hashlib
import os
import sys
import json
import re
import logging
from typing import List, Dict, Any

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import httpx
from supabase import create_client, Client
from dotenv import load_dotenv
from src.nlp.sentiment_analyzer import SentimentAnalyzer

# Load environment variables
load_dotenv(".env.local")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("YouTubeMonitor")

# Constants
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")

CHANNELS = {
    "Thanthi TV": "UC-JFyL0zDFOsPMpuWu39rPA",
    "Puthiya Thalaimurai": "UCmyKnNRH0wH-r8I-ceP-dsg",
    "Polimer News": "UC8Z-VjXBtDJTvq6aqkIskPg"
}

KEYWORDS = [
    'dmk', 'admk', 'aiadmk', 'bjp', 'tvk', 'tn election', 'stalin', 'edappadi', 'eps', 'vijay', 'annamalai', 'seeman', 'ntk',
    'திமுக', 'அதிமுக', 'பாஜக', 'தவெக', 'தேர்தல்', 'ஸ்டாலின்', 'எடப்பாடி', 'விஜய்', 'அண்ணாமலை', 'சீமான்', 'நாம் தமிழர்'
]

PARTY_BUCKETS = [
    {
        'name': 'TVK (Vijay)',
        'latinKeywords': ['tvk', 'vijay', 'thalapathy', 'tvk2026', 'vj', 'vetri kazhagam', 'anna'],
        'nativeKeywords': ['தவெக', 'விஜய்', 'தளபதி', 'தமிழக வெற்றிக் கழகம்']
    },
    {
        'name': 'DMK',
        'latinKeywords': ['dmk', 'stalin', 'udhay', 'rising sun', 'udhayanidhi', 'mk stalin'],
        'nativeKeywords': ['திமுக', 'ஸ்டாலின்', 'மு க ஸ்டாலின்', 'உதயநிதி']
    },
    {
        'name': 'AIADMK + BJP/NDA',
        'latinKeywords': ['aiadmk', 'admk', 'eps', 'ops', 'edappadi', 'bjp', 'annamalai', 'lotus', 'two leaves'],
        'nativeKeywords': ['அதிமுக', 'எடப்பாடி', 'எடப்பாடி பழனிசாமி', 'பாஜக', 'என்டிஏ', 'மோடி', 'அண்ணாமலை', 'பாமக']
    },
    {
        'name': 'NTK (Seeman)',
        'latinKeywords': ['ntk', 'seeman', 'naam thamizhar', 'annan', 'whistle'],
        'nativeKeywords': ['நாம் தமிழர்', 'நாம் தமிழர் கட்சி', 'சீமான்']
    }
]

VOTING_INTENT_PATTERNS = [
    r"vote for \w+", r"\w+ for 2026", r"cm \w+", r"winner", r"cup mukiyam", r"support \w*",
    "🇪🇸", "☀️", "🌿", "🦁", "🔥", "💯", "❤️"
]
VOTE_REGEX = re.compile("|".join(VOTING_INTENT_PATTERNS), re.IGNORECASE)


def escape_regexp(value: str) -> str:
    return re.escape(value)


def identify_entities_with_sentiment(text: str, overall_sentiment: str, analyzer) -> List[str]:
    """Module-level helper: maps text to per-party sentiment labels."""
    if not text:
        return []

    normalized = text.lower()

    present_parties = []
    for bucket in PARTY_BUCKETS:
        latin_match = False
        if bucket['latinKeywords']:
            pattern = "|".join(map(escape_regexp, bucket['latinKeywords']))
            regex = re.compile(rf"(^|[^a-z])({pattern})(?=$|[^a-z])", re.IGNORECASE)
            if regex.search(normalized):
                latin_match = True

        native_match = any(keyword.lower() in normalized for keyword in bucket['nativeKeywords'])

        if latin_match or native_match:
            present_parties.append(bucket['name'])

    if not present_parties:
        return []

    has_voting_intent = bool(VOTE_REGEX.search(normalized))
    results = []

    if len(present_parties) == 1:
        party = present_parties[0]
        sentiment = "POSITIVE" if has_voting_intent else overall_sentiment
        if ("🇪🇸" in text and party == "TVK (Vijay)") or \
           ("☀️" in text and party == "DMK") or \
           ("🌿" in text and party == "AIADMK + BJP/NDA") or \
           ("🦁" in text and party == "NTK (Seeman)"):
            sentiment = "POSITIVE"

        results.append(json.dumps({party: sentiment}))
        return results

    chunks = re.split(r'[,.!\n]| and | or | but ', text, flags=re.IGNORECASE)
    assigned_parties = set()

    for chunk in chunks:
        chunk_norm = chunk.lower()
        chunk_parties = []
        for bucket in PARTY_BUCKETS:
            if bucket['name'] in assigned_parties:
                continue

            latin_match = False
            if bucket['latinKeywords']:
                pattern = "|".join(map(escape_regexp, bucket['latinKeywords']))
                if re.search(rf"(^|[^a-z])({pattern})(?=$|[^a-z])", chunk_norm, re.IGNORECASE):
                    latin_match = True
            native_match = any(keyword.lower() in chunk_norm for keyword in bucket['nativeKeywords'])

            if latin_match or native_match:
                chunk_parties.append(bucket['name'])
                assigned_parties.add(bucket['name'])

        if chunk_parties:
            chunk_sentiment = analyzer.analyze(chunk)["label"]
            has_chunk_vi = bool(VOTE_REGEX.search(chunk_norm))

            for party in chunk_parties:
                final_sentiment = "POSITIVE" if has_chunk_vi else chunk_sentiment
                if ("🇪🇸" in chunk and party == "TVK (Vijay)") or \
                   ("☀️" in chunk and party == "DMK") or \
                   ("🌿" in chunk and party == "AIADMK + BJP/NDA") or \
                   ("🦁" in chunk and party == "NTK (Seeman)"):
                    final_sentiment = "POSITIVE"
                results.append(json.dumps({party: final_sentiment}))

    for p in present_parties:
        if p not in assigned_parties:
            sentiment = "POSITIVE" if has_voting_intent else overall_sentiment
            results.append(json.dumps({p: sentiment}))

    return results


class YouTubeMonitor:
    def __init__(self):
        if not YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY not found in .env.local")
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("Supabase credentials not found in .env.local")

        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.client = httpx.AsyncClient(timeout=30.0)
        self.analyzer = SentimentAnalyzer()

    async def close(self):
        await self.client.aclose()

    def generate_hash(self, text: str) -> str:
        """Generate a stable hash for a string to deduplicate."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    async def get_recent_videos(self, channel_id: str, max_videos: int = 150) -> List[Dict[str, Any]]:
        """Fetch the most recent videos from a channel using pagination."""
        logger.info(f"Fetching up to {max_videos} recent videos for channel: {channel_id}")
        url = "https://www.googleapis.com/youtube/v3/search"
        videos = []
        next_page_token = None

        while len(videos) < max_videos:
            params = {
                "part": "snippet",
                "channelId": channel_id,
                "maxResults": min(50, max_videos - len(videos)),
                "order": "date",
                "type": "video",
                "key": YOUTUBE_API_KEY
            }
            if next_page_token:
                params["pageToken"] = next_page_token

            response = await self.client.get(url, params=params)
            if response.status_code != 200:
                logger.error(f"Error fetching videos: {response.text}")
                break

            data = response.json()
            items = data.get("items", [])
            videos.extend(items)

            next_page_token = data.get("nextPageToken")
            if not next_page_token or not items:
                break

        return videos

    async def get_video_comments(self, video_id: str, max_comments: int = 300) -> List[Dict[str, Any]]:
        """Fetch top comments for a specific video using pagination."""
        logger.info(f"Fetching up to {max_comments} comments for video: {video_id}")
        url = "https://www.googleapis.com/youtube/v3/commentThreads"
        comments = []
        next_page_token = None

        while len(comments) < max_comments:
            params = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": min(100, max_comments - len(comments)),
                "order": "relevance",
                "key": YOUTUBE_API_KEY
            }
            if next_page_token:
                params["pageToken"] = next_page_token

            response = await self.client.get(url, params=params)
            if response.status_code != 200:
                logger.warning(f"Could not fetch comments for {video_id}: {response.status_code}")
                break

            data = response.json()
            for item in data.get("items", []):
                snippet = item["snippet"]["topLevelComment"]["snippet"]
                comments.append({
                    "video_id": video_id,
                    "comment_id": item["id"],
                    "text": snippet["textDisplay"],
                    "author": snippet["authorDisplayName"],
                    "published_at": snippet["publishedAt"],
                    "like_count": snippet.get("likeCount", 0)
                })

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break

        return comments

    def filter_videos(self, videos: List[Dict[str, Any]], keywords: List[str]) -> List[str]:
        """Filter video IDs based on keywords in title or description."""
        filtered_ids = []
        for video in videos:
            snippet = video["snippet"]
            text_to_search = (snippet["title"] + " " + snippet["description"]).lower()
            if any(kw.lower() in text_to_search for kw in keywords):
                filtered_ids.append(video["id"]["videoId"])
        return filtered_ids

    async def process_channel(self, channel_name: str, channel_id: str):
        """Monitor a single channel for relevant videos and pull comments."""
        logger.info(f"--- Processing {channel_name} ---")
        recent_videos = await self.get_recent_videos(channel_id)
        relevant_video_ids = self.filter_videos(recent_videos, KEYWORDS)

        logger.info(f"Found {len(relevant_video_ids)} relevant videos out of {len(recent_videos)} recent uploads.")

        all_comments = []
        for v_id in relevant_video_ids:
            comments = await self.get_video_comments(v_id)
            all_comments.extend(comments)
            await asyncio.sleep(0.5)

        if not all_comments:
            logger.info(f"No comments found for {channel_name}")
            return

        # Deduplicate locally before analysis to save compute
        unique_comments = []
        seen_hashes = set()
        for c in all_comments:
            h = self.generate_hash(c["text"])
            if h not in seen_hashes:
                unique_comments.append(c)
                seen_hashes.add(h)

        # Batch Sentiment Analysis
        logger.info(f"Analyzing sentiment for {len(unique_comments)} comments using IndicBERT...")
        texts = [c["text"] for c in unique_comments]
        sentiment_results = self.analyzer.batch_analyze(texts)

        # Prepare for Upsert
        processed_data = []
        for i, comment in enumerate(unique_comments):
            comment_hash = self.generate_hash(comment["text"])
            sentiment = sentiment_results[i]

            processed_data.append({
                "id": comment_hash,
                "video_id": comment["video_id"],
                "channel_name": channel_name,
                "comment_text": comment["text"],
                "author_name": comment["author"],
                "published_at": comment["published_at"],
                "sentiment_label": sentiment["label"],
                "sentiment_score": sentiment["score"],
                "parties": identify_entities_with_sentiment(comment["text"], sentiment["label"], self.analyzer),
                "metadata": {
                    "like_count": comment["like_count"],
                    "comment_id": comment["comment_id"]
                }
            })

        if processed_data:
            logger.info(f"Upserting {len(processed_data)} unique comments into voter_sentiment...")
            try:
                result = self.supabase.table("voter_sentiment").upsert(processed_data).execute()
                logger.info(f"✅ Upsert complete for {channel_name}")
            except Exception as e:
                logger.error(f"❌ Error upserting to Supabase: {e}")

    async def run(self):
        for name, c_id in CHANNELS.items():
            await self.process_channel(name, c_id)
        await self.close()


if __name__ == "__main__":
    monitor = YouTubeMonitor()
    asyncio.run(monitor.run())
