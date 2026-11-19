# Vitrina

Plataforma SaaS de creación de contenido con IA para negocios pequeños de Colombia.
Contexto completo para desarrollo: [CLAUDE.md](CLAUDE.md). Decisiones técnicas: [docs/DECISIONES.md](docs/DECISIONES.md).

## Estructura

```
apps/web        React + Vite + TS (interfaz)
apps/api        FastAPI (lógica de negocio, valida JWT de Supabase)
apps/worker     Worker arq (trabajos asíncronos)
apps/renderer   Remotion (render de video modo plantilla, HTTP)
apps/tts        Kokoro-82M (voz, HTTP)
packages/core   Código Python compartido: config, proveedores, cola, presupuesto
supabase/       Migraciones, políticas RLS, seed y tests de BD
scripts/        Utilidades (smoke test del LLM, mediciones)
docs/           Decisiones y buzón con Cowork
```

## Requisitos (Windows)

- Docker Desktop (con WSL2) **abierto**.
- Node 20+ y npm.
- [uv](https://docs.astral.sh/uv/) (instala Python 3.12 solo: `uv python install 3.12`).
- Git.

## Levantar todo en local

```powershell
# 1. Dependencias
npm install
uv sync

# 2. Variables de entorno
copy .env.example .env

# 3. Supabase local (Postgres, Auth, Studio) — primera vez descarga imágenes
npx supabase start
npx supabase status        # copia anon key y service_role key a .env

# 4. API, worker, Redis, TTS y renderer
docker compose up --build
```

Direcciones:

| Servicio | URL |
|---|---|
| API (docs OpenAPI) | http://127.0.0.1:8000/docs |
| Supabase Studio | http://127.0.0.1:54323 |
| Correos de prueba (Inbucket/Mailpit) | http://127.0.0.1:54324 |
| TTS | http://127.0.0.1:8100/docs |
| Renderer | http://127.0.0.1:8200/health |
| Web | http://127.0.0.1:5173 (`npm run dev -w apps/web`) |

## Calidad

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest                    # tests unitarios
uv run pytest -m db              # tests contra Supabase local (aislamiento, ledger)
npm run lint; npm run typecheck
```

## Base de datos

- Nueva migración: `npx supabase migration new <nombre>`.
- Aplicar desde cero: `npx supabase db reset`.
- Las migraciones son la **única** fuente de verdad del esquema y la RLS.

## Sin clave de Claude

Todo arranca sin `ANTHROPIC_API_KEY`. Las llamadas al LLM devuelven el error
"falta ANTHROPIC_API_KEY". Cuando exista la clave: `uv run python scripts/llm_smoke_test.py`.
