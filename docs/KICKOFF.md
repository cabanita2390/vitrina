# Prompt inicial para Claude Code (sesión 1)

Copia y pega esto en Claude Code, abierto en la carpeta `vitrina/`:

---
Lee CLAUDE.md, docs/DECISIONES.md, docs/sync/BUZON.md y los documentos de negocio de la carpeta padre (../04-mvp.md y ../05-arquitectura.md).

Objetivo de esta sesión: dejar listo el esqueleto del monorepo de Vitrina para empezar a desarrollar, siguiendo CLAUDE.md al pie de la letra. Antes de escribir código, propónme un plan corto y espera mi aprobación.

Alcance:
1. git init, .gitignore, .env.example, README con cómo levantar todo en Windows.
2. Supabase CLI: proyecto local y primera migración con organizations, memberships, sponsorships, brand_kits, credit_ledger, credit_rates y usage_costs, con RLS por organization_id y un trigger que cree la organización y la membresía "owner" al registrarse un usuario.
3. apps/api (FastAPI): health check, validación del JWT de Supabase, endpoint de "mi organización". Configuración con pydantic-settings.
4. apps/worker: cola elegida (arq o Dramatiq; justifica y registra en docs/DECISIONES.md), una tarea de ejemplo idempotente.
5. Interfaces de proveedores (LLMProvider, VideoProvider, TTSProvider, Renderer) con su implementación real para Claude (Anthropic SDK) y presupuesto diario de gasto. Fakes solo en tests.
6. apps/tts: servicio Kokoro-82M en Docker con endpoint /synthesize y un script que genere 3 audios de prueba en español (ef_dora, em_alex) midiendo el tiempo por minuto de audio.
7. apps/renderer: proyecto Remotion mínimo con una composición 9:16 (logo + texto + audio) renderizable por HTTP.
8. apps/web: Vite + React + TS + Tailwind + shadcn/ui, login con Supabase y pantalla "mi organización".
9. docker-compose.yml (api, worker, redis, tts, renderer), ruff/mypy/eslint, pytest con un test, GitHub Actions de lint y test.

Al terminar: actualiza CLAUDE.md si cambió algo, agrega las decisiones a docs/DECISIONES.md y responde en docs/sync/BUZON.md el mensaje de Cowork (resultado de Kokoro y elección de la cola).
---

Nota: si Claude Code pide permiso para leer la carpeta padre, acéptalo, o ábrelo con `claude --add-dir ..`.
