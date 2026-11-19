"""Benchmark de Kokoro: velocidad, RAM/CPU y tiempo de arranque del contenedor.

Uso (con el contenedor tts corriendo):
    uv run python scripts/tts_bench.py --container vitrina-tts-1

Escribe los audios y un informe en apps/tts/bench/out/.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "apps" / "tts" / "bench" / "out"

TEXTS: dict[str, str] = {
    "precios": (
        "¡Promoción en Panadería La Espiga! Pan de bono a $2.500, almojábanas 2x1 "
        "y torta de queso a $25.000. Válido hasta el 30 de noviembre."
    ),
    "horarios": (
        "Abrimos de lunes a sábado de 7:00 a. m. a 8:30 p. m., y los domingos de 8 a 2. "
        "Pedidos al 310 456 7890. Domicilio gratis por compras desde $40.000."
    ),
    "lugares": (
        "Visítanos en Sogamoso, Duitama, Paipa y Tunja. Lo mejor de Boyacá, "
        "con el sabor de siempre y ahora a domicilio."
    ),
    "anuncio_45s": (
        "¿Buscas el regalo perfecto para esta Navidad? En Artesanías El Telar, en el centro "
        "de Sogamoso, tenemos ruanas de lana virgen tejidas a mano por artesanos de Boyacá. "
        "Cada pieza es única: colores tierra, diseños tradicionales y la calidez que solo da "
        "la lana de nuestras montañas. Este mes, llévate una ruana desde $85.000 y recibe "
        "una bufanda de regalo. Además, por compras superiores a $150.000, el envío a "
        "Duitama, Paipa y Tunja es totalmente gratis. Estamos abiertos de lunes a domingo, "
        "de 9 de la mañana a 7 de la noche, en la calle 12 número 10-45, frente al parque "
        "principal. También puedes hacer tu pedido por WhatsApp al 311 222 3344. Artesanías "
        "El Telar: tradición boyacense que abriga. ¡Te esperamos!"
    ),
}

CASES: list[tuple[str, str]] = [
    ("precios", "ef_dora"),
    ("precios", "em_alex"),
    ("horarios", "ef_dora"),
    ("horarios", "em_alex"),
    ("lugares", "ef_dora"),
    ("lugares", "em_alex"),
    ("anuncio_45s", "ef_dora"),
    ("anuncio_45s", "em_alex"),
    ("anuncio_45s", "em_santa"),
]


@dataclass
class Result:
    text: str
    voice: str
    characters: int
    audio_seconds: float
    process_seconds: float
    rtf: float  # segundos de proceso por segundo de audio
    file: str


def docker_stats(container: str) -> tuple[float, float]:
    """(CPU %, RAM MiB) instantáneos del contenedor."""
    out = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}};{{.MemUsage}}", container],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    cpu_s, mem_s = out.split(";")
    used = mem_s.split("/")[0].strip()
    value = float(used[:-3])
    unit = used[-3:]
    mib = value * {"KiB": 1 / 1024, "MiB": 1, "GiB": 1024}[unit]
    return float(cpu_s.rstrip("%")), mib


class StatsSampler(threading.Thread):
    def __init__(self, container: str) -> None:
        super().__init__(daemon=True)
        self.container = container
        self.samples: list[tuple[float, float]] = []
        self._halt = threading.Event()

    def run(self) -> None:
        while not self._halt.is_set():
            self.samples.append(docker_stats(self.container))

    def stop(self) -> None:
        self._halt.set()
        self.join()


def wait_healthy(url: str, timeout: float = 300) -> float:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        try:
            if httpx.get(f"{url}/health", timeout=2).json().get("status") == "ok":
                return time.monotonic() - t0
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(0.5)
    raise TimeoutError("el servicio TTS no quedó listo")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8100")
    parser.add_argument("--container", required=True)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    # 1. Arranque en frío del contenedor (reinicio -> /health ok)
    subprocess.run(["docker", "restart", args.container], check=True, capture_output=True)
    startup = wait_healthy(args.url)
    health = httpx.get(f"{args.url}/health").json()
    time.sleep(3)
    idle_cpu, idle_mem = docker_stats(args.container)

    # 2. Calentamiento (la primera síntesis es más lenta)
    httpx.post(f"{args.url}/synthesize", json={"text": "Hola.", "voice": "ef_dora"}, timeout=120)

    # 3. Casos
    sampler = StatsSampler(args.container)
    sampler.start()
    results: list[Result] = []
    with httpx.Client(timeout=600) as client:
        for text_id, voice in CASES:
            text = TEXTS[text_id]
            r = client.post(f"{args.url}/synthesize", json={"text": text, "voice": voice})
            r.raise_for_status()
            path = OUT / f"{text_id}_{voice}.wav"
            path.write_bytes(r.content)
            audio = float(r.headers["X-Audio-Duration"])
            process = float(r.headers["X-Process-Seconds"])
            results.append(
                Result(text_id, voice, len(text), audio, process, process / audio, path.name)
            )
            print(
                f"{text_id:12} {voice:9} audio={audio:6.1f}s proceso={process:6.2f}s "
                f"RTF={process / audio:.3f}"
            )
    sampler.stop()

    busy_cpu = max(s[0] for s in sampler.samples)
    busy_mem = max(s[1] for s in sampler.samples)
    total_audio = sum(r.audio_seconds for r in results)
    total_process = sum(r.process_seconds for r in results)
    summary = {
        "container_startup_seconds": round(startup, 1),
        "model_load_seconds": health.get("model_load_seconds"),
        "idle": {"cpu_percent": idle_cpu, "ram_mib": round(idle_mem)},
        "busy_peak": {"cpu_percent": busy_cpu, "ram_mib": round(busy_mem)},
        "process_seconds_per_audio_minute": round(total_process / total_audio * 60, 1),
        "median_rtf": round(statistics.median(r.rtf for r in results), 3),
        "results": [asdict(r) for r in results],
    }
    (OUT / "report.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
