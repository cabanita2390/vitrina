# Renderer Remotion (Chrome headless + FFmpeg incluidos por Remotion).
FROM node:22-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      libnss3 libdbus-1-3 libatk1.0-0 libgbm-dev libasound2 libxrandr2 libxkbcommon-dev \
      libxfixes3 libxcomposite1 libxdamage1 libatk-bridge2.0-0 libpango-1.0-0 libcairo2 \
      libcups2 fonts-dejavu-core curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# Instalación aislada del workspace (el lock de la raíz no se copia al contexto).
COPY package.json ./
RUN npm install --no-audit --no-fund --omit=dev && npx remotion browser ensure

COPY tsconfig.json ./
COPY src ./src
COPY server ./server

RUN mkdir -p /app/out/assets && chown -R node /app
USER node
ENV PORT=8200 RENDER_CONCURRENCY=2
EXPOSE 8200
HEALTHCHECK --interval=10s --timeout=3s --start-period=60s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8200/health || exit 1
CMD ["npx", "tsx", "server/index.ts"]
