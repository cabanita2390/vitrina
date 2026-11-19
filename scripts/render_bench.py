"""Render de prueba 9:16 (logo + texto + voz Kokoro) y consumo del renderer.

Uso (con `docker compose up -d tts renderer`):
    uv run python scripts/render_bench.py

Guarda el video en apps/renderer/out/ y un informe JSON.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import httpx
from tts_bench import StatsSampler, docker_stats, wait_healthy

OUT = Path(__file__).resolve().parents[1] / "apps" / "renderer" / "out"
TTS = "http://127.0.0.1:8100"
RENDERER = "http://127.0.0.1:8200"
CONTAINER = "vitrina-renderer-1"

VOICE_TEXT = (
    "¡Llegó la temporada de almojábanas en Panadería La Espiga! Todos los martes, "
    "dos por uno en Sogamoso. Te esperamos desde las siete de la mañana."
)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    wait_healthy(RENDERER)
    time.sleep(2)
    idle_cpu, idle_mem = docker_stats(CONTAINER)

    voice = httpx.post(
        f"{TTS}/synthesize", json={"text": VOICE_TEXT, "voice": "ef_dora"}, timeout=300
    )
    voice.raise_for_status()
    audio_seconds = float(voice.headers["X-Audio-Duration"])

    payload = {
        "composition": "SocialPost",
        "outputName": "demo_espiga",
        "assets": {"voz.wav": base64.b64encode(voice.content).decode()},
        "props": {
            "businessName": "Panadería La Espiga",
            "headline": "Almojábanas 2x1",
            "body": "Todos los martes en Sogamoso. ¡Te esperamos!",
            "audioUrl": "asset:voz.wav",
            "primaryColor": "#B45309",
            "accentColor": "#FDE68A",
            "durationInSeconds": round(audio_seconds + 1.5, 1),
        },
    }
    sampler = StatsSampler(CONTAINER)
    sampler.start()
    t0 = time.perf_counter()
    r = httpx.post(f"{RENDERER}/render", json=payload, timeout=900)
    wall = time.perf_counter() - t0
    sampler.stop()
    r.raise_for_status()
    result = r.json()

    video = httpx.get(f"{RENDERER}{result['location']}", timeout=120)
    (OUT / "demo_espiga.mp4").write_bytes(video.content)

    report = {
        "video_seconds": result["durationSeconds"],
        "render_seconds": result["renderSeconds"],
        "render_seconds_per_video_second": round(
            result["renderSeconds"] / result["durationSeconds"], 2
        ),
        "wall_seconds": round(wall, 1),
        "size_mb": round(result["sizeBytes"] / 1e6, 2),
        "idle": {"cpu_percent": idle_cpu, "ram_mib": round(idle_mem)},
        "busy_peak": {
            "cpu_percent": max(s[0] for s in sampler.samples),
            "ram_mib": round(max(s[1] for s in sampler.samples)),
        },
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
