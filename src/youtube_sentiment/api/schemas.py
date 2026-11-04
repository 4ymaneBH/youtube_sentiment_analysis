from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

Sentiment = Literal["negative", "neutral", "positive"]


class Comment(BaseModel):
    id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class BatchRequest(BaseModel):
    comments: list[Comment] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_ids(self) -> "BatchRequest":
        if len({comment.id for comment in self.comments}) != len(self.comments):
            raise ValueError("Comment IDs must be unique within each batch")
        return self


class Prediction(BaseModel):
    id: str
    status: Literal["ok", "skipped"]
    label: Literal[-1, 0, 1] | None = None
    sentiment: Sentiment | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str | None = None


class Summary(BaseModel):
    received: int
    analyzed: int
    skipped: int
    counts: dict[Sentiment, int]
    percentages: dict[Sentiment, float]


class BatchResponse(BaseModel):
    results: list[Prediction]
    summary: Summary
    model_version: str
    inference_ms: float
