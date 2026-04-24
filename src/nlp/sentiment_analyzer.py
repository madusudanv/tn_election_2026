from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
import torch
import re

class SentimentAnalyzer:
    def __init__(self, model_name="vishnun/bert-base-cased-tamil-mix-sentiment"):
        """
        Initializes the Sentiment Analyzer with a Code-Mixed Tamil model specially tuned for tanglish slang.
        """
        self.device = 0 if torch.cuda.is_available() else -1
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.classifier = pipeline("sentiment-analysis", model=self.model, tokenizer=self.tokenizer, device=self.device)
        
        # Vishnun model labels: Positive, Negative, Mixed_feelings, unknown_state, not-Tamil
        self.label_map = {
            "Positive": "POSITIVE",
            "Negative": "NEGATIVE", 
            "Mixed_feelings": "NEUTRAL",
            "unknown_state": "NEUTRAL",
            "not-Tamil": "NEUTRAL"
        }
        self.positive_cues = {
            "winner": 2, "win": 2, "nice": 1, "best": 1, "thank you": 1, "thanks": 1,
            "support": 1, "vote": 2, "cm": 1, "varum": 2, "namadhe": 2, "chance kudupom": 1,
            "jeyikkattum": 3, "jayikkattum": 3, "vazhga": 3,
            "வெற்றி": 2, "ஜெயிக்கட்டும்": 3, "வாழ்க": 3, "ஆதரவு": 1, "நல்ல": 1, "சூப்பர்": 1,
            "வரும்": 2, "நமதே": 2, "cup mukiyam": 2,
            "🇪🇸": 2, "☀️": 2, "🌿": 2, "🦁": 2, "🔥": 2, "💯": 2, "❤️": 2
        }
        self.negative_cues = {
            "bad": 2, "worst": 2, "corrupt": 2, "control": 1, "weak": 1, "confused": 1,
            "hype": 1, "propaganda": 1, "dont trust": 2, "don't trust": 2, "letdown": 2,
            "failed": 2, "failure": 2, "go away": 1, "remove": 1, "ozhiyattum": 1,
            "ஒழியட்டும்": 1, "மோசம்": 2, "கெட்ட": 2, "ஏமாற்றம்": 2, "தோல்வி": 2
        }

    def clean_text(self, text: str):
        """Standard cleaning for social media text."""
        text = re.sub(r'http\S+|www\S+|mailto\S+', '', text, flags=re.MULTILINE)
        # We keep Tamil characters (\u0B80-\u0BFF) and alphanumeric for English
        text = re.sub(r'[^\u0B80-\u0BFF\s\w]', '', text)
        return " ".join(text.split())

    def _count_cues(self, text: str, cues: dict[str, int]) -> int:
        lowered = text.lower()
        score = 0
        for cue, weight in cues.items():
            cue_lower = cue.lower()
            if re.search(r'[a-z]', cue_lower):
                if re.search(rf'(^|[^a-z]){re.escape(cue_lower)}(?=$|[^a-z])', lowered):
                    score += weight
            elif cue in text:
                score += weight
        return score

    def _postprocess_label(self, text: str, result: dict):
        raw_label = result["label"]
        mapped_label = self.label_map.get(raw_label, raw_label)

        if raw_label in {"Mixed_feelings", "unknown_state", "not-Tamil"}:
            positive_hits = self._count_cues(text, self.positive_cues)
            negative_hits = self._count_cues(text, self.negative_cues)

            # Election slogans often combine anti-opponent and pro-party phrasing in one line.
            if positive_hits >= negative_hits + 1 and positive_hits >= 1:
                mapped_label = "POSITIVE"
            elif negative_hits >= positive_hits + 1 and negative_hits >= 1:
                mapped_label = "NEGATIVE"

        return {
            "label": mapped_label,
            "score": result["score"]
        }

    def format_result(self, result):
        """Map generic labels to readable ones."""
        return {
            "label": self.label_map.get(result["label"], result["label"]),
            "score": result["score"]
        }

    def analyze(self, text: str):
        text = self.clean_text(text)
        if not text:
            return {"label": "NEUTRAL", "score": 1.0}
        
        results = self.classifier(text[:512])
        return self._postprocess_label(text, results[0])

    def batch_analyze(self, texts: list):
        # Filter and clean
        cleaned_texts = [self.clean_text(t)[:512] for t in texts if t]
        if not cleaned_texts:
            return []
            
        results = self.classifier(cleaned_texts)
        return [self._postprocess_label(text, result) for text, result in zip(cleaned_texts, results)]
