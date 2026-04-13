import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class SupabaseManager:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables.")
        self.supabase: Client = create_client(url, key)

    def insert_mention(self, data: dict):
        """Insert a scraped news or social media mention into the database."""
        return self.supabase.table("mentions").insert(data).execute()

    def insert_sentiment(self, data: dict):
        """Insert a sentiment analysis record into the election_sentiment table."""
        return self.supabase.table("election_sentiment").insert(data).execute()

    def get_latest_mentions(self, limit: int = 100):
        """Fetch latest mentions for analysis."""
        return self.supabase.table("mentions").select("*").order("created_at", desc=True).limit(limit).execute()

    def update_sentiment(self, mention_id: str, sentiment: dict):
        """Update the sentiment analysis results for a mention."""
        return self.supabase.table("mentions").update({"sentiment": sentiment}).eq("id", mention_id).execute()
