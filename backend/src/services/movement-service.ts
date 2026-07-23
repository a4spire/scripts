import { Prisma, MovementType } from "@prisma/client";
import { prisma } from "../lib/prisma.js";

export class MovementError extends Error {}

interface BookMovementInput {
  itemId: string;
  type: MovementType;
  quantity: number;
  userId: string;
  projectId?: string | null;
  reason?: string | null;
}

/**
 * Signed delta applied to Item.quantity for each movement type.
 * IN/RETURN increase stock, OUT decreases it, CORRECTION sets an explicit signed delta.
 */
function signedDelta(type: MovementType, quantity: number): number {
  switch (type) {
    case "IN":
    case "RETURN":
      return Math.abs(quantity);
    case "OUT":
      return -Math.abs(quantity);
    case "CORRECTION":
      return quantity;
    default:
      throw new MovementError(`Unbekannter Bewegungstyp: ${type}`);
  }
}

export async function bookMovement(input: BookMovementInput) {
  return prisma.$transaction(async (tx) => {
    const item = await tx.item.findUnique({ where: { id: input.itemId } });
    if (!item) {
      throw new MovementError("Artikel nicht gefunden");
    }

    const delta = signedDelta(input.type, input.quantity);
    const newQuantity = new Prisma.Decimal(item.quantity).plus(delta);

    if (newQuantity.lessThan(0)) {
      throw new MovementError(
        `Bestand kann nicht negativ werden (aktuell ${item.quantity}, Änderung ${delta})`
      );
    }

    const movement = await tx.stockMovement.create({
      data: {
        itemId: input.itemId,
        type: input.type,
        quantity: input.quantity,
        projectId: input.projectId ?? null,
        userId: input.userId,
        reason: input.reason ?? null,
      },
    });

    await tx.item.update({
      where: { id: input.itemId },
      data: { quantity: newQuantity },
    });

    return movement;
  });
}

interface TransferBetweenProjectsInput {
  itemId: string;
  quantity: number;
  userId: string;
  fromProjectId: string | null;
  toProjectId: string | null;
  reason?: string | null;
}

/**
 * Moves material between projects (or back to general stock) without changing
 * Item.quantity: a RETURN against the source project followed by an OUT
 * against the destination keeps "sum of movements == current stock" intact.
 */
export async function transferBetweenProjects(input: TransferBetweenProjectsInput) {
  return prisma.$transaction(async (tx) => {
    const returnMovement = await tx.stockMovement.create({
      data: {
        itemId: input.itemId,
        type: "RETURN",
        quantity: input.quantity,
        projectId: input.fromProjectId,
        userId: input.userId,
        reason: input.reason ?? "Umbuchung zwischen Projekten",
      },
    });

    const outMovement = await tx.stockMovement.create({
      data: {
        itemId: input.itemId,
        type: "OUT",
        quantity: input.quantity,
        projectId: input.toProjectId,
        userId: input.userId,
        reason: input.reason ?? "Umbuchung zwischen Projekten",
      },
    });

    return { returnMovement, outMovement };
  });
}
