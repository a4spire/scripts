import fp from "fastify-plugin";
import cookie from "@fastify/cookie";
import session from "@fastify/session";
import type { FastifyInstance, FastifyReply, FastifyRequest } from "fastify";
import { env } from "../lib/env.js";

declare module "fastify" {
  interface Session {
    userId?: string;
  }
  interface FastifyInstance {
    requireAuth: (request: FastifyRequest, reply: FastifyReply) => Promise<void>;
  }
}

export default fp(async function authPlugin(fastify: FastifyInstance) {
  await fastify.register(cookie);
  await fastify.register(session, {
    secret: env.sessionSecret,
    cookieName: "werkstatt_session",
    cookie: {
      secure: env.nodeEnv === "production",
      httpOnly: true,
      sameSite: "lax",
      maxAge: 1000 * 60 * 60 * 24 * 30,
    },
  });

  fastify.decorate("requireAuth", async (request: FastifyRequest, reply: FastifyReply) => {
    if (!request.session.userId) {
      reply.code(401).send({ error: "Nicht angemeldet" });
    }
  });
});
