import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { randomUUID } from "node:crypto";
import { createWriteStream } from "node:fs";
import { mkdir, unlink } from "node:fs/promises";
import path from "node:path";
import { pipeline } from "node:stream/promises";
import { Prisma } from "@prisma/client";
import { prisma } from "../lib/prisma.js";
import { env } from "../lib/env.js";
import { userPublicSelect } from "../lib/selects.js";

const itemSchema = z.object({
  name: z.string().min(1),
  description: z.string().optional(),
  categoryId: z.string().nullable().optional(),
  locationId: z.string().nullable().optional(),
  unit: z.string().default("Stk"),
  minQuantity: z.coerce.number().min(0).default(0),
  manufacturer: z.string().nullable().optional(),
  specs: z.record(z.any()).nullable().optional(),
  purchasePrice: z.coerce.number().nullable().optional(),
  purchaseSource: z.string().nullable().optional(),
  barcode: z.string().nullable().optional(),
});

const ALLOWED_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

function toJsonInput(specs: Record<string, unknown> | null | undefined) {
  if (specs === null) return Prisma.JsonNull;
  if (specs === undefined) return undefined;
  return specs as Prisma.InputJsonValue;
}

export default async function itemRoutes(fastify: FastifyInstance) {
  fastify.addHook("preHandler", fastify.requireAuth);

  fastify.get("/api/items", async (request) => {
    const { search, lowStock } = request.query as { search?: string; lowStock?: string };
    const where: Prisma.ItemWhereInput = {};
    if (search) {
      where.name = { contains: search, mode: "insensitive" };
    }
    const items = await prisma.item.findMany({
      where,
      include: { category: true, location: true },
      orderBy: { name: "asc" },
    });
    if (lowStock === "true") {
      return items.filter((item) => new Prisma.Decimal(item.quantity).lte(item.minQuantity));
    }
    return items;
  });

  fastify.get("/api/items/:id", async (request, reply) => {
    const { id } = request.params as { id: string };
    const item = await prisma.item.findUnique({
      where: { id },
      include: {
        category: true,
        location: true,
        movements: {
          orderBy: { createdAt: "desc" },
          take: 50,
          include: { project: true, user: { select: userPublicSelect } },
        },
      },
    });
    if (!item) return reply.code(404).send({ error: "Artikel nicht gefunden" });
    return item;
  });

  fastify.post("/api/items", async (request) => {
    const body = itemSchema.parse(request.body);
    const data: Prisma.ItemUncheckedCreateInput = { ...body, specs: toJsonInput(body.specs) };
    return prisma.item.create({ data });
  });

  fastify.patch("/api/items/:id", async (request) => {
    const { id } = request.params as { id: string };
    const body = itemSchema.partial().parse(request.body);
    const data: Prisma.ItemUncheckedUpdateInput = { ...body, specs: toJsonInput(body.specs) };
    return prisma.item.update({ where: { id }, data });
  });

  fastify.delete("/api/items/:id", async (request, reply) => {
    const { id } = request.params as { id: string };
    await prisma.item.delete({ where: { id } });
    return reply.code(204).send();
  });

  fastify.post("/api/items/:id/photo", async (request, reply) => {
    const { id } = request.params as { id: string };
    const item = await prisma.item.findUnique({ where: { id } });
    if (!item) return reply.code(404).send({ error: "Artikel nicht gefunden" });

    const file = await request.file();
    if (!file) return reply.code(400).send({ error: "Keine Datei übermittelt" });
    if (!ALLOWED_IMAGE_TYPES.has(file.mimetype)) {
      return reply.code(400).send({ error: "Nur JPEG/PNG/WebP erlaubt" });
    }

    await mkdir(env.photoStorageDir, { recursive: true });
    const extension = file.mimetype === "image/png" ? "png" : file.mimetype === "image/webp" ? "webp" : "jpg";
    const filename = `${id}-${randomUUID()}.${extension}`;
    const destPath = path.join(env.photoStorageDir, filename);

    await pipeline(file.file, createWriteStream(destPath));

    if (item.photoPath) {
      await unlink(path.join(env.photoStorageDir, item.photoPath)).catch(() => undefined);
    }

    return prisma.item.update({ where: { id }, data: { photoPath: filename } });
  });
}
