import hashlib
import json
from collections import Counter
from pathlib import Path

import joblib

from youtube_sentiment.api.schemas import BatchRequest, Prediction, Summary
from youtube_sentiment.data.download import LABELS


class Predictor:
    def __init__(self, directory: Path):
        artifact = directory / "sentiment_pipeline.joblib"
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if checksum != metadata["pipeline_sha256"]:
            raise ValueError("Model artifact checksum does not match metadata")
        pipeline = joblib.load(artifact)
        self.clean = pipeline.named_steps["clean"]
        self.model = pipeline[1:]
        self.version = metadata["model_version"]
        if set(self.model.classes_) != set(LABELS):
            raise ValueError("Model is missing required sentiment classes")

    def predict(self, batch: BatchRequest) -> tuple[list[Prediction], Summary]:
        cleaned = self.clean.transform([comment.text for comment in batch.comments])
        usable = [text for text in cleaned if text]
        scores = iter(self.model.predict_proba(usable) if usable else [])
        predictions = []
        for comment, text in zip(batch.comments, cleaned, strict=True):
            if not text:
                predictions.append(Prediction(
                    id=comment.id, status="skipped", reason="No usable text after cleaning"
                ))
                continue
            probabilities = next(scores)
            index = int(probabilities.argmax())
            label = int(self.model.classes_[index])
            predictions.append(Prediction(
                id=comment.id, status="ok", label=label,
                sentiment=LABELS[label], confidence=float(probabilities[index]),
            ))
        counts = Counter(item.sentiment for item in predictions if item.status == "ok")
        summary = Summary(
            received=len(predictions), analyzed=len(usable), skipped=len(predictions) - len(usable),
            counts={name: counts[name] for name in LABELS.values()},
            percentages={name: round(100 * counts[name] / len(usable), 2) if usable else 0
                         for name in LABELS.values()},
        )
        return predictions, summary
