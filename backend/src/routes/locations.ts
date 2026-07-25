import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { randomBytes } from "node:crypto";
import { prisma } from "../lib/prisma.js";
import { generateLocationLabelsPdf } from "../services/labels-service.js";

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

  fastify.get("/api/locations/labels/pdf", async (request, reply) => {
    const { ids } = request.query as { ids?: string };
    const idList = ids ? ids.split(",").filter(Boolean) : undefined;

    const locations = await prisma.location.findMany({
      where: idList ? { id: { in: idList } } : undefined,
      orderBy: { name: "asc" },
    });
    if (locations.length === 0) {
      return reply.code(404).send({ error: "Keine Lagerorte für Label-Druck gefunden" });
    }

    // Breadcrumb-Pfade brauchen die volle Hierarchie, auch wenn nur eine Teilmenge gedruckt wird.
    const allLocations = idList ? await prisma.location.findMany() : locations;
    const toLabel = (l: (typeof locations)[number]) => ({
      id: l.id,
      name: l.name,
      qrCode: l.qrCode,
      parentId: l.parentId,
    });
    const pdfBytes = await generateLocationLabelsPdf(locations.map(toLabel), allLocations.map(toLabel));

    return reply
      .header("Content-Type", "application/pdf")
      .header("Content-Disposition", 'attachment; filename="lagerort-labels.pdf"')
      .send(Buffer.from(pdfBytes));
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
