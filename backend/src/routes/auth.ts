import type { FastifyInstance } from "fastify";
import { z } from "zod";
import argon2 from "argon2";
import { Prisma } from "@prisma/client";
import { prisma } from "../lib/prisma.js";

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

const updateMeSchema = z
  .object({
    displayName: z.string().min(1).optional(),
    email: z.string().email().optional(),
    currentPassword: z.string().optional(),
    newPassword: z.string().min(8).optional(),
  })
  .refine((data) => !(data.email !== undefined && !data.currentPassword), {
    message: "Aktuelles Passwort erforderlich, um die E-Mail zu ändern",
    path: ["currentPassword"],
  })
  .refine((data) => !(data.newPassword !== undefined && !data.currentPassword), {
    message: "Aktuelles Passwort erforderlich, um das Passwort zu ändern",
    path: ["currentPassword"],
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

  fastify.patch("/api/auth/me", { preHandler: fastify.requireAuth }, async (request, reply) => {
    const body = updateMeSchema.parse(request.body);
    const user = await prisma.user.findUniqueOrThrow({ where: { id: request.session.userId } });

    if (body.currentPassword) {
      const valid = await argon2.verify(user.passwordHash, body.currentPassword);
      if (!valid) {
        return reply.code(401).send({ error: "Aktuelles Passwort ist falsch" });
      }
    }

    const data: { displayName?: string; email?: string; passwordHash?: string } = {};
    if (body.displayName !== undefined) data.displayName = body.displayName;
    if (body.email !== undefined) data.email = body.email;
    if (body.newPassword !== undefined) data.passwordHash = await argon2.hash(body.newPassword);

    try {
      const updated = await prisma.user.update({ where: { id: user.id }, data });
      return {
        id: updated.id,
        email: updated.email,
        displayName: updated.displayName,
        role: updated.role,
      };
    } catch (err) {
      if (err instanceof Prisma.PrismaClientKnownRequestError && err.code === "P2002") {
        return reply.code(409).send({ error: "Diese E-Mail wird bereits verwendet" });
      }
      throw err;
    }
  });
}
