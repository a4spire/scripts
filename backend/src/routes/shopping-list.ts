import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { Prisma } from "@prisma/client";
import { prisma } from "../lib/prisma.js";

const createSchema = z.object({
  itemId: z.string().nullable().optional(),
  customName: z.string().nullable().optional(),
  quantity: z.coerce.number().positive(),
  note: z.string().nullable().optional(),
});

const updateSchema = z.object({
  status: z.enum(["OPEN", "ORDERED", "DONE"]).optional(),
  quantity: z.coerce.number().positive().optional(),
  note: z.string().nullable().optional(),
});

export default async function shoppingListRoutes(fastify: FastifyInstance) {
  fastify.addHook("preHandler", fastify.requireAuth);

  fastify.get("/api/shopping-list", async (request) => {
    const { status } = request.query as { status?: string };
    return prisma.shoppingListItem.findMany({
      where: status ? { status: status as never } : undefined,
      include: { item: { include: { location: true } } },
      orderBy: { createdAt: "asc" },
    });
  });

  // Adds one OPEN entry per item currently at/under its minimum stock that isn't already
  // on the list as OPEN/ORDERED — safe to call repeatedly (e.g. from a "Vorschläge holen" button).
  fastify.post("/api/shopping-list/generate", async () => {
    const items = await prisma.item.findMany();
    const lowStock = items.filter((item) => new Prisma.Decimal(item.quantity).lte(item.minQuantity));

    const existing = await prisma.shoppingListItem.findMany({
      where: { status: { in: ["OPEN", "ORDERED"] }, itemId: { not: null } },
      select: { itemId: true },
    });
    const alreadyListed = new Set(existing.map((e) => e.itemId));

    const toCreate = lowStock.filter((item) => !alreadyListed.has(item.id));
    if (toCreate.length === 0) return { created: 0 };

    await prisma.shoppingListItem.createMany({
      data: toCreate.map((item) => {
        const deficit = new Prisma.Decimal(item.minQuantity).minus(item.quantity);
        const suggested = deficit.greaterThan(0) ? deficit : new Prisma.Decimal(item.minQuantity);
        return {
          itemId: item.id,
          quantity: (suggested.greaterThan(0) ? suggested : new Prisma.Decimal(1)).toString(),
          note: "Automatisch aus Mindestbestand-Unterschreitung",
        };
      }),
    });

    return { created: toCreate.length };
  });

  fastify.post("/api/shopping-list", async (request, reply) => {
    const body = createSchema.parse(request.body);
    if (!body.itemId && !body.customName) {
      return reply.code(422).send({ error: "Entweder itemId oder customName muss gesetzt sein" });
    }
    return prisma.shoppingListItem.create({
      data: {
        itemId: body.itemId ?? null,
        customName: body.customName ?? null,
        quantity: body.quantity,
        note: body.note ?? null,
      },
    });
  });

  fastify.patch("/api/shopping-list/:id", async (request) => {
    const { id } = request.params as { id: string };
    const body = updateSchema.parse(request.body);
    const resolvedAt = body.status && body.status !== "OPEN" ? new Date() : body.status === "OPEN" ? null : undefined;
    return prisma.shoppingListItem.update({
      where: { id },
      data: { ...body, resolvedAt },
    });
  });

  fastify.delete("/api/shopping-list/:id", async (request, reply) => {
    const { id } = request.params as { id: string };
    await prisma.shoppingListItem.delete({ where: { id } });
    return reply.code(204).send();
  });

  fastify.get("/api/shopping-list/export", async (request, reply) => {
    const entries = await prisma.shoppingListItem.findMany({
      where: { status: { in: ["OPEN", "ORDERED"] } },
      include: { item: true },
      orderBy: { createdAt: "asc" },
    });

    const header = ["Artikel", "Menge", "Einheit", "Notiz", "Status"];
    const rows = entries.map((e) => [
      e.item?.name ?? e.customName ?? "",
      e.quantity.toString(),
      e.item?.unit ?? "",
      e.note ?? "",
      e.status,
    ]);
    const csvEscape = (v: string) => (/[;"\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
    const csv = [header, ...rows].map((row) => row.map(csvEscape).join(";")).join("\r\n");

    return reply
      .header("Content-Type", "text/csv; charset=utf-8")
      .header("Content-Disposition", 'attachment; filename="einkaufsliste.csv"')
      .send(`﻿${csv}`);
  });
}
