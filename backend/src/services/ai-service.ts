import Anthropic from "@anthropic-ai/sdk";
import { z } from "zod";
import { env } from "../lib/env.js";
import { prisma } from "../lib/prisma.js";

const anthropic = new Anthropic({ apiKey: env.anthropicApiKey });

export const proposedItemSchema = z.object({
  name: z.string(),
  categoryName: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  manufacturer: z.string().nullable().optional(),
  specs: z.record(z.string()).nullable().optional(),
  unit: z.string().default("Stk"),
});
export type ProposedItem = z.infer<typeof proposedItemSchema>;

export const photoProposalSchema = z.object({
  action: z.literal("create_item"),
  item: proposedItemSchema,
  confidence: z.number().min(0).max(1),
});
export type PhotoProposal = z.infer<typeof photoProposalSchema>;

const textActionSchema = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("create_item"),
    item: proposedItemSchema,
    locationName: z.string().nullable().optional(),
    initialQuantity: z.number().nullable().optional(),
  }),
  z.object({
    type: z.literal("book_movement"),
    itemId: z.string().nullable().optional(),
    itemName: z.string(),
    movementType: z.enum(["IN", "OUT", "RETURN", "CORRECTION"]),
    quantity: z.number(),
    projectName: z.string().nullable().optional(),
    reason: z.string().nullable().optional(),
  }),
]);
export type TextAction = z.infer<typeof textActionSchema>;

export const textProposalSchema = z.object({
  actions: z.array(textActionSchema).min(1),
  summary: z.string(),
});
export type TextProposal = z.infer<typeof textProposalSchema>;

const PHOTO_TOOL_NAME = "propose_item";
const TEXT_TOOL_NAME = "propose_actions";

async function loadContext() {
  const [items, locations, projects, categories] = await Promise.all([
    prisma.item.findMany({ select: { id: true, name: true }, take: 500 }),
    prisma.location.findMany({ select: { id: true, name: true } }),
    prisma.project.findMany({ where: { status: "ACTIVE" }, select: { id: true, name: true } }),
    prisma.category.findMany({ select: { id: true, name: true } }),
  ]);
  return { items, locations, projects, categories };
}

export async function analyzePhoto(base64Image: string, mimeType: string): Promise<PhotoProposal> {
  const { categories } = await loadContext();

  const response = await anthropic.messages.create({
    model: env.anthropicModel,
    max_tokens: 1024,
    system:
      "Du hilfst beim Erfassen von Werkstatt-/Lagerartikeln anhand eines Fotos. " +
      "Schlage Name, Kategorie, Beschreibung und ggf. technische Specs (z.B. Maße, Gewinde, Material) vor. " +
      `Bekannte Kategorien: ${categories.map((c) => c.name).join(", ") || "keine"}. ` +
      "Antworte ausschließlich über das Tool propose_item.",
    messages: [
      {
        role: "user",
        content: [
          { type: "image", source: { type: "base64", media_type: mimeType as never, data: base64Image } },
          { type: "text", text: "Analysiere dieses Werkstatt-Teil und schlage Stammdaten vor." },
        ],
      },
    ],
    tools: [
      {
        name: PHOTO_TOOL_NAME,
        description: "Strukturierter Vorschlag für einen neuen Lagerartikel basierend auf einem Foto.",
        input_schema: {
          type: "object",
          properties: {
            item: {
              type: "object",
              properties: {
                name: { type: "string" },
                categoryName: { type: ["string", "null"] },
                description: { type: ["string", "null"] },
                manufacturer: { type: ["string", "null"] },
                specs: { type: ["object", "null"] },
                unit: { type: "string" },
              },
              required: ["name", "unit"],
            },
            confidence: { type: "number", minimum: 0, maximum: 1 },
          },
          required: ["item", "confidence"],
        },
      },
    ],
    tool_choice: { type: "tool", name: PHOTO_TOOL_NAME },
  });

  const toolUse = response.content.find((block) => block.type === "tool_use");
  if (!toolUse || toolUse.type !== "tool_use") {
    throw new Error("Claude hat keinen strukturierten Vorschlag geliefert");
  }

  return photoProposalSchema.parse({ action: "create_item", ...(toolUse.input as object) });
}

export async function parseFreeText(text: string): Promise<TextProposal> {
  const { items, locations, projects, categories } = await loadContext();

  const response = await anthropic.messages.create({
    model: env.anthropicModel,
    max_tokens: 1536,
    system:
      "Du parst natürlichsprachliche Eingaben aus einer Werkstatt-Lagerverwaltung in strukturierte Aktionen. " +
      "Jede Aktion ist entweder 'create_item' (neuer Artikel, optional mit Erstbestand) oder 'book_movement' " +
      "(Bestandsbewegung IN/OUT/RETURN/CORRECTION für einen existierenden Artikel). " +
      "Wenn sich der genannte Artikel eindeutig einem bekannten Artikel zuordnen lässt, setze itemId. " +
      `Bekannte Artikel: ${items.map((i) => `${i.name} (id=${i.id})`).join(", ") || "keine"}. ` +
      `Bekannte Lagerorte: ${locations.map((l) => l.name).join(", ") || "keine"}. ` +
      `Bekannte aktive Projekte: ${projects.map((p) => p.name).join(", ") || "keine"}. ` +
      `Bekannte Kategorien: ${categories.map((c) => c.name).join(", ") || "keine"}. ` +
      "Antworte ausschließlich über das Tool propose_actions. Erfinde keine IDs.",
    messages: [{ role: "user", content: text }],
    tools: [
      {
        name: TEXT_TOOL_NAME,
        description: "Strukturierte Liste vorgeschlagener Lager-Aktionen aus einer Freitext-Eingabe.",
        input_schema: {
          type: "object",
          properties: {
            summary: { type: "string" },
            actions: {
              type: "array",
              items: {
                type: "object",
                properties: {
                  type: { type: "string", enum: ["create_item", "book_movement"] },
                  item: {
                    type: "object",
                    properties: {
                      name: { type: "string" },
                      categoryName: { type: ["string", "null"] },
                      description: { type: ["string", "null"] },
                      manufacturer: { type: ["string", "null"] },
                      specs: { type: ["object", "null"] },
                      unit: { type: "string" },
                    },
                  },
                  locationName: { type: ["string", "null"] },
                  initialQuantity: { type: ["number", "null"] },
                  itemId: { type: ["string", "null"] },
                  itemName: { type: "string" },
                  movementType: { type: "string", enum: ["IN", "OUT", "RETURN", "CORRECTION"] },
                  quantity: { type: "number" },
                  projectName: { type: ["string", "null"] },
                  reason: { type: ["string", "null"] },
                },
                required: ["type"],
              },
            },
          },
          required: ["summary", "actions"],
        },
      },
    ],
    tool_choice: { type: "tool", name: TEXT_TOOL_NAME },
  });

  const toolUse = response.content.find((block) => block.type === "tool_use");
  if (!toolUse || toolUse.type !== "tool_use") {
    throw new Error("Claude hat keinen strukturierten Vorschlag geliefert");
  }

  return textProposalSchema.parse(toolUse.input as object);
}

export async function transcribeAudio(audioBuffer: Buffer, filename: string, mimeType: string): Promise<string> {
  if (!env.whisperApiUrl) {
    throw new Error("WHISPER_API_URL ist nicht konfiguriert");
  }
  const form = new FormData();
  form.append("audio_file", new Blob([audioBuffer], { type: mimeType }), filename);

  const res = await fetch(`${env.whisperApiUrl}/asr?output=text`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    throw new Error(`Whisper-Transkription fehlgeschlagen: ${res.status}`);
  }
  return (await res.text()).trim();
}
