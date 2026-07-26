import Fastify from "fastify";
import cors from "@fastify/cors";
import multipart from "@fastify/multipart";
import fastifyStatic from "@fastify/static";
import { ZodError } from "zod";
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
import shoppingListRoutes from "./routes/shopping-list.js";

async function buildServer() {
  const fastify = Fastify({
    logger: env.nodeEnv === "development" ? { transport: { target: "pino-pretty" } } : true,
  });

  // Must be registered before any route plugin below: child contexts created by fastify.register()
  // capture the error handler in effect at registration time, so a handler set afterwards (even on
  // the root instance) is invisible to routes registered earlier — see CLAUDE.md.
  fastify.setErrorHandler((err, request, reply) => {
    if (err instanceof ZodError) {
      return reply.code(400).send({ error: err.errors.map((e) => e.message).join("; ") });
    }
    const statusCode =
      typeof err === "object" && err !== null && "statusCode" in err && typeof err.statusCode === "number"
        ? err.statusCode
        : 500;
    if (statusCode >= 500) request.log.error(err);
    const message = err instanceof Error ? err.message : "Unbekannter Fehler";
    return reply.code(statusCode).send({ error: statusCode < 500 ? message : "Interner Serverfehler" });
  });

  await fastify.register(cors, {
    origin: env.corsOrigin,
    credentials: true,
    methods: ["GET", "POST", "PATCH", "DELETE"],
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
  await fastify.register(shoppingListRoutes);

  fastify.get("/api/health", async () => ({ status: "ok" }));

  return fastify;
}

buildServer()
  .then((fastify) => fastify.listen({ port: env.port, host: "0.0.0.0" }))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
