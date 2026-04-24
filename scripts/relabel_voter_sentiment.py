import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.nlp.sentiment_analyzer import SentimentAnalyzer


def main():
    print("Starting relabeling process...")
    load_dotenv(ROOT / ".env.local")

    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
    if not url or not key:
        raise SystemExit("Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY in .env.local")

    client = create_client(url, key)
    analyzer = SentimentAnalyzer()

    page_size = 500
    offset = 0
    updated = 0

    while True:
        response = (
            client.table("voter_sentiment")
            .select("id, comment_text, sentiment_label, sentiment_score")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            break

        for i, row in enumerate(rows):
            text = row.get("comment_text") or ""
            result = analyzer.analyze(text)
            if (
                row.get("sentiment_label") != result["label"]
                or abs((row.get("sentiment_score") or 0) - result["score"]) > 1e-9
            ):
                (
                    client.table("voter_sentiment")
                    .update(
                        {
                            "sentiment_label": result["label"],
                            "sentiment_score": result["score"],
                        }
                    )
                    .eq("id", row["id"])
                    .execute()
                )
                updated += 1
            
            if (offset + i + 1) % 50 == 0:
                print(f"Processed {offset + i + 1} rows... Updated: {updated}")

        offset += page_size

    print(f"Relabeling complete. Total updated {updated} rows.")


if __name__ == "__main__":
    main()
