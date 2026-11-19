# CLAUDE.md — Vitrina

Contexto para Claude Code. Léelo completo al iniciar cada sesión.

## Qué es Vitrina (nombre tentativo)
Plataforma SaaS de creación de contenido con IA para negocios pequeños de Colombia (arranque en Boyacá).
El negocio carga su marca y la plataforma organiza la idea, genera calendario, guiones, voz y videos (modo plantilla o IA generativa) y, en v2, publica en Instagram/TikTok y muestra métricas.
Modelo: suscripción con créditos incluidos + recargas. Canal adicional (v2): instituciones (cámaras de comercio, alcaldías) que compran licencias para grupos de comerciantes.

Fundador y único desarrollador: Felipe Cabana (Pipe). ~6 h/día. Presupuesto mínimo: no gastar en infraestructura ni IA más de lo necesario, pero sin sacrificar calidad de arquitectura.
Entorno: Windows + Docker Desktop + Python 3.12 + Node 20+.

## Documentos de negocio (carpeta padre)
- ../README.md — estado de la metodología y registro de decisiones de negocio.
- ../04-mvp.md — alcance del MVP y cronograma.
- ../05-arquitectura.md — arquitectura completa, costos y fuentes.
- ../03-matriz.md — por qué se eligió esta idea, hipótesis a validar.
No los modifiques salvo que Felipe lo pida; las decisiones técnicas van en docs/DECISIONES.md.

## Stack (decidido)
- Frontend: React + Vite + TypeScript estricto, TanStack Query, Tailwind + shadcn/ui.
- Auth/DB/Realtime: Supabase (Postgres, RLS). Local con Supabase CLI.
- API: FastAPI (Python 3.12, Pydantic v2). Valida el JWT de Supabase.
- Workers: Python con arq + Redis, siempre detrás de la interfaz propia `JobQueue` (packages/core). Reintentos e idempotencia.
- Cerebro/ideación: Claude vía API (prompts y herramientas propias versionadas en el repo; Agent Skills solo donde aporten). Haiku por defecto, Sonnet donde haga falta calidad.
- Video modo plantilla: Remotion (servicio Node `apps/renderer`) + FFmpeg para utilidades.
- Video modo IA: agregador (fal.ai / Replicate / similar) -> Seedance, Kling, Veo.
- Voz estándar: Kokoro-82M (Apache-2.0) en servicio propio `apps/tts`. Voces español: ef_dora, em_alex, em_santa. Requiere espeak-ng.
- Archivos: Cloudflare R2 (S3 compatible), buckets dev/prod. Sin MinIO.
- Observabilidad: Sentry, logs estructurados, Langfuse.
- Infra futura: VPS + Coolify (Docker). Por ahora todo en local.

## Reglas de arquitectura (no negociables sin consultar a Felipe)
1. Monolito modular + workers. Nada de microservicios ni Kubernetes.
2. Multi-tenant por organización: toda tabla de negocio lleva `organization_id`; RLS en todas las tablas. Al registrarse se crea la organización automáticamente (autoservicio). Instituciones = organizaciones tipo `institution` que patrocinan negocios (`sponsorships`).
3. Capa de proveedores con interfaces: `LLMProvider`, `VideoProvider`, `TTSProvider`, `Renderer`. Cambiar de proveedor = configuración.
4. IA REAL también en desarrollo. Topes de gasto: presupuesto diario configurable en la app que corta llamadas, modelo barato por defecto en dev. Fakes SOLO en pruebas automatizadas (pytest/CI).
5. Créditos: libro inmutable (`credit_ledger`), saldo calculado, tarifas por proveedor (`credit_rates`), trabajos idempotentes (nunca cobrar dos veces).
6. Registrar costo real por trabajo en `usage_costs` (proveedor, segundos, caracteres, tokens, USD).
7. Migraciones con Supabase CLI como única fuente de verdad (esquema + políticas RLS).
8. Contratos tipados: OpenAPI de FastAPI -> cliente TypeScript generado.
9. Secretos solo en variables de entorno (.env fuera del repo; .env.example sí).

## Restricciones de licencias y proveedores
- Remotion: licencia gratis (<= 3 personas). Mantener el render detrás de `Renderer` para poder cambiar a FFmpeg.
- ElevenLabs: NO en v1. Sus términos OEM exigen plan Scale (USD 299/mes) para ofrecerlo a terceros. En v2: opción "trae tu propia clave".
- No usar motores TTS con licencia no comercial o AGPL (p. ej., voicestudio.sh). Chatterbox (marca de agua) queda para evaluar en v2.

## Estructura del monorepo
apps/web · apps/api · apps/worker · apps/renderer (Remotion) · apps/tts (Kokoro) · packages/core (Python compartido: config, proveedores, JobQueue, presupuesto) · supabase/ (migraciones, seed, tests) · scripts/ · docs/ · docker-compose.yml · .github/workflows/

Herramientas: npm workspaces (web, renderer) · uv workspace (core, api, worker; apps/tts aparte por sus dependencias pesadas) · Supabase CLI vía `npx supabase`.

## Modelo de datos (primer corte)
organizations · memberships · sponsorships · brand_kits · assets · content_plans · content_items · scripts · voiceovers · render_jobs · videos · credit_ledger · credit_rates · usage_costs

## Calidad
- Python: ruff + mypy (estricto), pytest. TS: eslint + typescript estricto.
- Evals simples para prompts (casos de entrada/salida esperada).
- CI con GitHub Actions: lint, test, build.
- Código e identificadores en inglés; textos de la interfaz y documentación en español.

## Alcance v1 (ver ../04-mvp.md)
Registro/organización · kit de marca · asistente de ideación + calendario · guiones · voz Kokoro · video plantilla + IA · biblioteca y descarga · créditos con recarga manual · panel admin de costos.
Fuera de v1: publicación directa IG/TikTok, métricas, panel institucional, ElevenLabs, pasarela de pagos.

## Mantener este archivo y la sincronización con Cowork
- Cuando Felipe y tú tomen una decisión técnica relevante, ACTUALIZA este CLAUDE.md (si cambia una regla o el stack) y agrega una entrada en docs/DECISIONES.md (fecha, decisión, motivo, alternativas descartadas).
- Al iniciar cada sesión, lee docs/sync/BUZON.md. Si hay mensajes "Para: Claude Code" sin responder, atiéndelos y responde ahí mismo.
- Si algo afecta negocio, precios, alcance o cronograma, deja un mensaje "Para: Cowork" en docs/sync/BUZON.md.
- Pregunta a Felipe antes de contradecir una regla de este archivo.
