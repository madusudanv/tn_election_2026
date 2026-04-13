from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
import torch
import re

class SentimentAnalyzer:
    def __init__(self, model_name="vives/indic-bert-tamil-sentiment"):
        """
        Initializes the Sentiment Analyzer with IndicBERT (fine-tuned for Tamil sentiment).
        If a specific fine-tuned model isn't provided, it defaults to a Tamil sentiment model.
        """
        self.device = 0 if torch.cuda.is_available() else -1
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.classifier = pipeline("sentiment-analysis", model=self.model, tokenizer=self.tokenizer, device=self.device)

    def clean_text(self, text: str):
        """Clean and normalize Tamil text for better IndicBERT performance."""
        # Remove URLs and email addresses
        text = re.sub(r'http\S+|www\S+|mailto\S+', '', text, flags=re.MULTILINE)
        # Remove special characters and numbers (optional, keeping Tamil script)
        # Tamil Unicode range: \u0B80-\u0BFF
        text = re.sub(r'[^\u0B80-\u0BFF\s]', '', text)
        # Remove extra whitespace
        text = " ".join(text.split())
        return text

    def analyze(self, text: str):
        """
        Analyze the sentiment of a given Tamil text.
        Returns a dictionary with label and score.
        """
        text = self.clean_text(text)
        if not text:
            return {"label": "NEUTRAL", "score": 1.0}
        
        # IndicBERT handles up to 512 tokens
        results = self.classifier(text[:512])
        return results[0]

    def batch_analyze(self, texts: list):
        """Analyze markers in bulk."""
        results = self.classifier([t[:512] for t in texts if t])
        return results
