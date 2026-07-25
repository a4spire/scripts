import { PDFDocument, StandardFonts, rgb } from "pdf-lib";

interface ExportMovement {
  type: string;
  quantity: { toString(): string };
  createdAt: Date;
  reason: string | null;
  projectId?: string | null;
  item: { name: string; unit: string };
  user: { displayName: string };
}

interface ExportProject {
  name: string;
  description: string | null;
  status: string;
  createdAt: Date;
  completedAt: Date | null;
  totalCost: string;
  movements: ExportMovement[];
}

const MOVEMENT_TYPE_LABELS: Record<string, string> = {
  IN: "Eingang",
  OUT: "Entnahme",
  RETURN: "Rückgabe",
  CORRECTION: "Korrektur",
};

const STATUS_LABELS: Record<string, string> = {
  ACTIVE: "Aktiv",
  COMPLETED: "Abgeschlossen",
  ARCHIVED: "Archiviert",
};

function formatDate(date: Date): string {
  return date.toLocaleDateString("de-DE") + " " + date.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}

function csvEscape(value: string): string {
  if (/[;"\n]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

export function generateProjectCsv(project: ExportProject): string {
  const header = ["Datum", "Typ", "Artikel", "Menge", "Einheit", "Grund", "Nutzer"];
  const rows = project.movements.map((m) => [
    formatDate(m.createdAt),
    MOVEMENT_TYPE_LABELS[m.type] ?? m.type,
    m.item.name,
    m.quantity.toString(),
    m.item.unit,
    m.reason ?? "",
    m.user.displayName,
  ]);

  const lines = [header, ...rows].map((row) => row.map(csvEscape).join(";"));
  lines.push("");
  lines.push(`Materialkosten (Summe);${project.totalCost} EUR`);
  return lines.join("\r\n");
}

const PAGE_WIDTH = 595.28;
const PAGE_HEIGHT = 841.89;
const MARGIN = 50;
const COLUMNS = [
  { label: "Datum", width: 95 },
  { label: "Typ", width: 65 },
  { label: "Artikel", width: 165 },
  { label: "Menge", width: 60 },
  { label: "Grund", width: 110 },
];

export async function generateProjectPdf(project: ExportProject): Promise<Uint8Array> {
  const doc = await PDFDocument.create();
  const font = await doc.embedFont(StandardFonts.Helvetica);
  const boldFont = await doc.embedFont(StandardFonts.HelveticaBold);

  let page = doc.addPage([PAGE_WIDTH, PAGE_HEIGHT]);
  let y = PAGE_HEIGHT - MARGIN;

  function newPage() {
    page = doc.addPage([PAGE_WIDTH, PAGE_HEIGHT]);
    y = PAGE_HEIGHT - MARGIN;
  }

  function ensureSpace(needed: number) {
    if (y - needed < MARGIN) newPage();
  }

  function text(value: string, x: number, size: number, useBold = false, color = rgb(0, 0, 0)) {
    page.drawText(value, { x, y, size, font: useBold ? boldFont : font, color });
  }

  text(project.name, MARGIN, 20, true);
  y -= 26;
  text(`Status: ${STATUS_LABELS[project.status] ?? project.status}`, MARGIN, 10, false, rgb(0.35, 0.35, 0.35));
  y -= 14;
  text(`Angelegt: ${formatDate(project.createdAt)}`, MARGIN, 10, false, rgb(0.35, 0.35, 0.35));
  if (project.completedAt) {
    y -= 14;
    text(`Abgeschlossen: ${formatDate(project.completedAt)}`, MARGIN, 10, false, rgb(0.35, 0.35, 0.35));
  }
  y -= 20;
  if (project.description) {
    const words = project.description.split(/\s+/);
    let line = "";
    const maxWidth = PAGE_WIDTH - 2 * MARGIN;
    for (const word of words) {
      const candidate = line ? `${line} ${word}` : word;
      if (font.widthOfTextAtSize(candidate, 10) > maxWidth) {
        text(line, MARGIN, 10);
        y -= 14;
        line = word;
      } else {
        line = candidate;
      }
    }
    if (line) {
      text(line, MARGIN, 10);
      y -= 14;
    }
    y -= 10;
  }

  function drawTableHeader() {
    ensureSpace(24);
    let x = MARGIN;
    for (const col of COLUMNS) {
      text(col.label, x, 10, true);
      x += col.width;
    }
    y -= 8;
    page.drawLine({
      start: { x: MARGIN, y },
      end: { x: PAGE_WIDTH - MARGIN, y },
      thickness: 0.5,
      color: rgb(0.7, 0.7, 0.7),
    });
    y -= 14;
  }

  drawTableHeader();

  for (const m of project.movements) {
    ensureSpace(16);
    let x = MARGIN;
    const values = [
      formatDate(m.createdAt),
      MOVEMENT_TYPE_LABELS[m.type] ?? m.type,
      m.item.name.slice(0, 28),
      `${m.quantity.toString()} ${m.item.unit}`,
      (m.reason ?? "").slice(0, 22),
    ];
    values.forEach((value, i) => {
      text(value, x, 9);
      x += COLUMNS[i].width;
    });
    y -= 16;
  }

  if (project.movements.length === 0) {
    text("Noch keine Bewegungen.", MARGIN, 10, false, rgb(0.5, 0.5, 0.5));
    y -= 16;
  }

  ensureSpace(30);
  y -= 10;
  page.drawLine({
    start: { x: MARGIN, y },
    end: { x: PAGE_WIDTH - MARGIN, y },
    thickness: 0.5,
    color: rgb(0.7, 0.7, 0.7),
  });
  y -= 20;
  text(`Materialkosten (Summe): ${project.totalCost} EUR`, MARGIN, 12, true);

  return doc.save();
}
