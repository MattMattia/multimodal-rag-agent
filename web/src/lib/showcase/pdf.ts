/**
 * Minimal, dependency-free PDF 1.4 writer (Helvetica, WinAnsiEncoding, A4, automatic pagination).
 * Every character is emitted as one Latin-1 byte, so string offsets equal byte offsets in the xref table.
 */

export interface PdfSection {
  heading?: string;
  lines: readonly string[];
}

export interface PdfDocumentSpec {
  title: string;
  subtitle?: string;
  sections: readonly PdfSection[];
  footer?: string;
}

const PAGE_WIDTH = 595;
const PAGE_HEIGHT = 842;
const MARGIN = 56;
const BODY_SIZE = 10.5;
const LINE_HEIGHT = 15;
const WRAP_COLUMNS = 92;

interface Line {
  text: string;
  size: number;
  bold: boolean;
  gapBefore: number;
}

/** Keep Latin-1 printable characters; map typographic characters to ASCII and anything else to "?". */
function toLatin1(text: string): string {
  return text
    .replace(/[‘’]/g, "'")
    .replace(/[“”]/g, '"')
    .replace(/[–—]/g, "-")
    .replace(/…/g, "...")
    .replace(/•/g, "-")
    .replace(/[^\x20-\x7E\xA0-\xFF]/g, "?");
}

function escapePdfText(text: string): string {
  return text.replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");
}

export function wrapText(text: string, columns: number = WRAP_COLUMNS): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    let rest = word;
    while (rest.length > columns) {
      if (current) {
        lines.push(current);
        current = "";
      }
      lines.push(rest.slice(0, columns));
      rest = rest.slice(columns);
    }
    if (!current) current = rest;
    else if (current.length + 1 + rest.length <= columns) current = `${current} ${rest}`;
    else {
      lines.push(current);
      current = rest;
    }
  }
  if (current) lines.push(current);
  return lines.length ? lines : [""];
}

function layout(spec: PdfDocumentSpec): Line[] {
  const lines: Line[] = [
    ...wrapText(spec.title, 52).map((text) => ({ text, size: 18, bold: true, gapBefore: 0 })),
  ];
  if (spec.subtitle) {
    lines.push(...wrapText(spec.subtitle).map((text, i) => ({ text, size: 9.5, bold: false, gapBefore: i ? 0 : 6 })));
  }
  for (const section of spec.sections) {
    if (section.heading) {
      lines.push(...wrapText(section.heading, 70).map((text, i) => ({ text, size: 12.5, bold: true, gapBefore: i ? 0 : 14 })));
    }
    for (const paragraph of section.lines) {
      lines.push(...wrapText(paragraph).map((text, i) => ({ text, size: BODY_SIZE, bold: false, gapBefore: i ? 0 : 4 })));
    }
  }
  if (spec.footer) lines.push({ text: spec.footer, size: 8.5, bold: false, gapBefore: 18 });
  return lines;
}

function paginate(lines: readonly Line[]): string[] {
  const pages: string[] = [];
  let ops: string[] = [];
  let y = PAGE_HEIGHT - MARGIN;
  for (const line of lines) {
    const step = line.gapBefore + Math.max(LINE_HEIGHT, line.size * 1.3);
    if (y - step < MARGIN && ops.length) {
      pages.push(ops.join("\n"));
      ops = [];
      y = PAGE_HEIGHT - MARGIN;
    }
    y -= step;
    const font = line.bold ? "/F2" : "/F1";
    ops.push(`BT ${font} ${line.size} Tf ${MARGIN} ${y.toFixed(2)} Td (${escapePdfText(toLatin1(line.text))}) Tj ET`);
  }
  pages.push(ops.join("\n"));
  return pages;
}

export function buildPdf(spec: PdfDocumentSpec): Uint8Array {
  const pageStreams = paginate(layout(spec));
  const objects: string[] = [];
  // 1 catalog, 2 pages, 3 Helvetica, 4 Helvetica-Bold, 5 info, then (page, content) pairs.
  const pageIds = pageStreams.map((_, i) => 6 + i * 2);
  objects[1] = "<< /Type /Catalog /Pages 2 0 R >>";
  objects[2] = `<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(" ")}] /Count ${pageIds.length} >>`;
  objects[3] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>";
  objects[4] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>";
  objects[5] = `<< /Title (${escapePdfText(toLatin1(spec.title))}) /Producer (RAG Showcase Engine) >>`;
  pageStreams.forEach((stream, i) => {
    const pageId = pageIds[i]!;
    objects[pageId] =
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${PAGE_WIDTH} ${PAGE_HEIGHT}] ` +
      `/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents ${pageId + 1} 0 R >>`;
    objects[pageId + 1] = `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`;
  });

  let body = "%PDF-1.4\n%\xE2\xE3\xCF\xD3\n";
  const offsets: number[] = [];
  for (let id = 1; id < objects.length; id += 1) {
    offsets[id] = body.length;
    body += `${id} 0 obj\n${objects[id]}\nendobj\n`;
  }
  const xrefOffset = body.length;
  body += `xref\n0 ${objects.length}\n0000000000 65535 f \n`;
  for (let id = 1; id < objects.length; id += 1) {
    body += `${String(offsets[id]).padStart(10, "0")} 00000 n \n`;
  }
  body += `trailer\n<< /Size ${objects.length} /Root 1 0 R /Info 5 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`;

  const bytes = new Uint8Array(body.length);
  for (let i = 0; i < body.length; i += 1) bytes[i] = body.charCodeAt(i) & 0xff;
  return bytes;
}
