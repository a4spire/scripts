import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { prisma } from "../lib/prisma.js";
import { bookMovement, transferBetweenProjects, MovementError } from "../services/movement-service.js";
import { userPublicSelect } from "../lib/selects.js";

const bookSchema = z.object({
  itemId: z.string(),
  type: z.enum(["IN", "OUT", "RETURN", "CORRECTION"]),
  quantity: z.coerce.number(),
  projectId: z.string().nullable().optional(),
  reason: z.string().nullable().optional(),
});

const transferSchema = z.object({
  itemId: z.string(),
  quantity: z.coerce.number().positive(),
  fromProjectId: z.string().nullable(),
  toProjectId: z.string().nullable(),
  reason: z.string().nullable().optional(),
});

export default async function movementRoutes(fastify: FastifyInstance) {
  fastify.addHook("preHandler", fastify.requireAuth);

  fastify.get("/api/movements", async (request) => {
    const { itemId, projectId } = request.query as { itemId?: string; projectId?: string };
    return prisma.stockMovement.findMany({
      where: {
        itemId: itemId ?? undefined,
        projectId: projectId ?? undefined,
      },
      include: { item: true, project: true, user: { select: userPublicSelect } },
      orderBy: { createdAt: "desc" },
      take: 200,
    });
  });

  fastify.post("/api/movements", async (request, reply) => {
    const body = bookSchema.parse(request.body);
    try {
      const movement = await bookMovement({
        ...body,
        userId: request.session.userId!,
      });
      return movement;
    } catch (err) {
      if (err instanceof MovementError) {
        return reply.code(422).send({ error: err.message });
      }
      throw err;
    }
  });

  fastify.post("/api/movements/transfer", async (request, reply) => {
    const body = transferSchema.parse(request.body);
    try {
      return await transferBetweenProjects({
        ...body,
        userId: request.session.userId!,
      });
    } catch (err) {
      if (err instanceof MovementError) {
        return reply.code(422).send({ error: err.message });
      }
      throw err;
    }
  });
}
