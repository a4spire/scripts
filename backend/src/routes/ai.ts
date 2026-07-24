import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { randomUUID } from "node:crypto";
import { mkdir, rename, unlink } from "node:fs/promises";
import path from "node:path";
import { prisma } from "../lib/prisma.js";
import { env } from "../lib/env.js";
import { analyzePhoto, parseFreeText, transcribeAudio } from "../services/ai-service.js";
import { bookMovement, MovementError } from "../services/movement-service.js";

const textRequestSchema = z.object({ text: z.string().min(1) });

const createItemOpSchema = z.object({
  kind: z.literal("create_item"),
  name: z.string().min(1),
  description: z.string().nullable().optional(),
  manufacturer: z.string().nullable().optional(),
  specs: z.record(z.any()).nullable().optional(),
  unit: z.string().default("Stk"),
  categoryId: z.string().nullable().optional(),
  locationId: z.string().nullable().optional(),
  minQuantity: z.coerce.number().min(0).default(0),
  initialQuantity: z.coerce.number().min(0).nullable().optional(),
  usePendingPhoto: z.boolean().optional(),
  barcode: z.string().nullable().optional(),
});

const bookMovementOpSchema = z.object({
  kind: z.literal("book_movement"),
  itemId: z.string(),
  movementType: z.enum(["IN", "OUT", "RETURN", "CORRECTION"]),
  quantity: z.coerce.number(),
  projectId: z.string().nullable().optional(),
  reason: z.string().nullable().optional(),
});

const confirmSchema = z.object({
  operations: z.array(z.discriminatedUnion("kind", [createItemOpSchema, bookMovementOpSchema])).min(1),
});

export default async function aiRoutes(fastify: FastifyInstance) {
  fastify.addHook("preHandler", fastify.requireAuth);

  fastify.post("/api/ai/photo", async (request, reply) => {
    const file = await request.file();
    if (!file) return reply.code(400).send({ error: "Keine Datei übermittelt" });

    const buffer = await file.toBuffer();
    const base64 = buffer.toString("base64");

    await mkdir(env.photoStorageDir, { recursive: true });
    const pendingFilename = `pending-${randomUUID()}.jpg`;
    const { writeFile } = await import("node:fs/promises");
    await writeFile(path.join(env.photoStorageDir, pendingFilename), buffer);

    try {
      const proposal = await analyzePhoto(base64, file.mimetype);
      const capture = await prisma.aiCapture.create({
        data: {
          userId: request.session.userId!,
          sourceType: "PHOTO",
          rawInput: pendingFilename,
          proposedAction: proposal,
          status: "PENDING",
        },
      });
      return { capture, proposal };
    } catch (err) {
      await unlink(path.join(env.photoStorageDir, pendingFilename)).catch(() => undefined);
      throw err;
    }
  });

  fastify.post("/api/ai/text", async (request) => {
    const { text } = textRequestSchema.parse(request.body);
    const proposal = await parseFreeText(text);
    const capture = await prisma.aiCapture.create({
      data: {
        userId: request.session.userId!,
        sourceType: "TEXT",
        rawInput: text,
        proposedAction: proposal,
        status: "PENDING",
      },
    });
    return { capture, proposal };
  });

  fastify.post("/api/ai/voice", async (request) => {
    const file = await request.file();
    if (!file) throw new Error("Keine Audiodatei übermittelt");
    const buffer = await file.toBuffer();

    const transcript = await transcribeAudio(buffer, file.filename, file.mimetype);
    const proposal = await parseFreeText(transcript);
    const capture = await prisma.aiCapture.create({
      data: {
        userId: request.session.userId!,
        sourceType: "VOICE",
        rawInput: transcript,
        proposedAction: proposal,
        status: "PENDING",
      },
    });
    return { capture, proposal, transcript };
  });

  fastify.get("/api/ai/captures", async (request) => {
    const { status } = request.query as { status?: string };
    return prisma.aiCapture.findMany({
      where: status ? { status: status as never } : undefined,
      orderBy: { createdAt: "desc" },
      take: 100,
    });
  });

  fastify.post("/api/ai/captures/:id/reject", async (request, reply) => {
    const { id } = request.params as { id: string };
    const capture = await prisma.aiCapture.findUnique({ where: { id } });
    if (!capture) return reply.code(404).send({ error: "Erfassung nicht gefunden" });
    return prisma.aiCapture.update({ where: { id }, data: { status: "REJECTED" } });
  });

  // Confirmation is mandatory before anything below touches Item/StockMovement data (requirement #14):
  // this is the only place proposals from analyzePhoto/parseFreeText turn into real records.
  fastify.post("/api/ai/captures/:id/confirm", async (request, reply) => {
    const { id } = request.params as { id: string };
    const capture = await prisma.aiCapture.findUnique({ where: { id } });
    if (!capture) return reply.code(404).send({ error: "Erfassung nicht gefunden" });
    if (capture.status !== "PENDING") {
      return reply.code(409).send({ error: "Erfassung wurde bereits bearbeitet" });
    }

    const { operations } = confirmSchema.parse(request.body);
    const userId = request.session.userId!;

    let resultItemId: string | null = null;
    let resultMovementId: string | null = null;
    const wasEdited =
      JSON.stringify(operations) !== JSON.stringify((capture.proposedAction as { operations?: unknown })?.operations);

    for (const op of operations) {
      if (op.kind === "create_item") {
        const item = await prisma.item.create({
          data: {
            name: op.name,
            description: op.description ?? undefined,
            manufacturer: op.manufacturer ?? undefined,
            specs: op.specs ?? undefined,
            unit: op.unit,
            categoryId: op.categoryId ?? undefined,
            locationId: op.locationId ?? undefined,
            minQuantity: op.minQuantity,
            barcode: op.barcode ?? undefined,
          },
        });
        resultItemId = item.id;

        if (op.usePendingPhoto && capture.sourceType === "PHOTO") {
          const finalName = `${item.id}-${randomUUID()}.jpg`;
          await rename(
            path.join(env.photoStorageDir, capture.rawInput),
            path.join(env.photoStorageDir, finalName)
          );
          await prisma.item.update({ where: { id: item.id }, data: { photoPath: finalName } });
        }

        if (op.initialQuantity && op.initialQuantity > 0) {
          const movement = await bookMovement({
            itemId: item.id,
            type: "IN",
            quantity: op.initialQuantity,
            userId,
            reason: "Erfassung über KI-Vorschlag",
          });
          resultMovementId = movement.id;
        }
      } else {
        try {
          const movement = await bookMovement({
            itemId: op.itemId,
            type: op.movementType,
            quantity: op.quantity,
            projectId: op.projectId ?? null,
            reason: op.reason ?? "Erfassung über KI-Vorschlag",
            userId,
          });
          resultMovementId = movement.id;
        } catch (err) {
          if (err instanceof MovementError) {
            return reply.code(422).send({ error: err.message });
          }
          throw err;
        }
      }
    }

    return prisma.aiCapture.update({
      where: { id },
      data: {
        status: wasEdited ? "EDITED" : "CONFIRMED",
        resultItemId,
        resultMovementId,
        confirmedAt: new Date(),
      },
    });
  });
}
