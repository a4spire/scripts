import { PDFDocument, StandardFonts, rgb } from "pdf-lib";
import QRCode from "qrcode";

interface LabelLocation {
  id: string;
  name: string;
  qrCode: string | null;
  parentId: string | null;
}

const PAGE_WIDTH = 595.28;
const PAGE_HEIGHT = 841.89;
const MARGIN = 28;
const COLUMNS = 3;
const ROWS = 8;
const CELL_WIDTH = (PAGE_WIDTH - 2 * MARGIN) / COLUMNS;
const CELL_HEIGHT = (PAGE_HEIGHT - 2 * MARGIN) / ROWS;
const QR_SIZE = 60;
const CELL_PADDING = 8;

function pathFor(location: LabelLocation, byId: Map<string, LabelLocation>): string {
  const parts: string[] = [location.name];
  let current = location;
  while (current.parentId) {
    const parent = byId.get(current.parentId);
    if (!parent) break;
    parts.unshift(parent.name);
    current = parent;
  }
  return parts.join(" > ");
}

function truncate(font: { widthOfTextAtSize(text: string, size: number): number }, text: string, size: number, maxWidth: number): string {
  if (font.widthOfTextAtSize(text, size) <= maxWidth) return text;
  let result = text;
  while (result.length > 1 && font.widthOfTextAtSize(`${result}…`, size) > maxWidth) {
    result = result.slice(0, -1);
  }
  return `${result}…`;
}

export async function generateLocationLabelsPdf(
  locations: LabelLocation[],
  allLocations: LabelLocation[] = locations
): Promise<Uint8Array> {
  const byId = new Map(allLocations.map((l) => [l.id, l]));
  const doc = await PDFDocument.create();
  const font = await doc.embedFont(StandardFonts.Helvetica);
  const boldFont = await doc.embedFont(StandardFonts.HelveticaBold);

  let page = doc.addPage([PAGE_WIDTH, PAGE_HEIGHT]);
  let cellIndex = 0;

  function cellOrigin(index: number) {
    const col = index % COLUMNS;
    const row = Math.floor(index / COLUMNS) % ROWS;
    return {
      x: MARGIN + col * CELL_WIDTH,
      y: PAGE_HEIGHT - MARGIN - (row + 1) * CELL_HEIGHT,
    };
  }

  for (const location of locations) {
    if (cellIndex > 0 && cellIndex % (COLUMNS * ROWS) === 0) {
      page = doc.addPage([PAGE_WIDTH, PAGE_HEIGHT]);
    }
    const { x, y } = cellOrigin(cellIndex % (COLUMNS * ROWS));

    page.drawRectangle({
      x: x + 2,
      y: y + 2,
      width: CELL_WIDTH - 4,
      height: CELL_HEIGHT - 4,
      borderColor: rgb(0.8, 0.8, 0.8),
      borderWidth: 0.5,
    });

    if (location.qrCode) {
      const qrDataUrl = await QRCode.toDataURL(location.qrCode, { margin: 0, width: 256 });
      const qrImage = await doc.embedPng(qrDataUrl);
      page.drawImage(qrImage, {
        x: x + CELL_PADDING,
        y: y + (CELL_HEIGHT - QR_SIZE) / 2,
        width: QR_SIZE,
        height: QR_SIZE,
      });
    }

    const textX = x + CELL_PADDING + QR_SIZE + 10;
    const textMaxWidth = CELL_WIDTH - CELL_PADDING * 2 - QR_SIZE - 10;
    let textY = y + CELL_HEIGHT / 2 + 14;

    page.drawText(truncate(boldFont, location.name, 11, textMaxWidth), {
      x: textX,
      y: textY,
      size: 11,
      font: boldFont,
    });
    textY -= 14;

    const path = pathFor(location, byId);
    if (path !== location.name) {
      page.drawText(truncate(font, path, 7, textMaxWidth), {
        x: textX,
        y: textY,
        size: 7,
        font,
        color: rgb(0.4, 0.4, 0.4),
      });
      textY -= 11;
    }

    if (location.qrCode) {
      page.drawText(location.qrCode, {
        x: textX,
        y: textY,
        size: 7,
        font,
        color: rgb(0.55, 0.55, 0.55),
      });
    }

    cellIndex += 1;
  }

  return doc.save();
}
