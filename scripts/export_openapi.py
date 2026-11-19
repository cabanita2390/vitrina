"""Exporta el contrato OpenAPI de la API para generar el cliente TypeScript.

Uso: uv run python scripts/export_openapi.py apps/web/openapi.json
(`npm run gen:api -w apps/web` lo hace todo.)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from vitrina_api.main import create_app
from vitrina_core.config import Settings


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    spec = create_app(Settings(app_env="test")).openapi()
    target.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OpenAPI escrito en {target}")


if __name__ == "__main__":
    main()
