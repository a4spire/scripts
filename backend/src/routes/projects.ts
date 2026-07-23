import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { Prisma } from "@prisma/client";
import { prisma } from "../lib/prisma.js";
import { userPublicSelect } from "../lib/selects.js";

const projectSchema = z.object({
  name: z.string().min(1),
  description: z.string().nullable().optional(),
  status: z.enum(["ACTIVE", "COMPLETED", "ARCHIVED"]).default("ACTIVE"),
});

export default async function projectRoutes(fastify: FastifyInstance) {
  fastify.addHook("preHandler", fastify.requireAuth);

  fastify.get("/api/projects", async (request) => {
    const { status } = request.query as { status?: string };
    return prisma.project.findMany({
      where: status ? { status: status as never } : undefined,
      orderBy: { createdAt: "desc" },
    });
  });

  fastify.get("/api/projects/:id", async (request, reply) => {
    const { id } = request.params as { id: string };
    const project = await prisma.project.findUnique({
      where: { id },
      include: {
        movements: {
          orderBy: { createdAt: "desc" },
          include: { item: true, user: { select: userPublicSelect } },
        },
      },
    });
    if (!project) return reply.code(404).send({ error: "Projekt nicht gefunden" });

    // Materialkosten-Summe: nur OUT-Bewegungen abzüglich RETURN, bewertet mit dem
    // aktuellen Einkaufspreis des Artikels (kein historischer Preis in v1).
    let totalCost = new Prisma.Decimal(0);
    for (const movement of project.movements) {
      if (!movement.item.purchasePrice) continue;
      const price = new Prisma.Decimal(movement.item.purchasePrice);
      if (movement.type === "OUT") {
        totalCost = totalCost.plus(price.times(movement.quantity));
      } else if (movement.type === "RETURN") {
        totalCost = totalCost.minus(price.times(movement.quantity));
      }
    }

    return { ...project, totalCost: totalCost.toFixed(2) };
  });

  fastify.post("/api/projects", async (request) => {
    const body = projectSchema.parse(request.body);
    return prisma.project.create({ data: body });
  });

  fastify.patch("/api/projects/:id", async (request) => {
    const { id } = request.params as { id: string };
    const body = projectSchema.partial().parse(request.body);
    const data = {
      ...body,
      completedAt: body.status === "COMPLETED" ? new Date() : undefined,
    };
    return prisma.project.update({ where: { id }, data });
  });

  fastify.delete("/api/projects/:id", async (request, reply) => {
    const { id } = request.params as { id: string };
    await prisma.project.delete({ where: { id } });
    return reply.code(204).send();
  });
}
