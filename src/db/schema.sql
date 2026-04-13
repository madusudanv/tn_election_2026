-- SQL Script to set up the mentions table in Supabase
-- Run this in the Supabase SQL Editor for your second project

CREATE TABLE IF NOT EXISTS mentions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content TEXT NOT NULL,
    source TEXT NOT NULL, -- e.g., 'Dinamalar', 'Twitter'
    url TEXT,
    sentiment_label TEXT, -- 'POSITIVE', 'NEGATIVE', 'NEUTRAL'
    sentiment_score FLOAT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster sentiment analysis lookups
CREATE INDEX IF NOT EXISTS idx_mentions_sentiment ON mentions(sentiment_label);
CREATE INDEX IF NOT EXISTS idx_mentions_source ON mentions(source);

-- Enable Row Level Security (RLS)
ALTER TABLE mentions ENABLE ROW LEVEL SECURITY;

-- Create policy to allow public read (if needed) or restricted write
CREATE POLICY "Enable insert for authenticated users only" ON mentions
    FOR INSERT WITH CHECK (true); -- Adjust based on your security needs

CREATE POLICY "Enable select for everyone" ON mentions
    FOR SELECT USING (true);
