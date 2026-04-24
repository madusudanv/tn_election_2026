import os
from supabase import create_client
from dotenv import load_dotenv

# Load from .env.local
load_dotenv(".env.local")

url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
key = os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")

if not url or not key:
    print("Error: NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY not found in .env.local")
    exit(1)

supabase = create_client(url, key)

try:
    print(f"Testing access to table 'election_sentiment' at {url}...")
    response = supabase.table("election_sentiment").select("*").limit(1).execute()
    print("SUCCESS: Can access 'election_sentiment' table.")
    print(f"Data received: {response.data}")
except Exception as e:
    print(f"FAILURE: Failed to access table: {e}")
