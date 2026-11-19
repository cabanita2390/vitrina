# Servicio de voz Kokoro-82M (CPU).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models/hf

RUN apt-get update \
    && apt-get install -y --no-install-recommends espeak-ng libsndfile1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.4,<3"
COPY requirements.txt .
RUN pip install -r requirements.txt

# Descarga pesos y voces en la imagen: el contenedor arranca sin red y más rápido.
RUN python -c "from kokoro import KPipeline; p = KPipeline(lang_code='e', repo_id='hexgrad/Kokoro-82M'); [p.load_voice(v) for v in ('ef_dora','em_alex','em_santa')]"

COPY app.py .

RUN useradd --create-home --uid 1000 tts && chown -R tts /models
USER tts

ENV HF_HUB_OFFLINE=1
EXPOSE 8100
HEALTHCHECK --interval=10s --timeout=3s --start-period=60s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8100/health | grep -q '"ok"' || exit 1
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8100"]
