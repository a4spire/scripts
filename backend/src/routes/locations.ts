import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { randomBytes } from "node:crypto";
import { prisma } from "../lib/prisma.js";

const locationSchema = z.object({
  name: z.string().min(1),
  type: z.enum(["WERKSTATT", "REGAL", "FACH", "BOX", "SONSTIGE"]).default("SONSTIGE"),
  parentId: z.string().nullable().optional(),
});

export default async function locationRoutes(fastify: FastifyInstance) {
  fastify.addHook("preHandler", fastify.requireAuth);

  fastify.get("/api/locations", async () => {
    return prisma.location.findMany({ orderBy: { name: "asc" } });
  });

  fastify.get("/api/locations/qr/:code", async (request, reply) => {
    const { code } = request.params as { code: string };
    const location = await prisma.location.findUnique({ where: { qrCode: code } });
    if (!location) return reply.code(404).send({ error: "Kein Lagerort mit diesem Code gefunden" });
    return location;
  });

  fastify.get("/api/locations/:id", async (request, reply) => {
    const { id } = request.params as { id: string };
    const location = await prisma.location.findUnique({
      where: { id },
      include: { children: true, items: true },
    });
    if (!location) return reply.code(404).send({ error: "Lagerort nicht gefunden" });
    return location;
  });

  fastify.post("/api/locations", async (request) => {
    const body = locationSchema.parse(request.body);
    return prisma.location.create({
      data: {
        ...body,
        qrCode: randomBytes(6).toString("hex"),
      },
    });
  });

  fastify.patch("/api/locations/:id", async (request) => {
    const { id } = request.params as { id: string };
    const body = locationSchema.partial().parse(request.body);
    return prisma.location.update({ where: { id }, data: body });
  });

  fastify.delete("/api/locations/:id", async (request, reply) => {
    const { id } = request.params as { id: string };
    await prisma.location.delete({ where: { id } });
    return reply.code(204).send();
  });
}
