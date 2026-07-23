import type { FastifyInstance } from "fastify";
import { z } from "zod";
import argon2 from "argon2";
import { prisma } from "../lib/prisma.js";

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

export default async function authRoutes(fastify: FastifyInstance) {
  fastify.post("/api/auth/login", async (request, reply) => {
    const body = loginSchema.parse(request.body);

    const user = await prisma.user.findUnique({ where: { email: body.email } });
    if (!user) {
      return reply.code(401).send({ error: "E-Mail oder Passwort falsch" });
    }

    const valid = await argon2.verify(user.passwordHash, body.password);
    if (!valid) {
      return reply.code(401).send({ error: "E-Mail oder Passwort falsch" });
    }

    request.session.userId = user.id;
    return {
      id: user.id,
      email: user.email,
      displayName: user.displayName,
      role: user.role,
    };
  });

  fastify.post("/api/auth/logout", async (request, reply) => {
    await request.session.destroy();
    return reply.code(204).send();
  });

  fastify.get("/api/auth/me", { preHandler: fastify.requireAuth }, async (request) => {
    const user = await prisma.user.findUniqueOrThrow({ where: { id: request.session.userId } });
    return {
      id: user.id,
      email: user.email,
      displayName: user.displayName,
      role: user.role,
    };
  });
}
