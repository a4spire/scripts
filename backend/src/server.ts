import Fastify from "fastify";
import cors from "@fastify/cors";
import multipart from "@fastify/multipart";
import fastifyStatic from "@fastify/static";
import { env } from "./lib/env.js";
import authPlugin from "./plugins/auth.js";
import authRoutes from "./routes/auth.js";
import locationRoutes from "./routes/locations.js";
import categoryRoutes from "./routes/categories.js";
import itemRoutes from "./routes/items.js";
import movementRoutes from "./routes/movements.js";
import projectRoutes from "./routes/projects.js";
import aiRoutes from "./routes/ai.js";
import statsRoutes from "./routes/stats.js";

async function buildServer() {
  const fastify = Fastify({
    logger: env.nodeEnv === "development" ? { transport: { target: "pino-pretty" } } : true,
  });

  await fastify.register(cors, {
    origin: env.corsOrigin,
    credentials: true,
  });
  await fastify.register(multipart, {
    limits: { fileSize: 25 * 1024 * 1024 },
  });
  await fastify.register(fastifyStatic, {
    root: env.photoStorageDir,
    prefix: "/photos/",
  });

  await fastify.register(authPlugin);

  await fastify.register(authRoutes);
  await fastify.register(locationRoutes);
  await fastify.register(categoryRoutes);
  await fastify.register(itemRoutes);
  await fastify.register(movementRoutes);
  await fastify.register(projectRoutes);
  await fastify.register(aiRoutes);
  await fastify.register(statsRoutes);

  fastify.get("/api/health", async () => ({ status: "ok" }));

  return fastify;
}

buildServer()
  .then((fastify) => fastify.listen({ port: env.port, host: "0.0.0.0" }))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
