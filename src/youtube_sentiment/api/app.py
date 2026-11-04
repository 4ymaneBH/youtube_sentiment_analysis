import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from youtube_sentiment.api.schemas import BatchRequest, BatchResponse
from youtube_sentiment.models.predict import Predictor

logger = logging.getLogger("uvicorn.error")


def create_app(model_dir: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        directory = model_dir if model_dir is not None else Path(os.getenv("MODEL_DIR", "models"))
        application.state.predictor = None
        try:
            application.state.predictor = Predictor(directory)
        except Exception:
            logger.exception("Could not load the sentiment model")
        yield

    application = FastAPI(title="YouTube Sentiment API", version="1.0.0", lifespan=lifespan)
    origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()]
    if origins:
        application.add_middleware(
            CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    @application.get("/health")
    def health(request: Request):
        predictor = request.app.state.predictor
        if predictor is None:
            return JSONResponse({"status": "unavailable", "model_version": None}, status_code=503)
        return {"status": "ok", "model_version": predictor.version}

    @application.post("/predict_batch")
    def predict_batch(batch: BatchRequest, request: Request) -> BatchResponse:
        predictor = request.app.state.predictor
        if predictor is None:
            raise HTTPException(503, "Sentiment model unavailable")
        started = perf_counter()
        request_id = uuid4().hex
        try:
            results, summary = predictor.predict(batch)
        except Exception as exc:
            logger.exception("Prediction failed request_id=%s batch_size=%s", request_id, len(batch.comments))
            raise HTTPException(500, "Sentiment prediction failed") from exc
        elapsed = round((perf_counter() - started) * 1000, 3)
        logger.info("Prediction request_id=%s batch_size=%s inference_ms=%s",
                    request_id, len(batch.comments), elapsed)
        return BatchResponse(results=results, summary=summary, model_version=predictor.version,
                             inference_ms=elapsed)

    return application


app = create_app()
