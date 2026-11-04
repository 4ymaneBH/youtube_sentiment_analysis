import math
from pathlib import Path

import joblib
import pytest
from fastapi.testclient import TestClient

from youtube_sentiment.api.app import create_app

ARTIFACTS = Path(__file__).resolve().parents[1] / "models"


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(ARTIFACTS)) as test_client:
        yield test_client


def test_health_and_artifact_parity(client):
    health = client.get("/health")
    assert health.status_code == 200
    texts = ["This tutorial was incredibly helpful!", "I absolutely hate this.", "The video is 12 minutes.", "😊"]
    comments = [{"id": f"c{idx}", "text": text} for idx, text in enumerate(texts)]
    comments.insert(1, {"id": "skip", "text": "https://example.com"})
    response = client.post("/predict_batch", json={"comments": comments})
    assert response.status_code == 200
    result = response.json()
    assert result["model_version"] == health.json()["model_version"]
    assert [row["id"] for row in result["results"]] == [item["id"] for item in comments]
    assert result["results"][1]["status"] == "skipped"
    assert result["results"][1]["label"] is None
    model = joblib.load(ARTIFACTS / "sentiment_pipeline.joblib")
    expected = model.predict_proba(texts)
    usable = [row for row in result["results"] if row["status"] == "ok"]
    for row, probabilities in zip(usable, expected, strict=True):
        assert row["label"] == int(model.classes_[probabilities.argmax()])
        assert math.isclose(row["confidence"], float(probabilities.max()))
    summary = result["summary"]
    assert summary["analyzed"] == len(texts) and summary["skipped"] == 1
    assert sum(summary["counts"].values()) == len(texts)
    assert sum(summary["percentages"].values()) == pytest.approx(100, abs=0.02)


@pytest.mark.parametrize("comments", [
    [], [{"id": "1", "text": "  "}], [{"id": "1", "text": 99}],
    [{"id": "1", "text": "x" * 5001}], [{"id": str(i), "text": "ok"} for i in range(51)],
    [{"id": "same", "text": "hello"}, {"id": "same", "text": "world"}],
])
def test_invalid_batch(client, comments):
    assert client.post("/predict_batch", json={"comments": comments}).status_code == 422


def test_largest_valid_batch(client):
    comments = [{"id": str(i), "text": "J'adore ce tuto 😊 great work"} for i in range(50)]
    response = client.post("/predict_batch", json={"comments": comments})
    assert response.status_code == 200
    assert response.json()["summary"]["analyzed"] == 50


def test_unavailable_model(tmp_path):
    with TestClient(create_app(tmp_path)) as test_client:
        assert test_client.get("/health").status_code == 503
        response = test_client.post("/predict_batch", json={"comments": [{"id": "1", "text": "ok"}]})
        assert response.status_code == 503


def test_cors_is_configurable(monkeypatch):
    origin = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"
    monkeypatch.setenv("CORS_ORIGINS", origin)
    with TestClient(create_app(ARTIFACTS)) as test_client:
        response = test_client.options("/predict_batch", headers={
            "Origin": origin, "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        })
        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == origin
