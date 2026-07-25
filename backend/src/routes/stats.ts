import type { FastifyInstance } from "fastify";
import { Prisma } from "@prisma/client";
import { prisma } from "../lib/prisma.js";

interface TopItemRow {
  id: string;
  name: string;
  unit: string;
  totalOut: Prisma.Decimal;
}

interface ProjectCostRow {
  id: string;
  name: string;
  status: string;
  cost: Prisma.Decimal;
}

export default async function statsRoutes(fastify: FastifyInstance) {
  fastify.addHook("preHandler", fastify.requireAuth);

  fastify.get("/api/stats/overview", async () => {
    const items = await prisma.item.findMany({
      select: { quantity: true, purchasePrice: true },
    });
    let inventoryValue = new Prisma.Decimal(0);
    for (const item of items) {
      if (!item.purchasePrice) continue;
      inventoryValue = inventoryValue.plus(new Prisma.Decimal(item.quantity).times(item.purchasePrice));
    }

    const topItems = await prisma.$queryRaw<TopItemRow[]>`
      SELECT i.id, i.name, i.unit, SUM(m.quantity) AS "totalOut"
      FROM items i
      JOIN stock_movements m ON m."itemId" = i.id AND m.type = 'OUT'
      GROUP BY i.id, i.name, i.unit
      ORDER BY "totalOut" DESC
      LIMIT 10
    `;

    const projectCosts = await prisma.$queryRaw<ProjectCostRow[]>`
      SELECT p.id, p.name, p.status,
        COALESCE(SUM(
          CASE
            WHEN m.type = 'OUT' THEN m.quantity * COALESCE(i."purchasePrice", 0)
            WHEN m.type = 'RETURN' THEN -m.quantity * COALESCE(i."purchasePrice", 0)
            ELSE 0
          END
        ), 0) AS cost
      FROM projects p
      LEFT JOIN stock_movements m ON m."projectId" = p.id
      LEFT JOIN items i ON i.id = m."itemId"
      GROUP BY p.id, p.name, p.status
      ORDER BY cost DESC
      LIMIT 20
    `;

    return {
      inventoryValue: inventoryValue.toFixed(2),
      itemCount: items.length,
      topItems: topItems.map((row) => ({
        id: row.id,
        name: row.name,
        unit: row.unit,
        totalOut: row.totalOut.toString(),
      })),
      projectCosts: projectCosts.map((row) => ({
        id: row.id,
        name: row.name,
        status: row.status,
        cost: row.cost.toFixed(2),
      })),
    };
  });
}
