"""Servicio de voz Kokoro-82M (Apache-2.0). Español: ef_dora, em_alex, em_santa."""

from __future__ import annotations

import io
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Any

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from kokoro import KPipeline
from misaki.espeak import EspeakG2P
from pydantic import BaseModel, Field

SAMPLE_RATE = 24_000
SPANISH_VOICES = ("ef_dora", "em_alex", "em_santa")
# es-419 (español latinoamericano) da seseo; "es" es fonética de España (θ).
G2P_LANGUAGE = os.environ.get("TTS_G2P_LANGUAGE", "es-419")
STARTED_AT = time.monotonic()

state: dict[str, Any] = {}
_lock = threading.Lock()  # una síntesis a la vez: torch ya usa todos los núcleos


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    t0 = time.monotonic()
    pipeline = KPipeline(lang_code="e", repo_id="hexgrad/Kokoro-82M")
    if G2P_LANGUAGE != "es":
        pipeline.g2p = EspeakG2P(language=G2P_LANGUAGE)
    for voice in SPANISH_VOICES:  # precarga de voces
        pipeline.load_voice(voice)
    state["pipeline"] = pipeline
    state["load_seconds"] = round(time.monotonic() - t0, 2)
    yield


app = FastAPI(title="Vitrina TTS (Kokoro-82M)", version="0.1.0", lifespan=lifespan)


class SynthesizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    voice: str = "ef_dora"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok" if "pipeline" in state else "loading",
        "model_load_seconds": state.get("load_seconds"),
        "uptime_seconds": round(time.monotonic() - STARTED_AT, 1),
        "torch_threads": os.environ.get("OMP_NUM_THREADS", "auto"),
        "g2p_language": G2P_LANGUAGE,
    }


@app.get("/voices")
def voices() -> dict[str, list[str]]:
    return {"es": list(SPANISH_VOICES)}


def _synthesize(req: SynthesizeRequest) -> tuple[bytes, float, float]:
    pipeline: KPipeline = state["pipeline"]
    t0 = time.perf_counter()
    chunks: list[np.ndarray] = []
    with _lock:
        for _graphemes, _phonemes, audio in pipeline(req.text, voice=req.voice, speed=req.speed):
            if audio is not None:
                chunks.append(audio.numpy() if hasattr(audio, "numpy") else np.asarray(audio))
    process_seconds = time.perf_counter() - t0
    if not chunks:
        raise ValueError("no se generó audio")
    samples = np.concatenate(chunks)
    buf = io.BytesIO()
    sf.write(buf, samples, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    return buf.getvalue(), len(samples) / SAMPLE_RATE, process_seconds


@app.post("/synthesize", response_class=Response)
async def synthesize(req: SynthesizeRequest) -> Response:
    if req.voice not in SPANISH_VOICES:
        raise HTTPException(422, f"voz no soportada; usa una de {SPANISH_VOICES}")
    if "pipeline" not in state:
        raise HTTPException(503, "modelo cargando")
    try:
        wav, duration, process = await run_in_threadpool(_synthesize, req)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return Response(
        content=wav,
        media_type="audio/wav",
        headers={
            "X-Audio-Duration": f"{duration:.3f}",
            "X-Process-Seconds": f"{process:.3f}",
            "X-Characters": str(len(req.text)),
        },
    )
