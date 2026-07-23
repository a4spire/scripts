import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { prisma } from "../lib/prisma.js";

const categorySchema = z.object({
  name: z.string().min(1),
  parentId: z.string().nullable().optional(),
});

export default async function categoryRoutes(fastify: FastifyInstance) {
  fastify.addHook("preHandler", fastify.requireAuth);

  fastify.get("/api/categories", async () => {
    return prisma.category.findMany({ orderBy: { name: "asc" } });
  });

  fastify.post("/api/categories", async (request) => {
    const body = categorySchema.parse(request.body);
    return prisma.category.create({ data: body });
  });

  fastify.patch("/api/categories/:id", async (request) => {
    const { id } = request.params as { id: string };
    const body = categorySchema.partial().parse(request.body);
    return prisma.category.update({ where: { id }, data: body });
  });

  fastify.delete("/api/categories/:id", async (request, reply) => {
    const { id } = request.params as { id: string };
    await prisma.category.delete({ where: { id } });
    return reply.code(204).send();
  });
}
