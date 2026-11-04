FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/src \
    OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MODEL_DIR=/app/models

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt \
    && useradd --create-home --uid 1000 app

COPY --chown=app:app app_api.py .
COPY --chown=app:app src/ ./src/
COPY --chown=app:app models/metadata.json models/sentiment_pipeline.joblib ./models/
USER app
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD ["python", "-c", "from urllib.request import urlopen; urlopen('http://127.0.0.1:7860/health', timeout=3)"]
CMD ["uvicorn", "app_api:app", "--host", "0.0.0.0", "--port", "7860"]
