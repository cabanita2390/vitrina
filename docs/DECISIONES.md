# Registro de decisiones técnicas — Vitrina

Formato: fecha · decisión · motivo · alternativas descartadas. Lo actualizan Claude Code y Cowork.

- 2026-11-19 · Monolito modular + workers (React, FastAPI, Supabase, Redis, R2) · escalable sin complejidad de microservicios para un fundador único · NestJS (menos natural para IA), microservicios/K8s.
- 2026-11-19 · Multi-tenant por organización con RLS · prepara agencias, equipos y canal institucional sin migraciones · datos por usuario.
- 2026-11-19 · IA real en desarrollo con topes de gasto; fakes solo en tests · Felipe quiere la plataforma funcionando con IA real · simular proveedores en dev.
- 2026-11-19 · Cloudflare R2 desde el inicio · 10 GB gratis, egress gratis · MinIO local, Supabase Storage para videos.
- 2026-11-19 · Remotion para el modo plantilla (licencia gratis <= 3 personas) · animación en React de calidad · solo FFmpeg (queda como respaldo).
- 2026-11-19 · Kokoro-82M como voz estándar · Apache-2.0, español, liviano, sin marca de agua · VoiceStudio (AGPL/no comercial), Chatterbox (marca de agua, GPU).
- 2026-11-19 · ElevenLabs fuera de v1; en v2 "trae tu propia clave" · términos OEM exigen plan Scale · pagar Scale desde el inicio.
- 2026-11-19 · Cola de trabajos: arq + Redis, detrás de la interfaz propia `JobQueue.enqueue(job_name, payload, idempotency_key)` en packages/core · asyncio nativo (encaja con FastAPI y los SDK async), liviano, reintentos y job_id para deduplicar; la interfaz permite migrar sin tocar la API ni las tareas (arq está en modo mantenimiento) · Dramatiq (síncrono, más piezas), Celery (pesado), RQ (sin async).
- 2026-11-19 · packages/core para el código Python compartido (config, proveedores, JobQueue, presupuesto) · evita duplicar entre api y worker · copiar código o que el worker importe la api.
- 2026-11-19 · Herramientas: Supabase CLI vía npx, npm workspaces para web/renderer, uv workspace con Python 3.12 para core/api/worker; apps/tts fuera del workspace · instalación reproducible en Windows sin instaladores globales; torch no infla el lock del resto · Poetry, pnpm, Supabase CLI global.
