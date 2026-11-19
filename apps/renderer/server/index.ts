/**
 * Servidor HTTP de render (detrás de la interfaz `Renderer` del backend).
 *
 * POST /render  { composition, props, outputName, assets? }  -> { location, ... }
 *   assets: { "voz.wav": "<base64>" } se sirven en /assets para que Chrome los lea.
 *   (Cuando exista R2, props apuntará a URLs firmadas y `assets` dejará de usarse.)
 * GET  /files/:name  descarga el video generado (solo desarrollo).
 */
import express from "express";
import { randomUUID } from "node:crypto";
import { mkdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";

const PORT = Number(process.env.PORT ?? 8200);
const ROOT = path.resolve(import.meta.dirname, "..");
const OUT_DIR = path.join(ROOT, "out");
const ASSETS_DIR = path.join(ROOT, "out", "assets");
const SAFE_NAME = /^[a-zA-Z0-9_-]{1,80}$/;
const SAFE_ASSET = /^[a-zA-Z0-9_-]{1,80}\.(wav|mp3|png|jpg|jpeg|webp|svg)$/;

await mkdir(ASSETS_DIR, { recursive: true });

console.log(JSON.stringify({ event: "bundling" }));
const t0 = performance.now();
const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.ts") });
console.log(JSON.stringify({ event: "bundled", seconds: (performance.now() - t0) / 1000 }));

const app = express();
app.use(express.json({ limit: "50mb" }));
app.use("/assets", express.static(ASSETS_DIR));

let busy = false;

app.get("/health", (_req, res) => {
  res.json({ status: "ok", busy });
});

app.get("/files/:name", (req, res) => {
  const name = req.params.name;
  if (!/^[a-zA-Z0-9_-]{1,80}\.mp4$/.test(name)) {
    res.status(400).json({ detail: "nombre inválido" });
    return;
  }
  res.sendFile(path.join(OUT_DIR, name));
});

app.post("/render", async (req, res) => {
  const { composition = "SocialPost", props = {}, outputName, assets = {} } = req.body ?? {};
  const name = outputName ?? randomUUID();
  if (!SAFE_NAME.test(name)) {
    res.status(400).json({ detail: "outputName inválido" });
    return;
  }
  if (busy) {
    // Un render a la vez por contenedor: la cola real vive en el worker.
    res.status(429).json({ detail: "renderer ocupado" });
    return;
  }
  busy = true;
  try {
    const resolvedProps: Record<string, unknown> = { ...props };
    for (const [file, b64] of Object.entries(assets as Record<string, string>)) {
      if (!SAFE_ASSET.test(file)) throw new Error(`asset inválido: ${file}`);
      await writeFile(path.join(ASSETS_DIR, file), Buffer.from(b64, "base64"));
      for (const [k, v] of Object.entries(resolvedProps)) {
        if (v === `asset:${file}`) resolvedProps[k] = `http://127.0.0.1:${PORT}/assets/${file}`;
      }
    }

    const start = performance.now();
    const comp = await selectComposition({ serveUrl, id: composition, inputProps: resolvedProps });
    const outputLocation = path.join(OUT_DIR, `${name}.mp4`);
    await renderMedia({
      composition: comp,
      serveUrl,
      codec: "h264",
      outputLocation,
      inputProps: resolvedProps,
      concurrency: Number(process.env.RENDER_CONCURRENCY ?? 2),
    });
    const renderSeconds = (performance.now() - start) / 1000;
    const { size } = await stat(outputLocation);
    res.json({
      location: `/files/${name}.mp4`,
      durationSeconds: comp.durationInFrames / comp.fps,
      renderSeconds: Math.round(renderSeconds * 100) / 100,
      sizeBytes: size,
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ detail: err instanceof Error ? err.message : String(err) });
  } finally {
    busy = false;
  }
});

app.listen(PORT, () => console.log(JSON.stringify({ event: "listening", port: PORT })));
