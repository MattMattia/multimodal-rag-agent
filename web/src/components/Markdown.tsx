import { Fragment, type ReactNode } from "react";
import { toBffHref } from "@/lib/client/api";

/**
 * Small, safe Markdown renderer (no HTML injection): headings, paragraphs, lists, fenced code,
 * pipe tables and inline **bold**, _italic_, `code` and [links](href). Only relative, http(s) and
 * anchor hrefs are rendered as links; report links are routed through the BFF.
 */
type Block =
  | { kind: "heading"; level: 1 | 2 | 3; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "list"; ordered: boolean; items: string[] }
  | { kind: "code"; text: string }
  | { kind: "table"; header: string[]; rows: string[][] };

const SAFE_HREF = /^(\/(?!\/)|https?:\/\/|#)/;
// `_italic_` only at word boundaries, so snake_case file names such as Reporte_Financiero_Q3.pdf stay intact.
const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)\s]+\)|(?<!\w)_[^_\s][^_]*_(?!\w))/g;

const cells = (line: string): string[] =>
  line
    .trim()
    .replace(/^\||\|$/g, "")
    .split("|")
    .map((c) => c.trim());

export function parseMarkdown(source: string): Block[] {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i] ?? "";
    if (!line.trim()) {
      i += 1;
      continue;
    }
    if (line.startsWith("```")) {
      const body: string[] = [];
      i += 1;
      while (i < lines.length && !(lines[i] ?? "").startsWith("```")) body.push(lines[i++] ?? "");
      i += 1;
      blocks.push({ kind: "code", text: body.join("\n") });
      continue;
    }
    const heading = /^(#{1,3})\s+(.*)$/.exec(line);
    if (heading) {
      blocks.push({ kind: "heading", level: heading[1]!.length as 1 | 2 | 3, text: heading[2] ?? "" });
      i += 1;
      continue;
    }
    if (line.trim().startsWith("|") && /^\s*\|?\s*:?-{3,}/.test(lines[i + 1] ?? "")) {
      const header = cells(line);
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && (lines[i] ?? "").trim().startsWith("|")) rows.push(cells(lines[i++] ?? ""));
      blocks.push({ kind: "table", header, rows });
      continue;
    }
    const listMatch = /^\s*([-*]|\d+\.)\s+/.exec(line);
    if (listMatch) {
      const ordered = /\d/.test(listMatch[1] ?? "");
      const items: string[] = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i] ?? "")) {
        items.push((lines[i] ?? "").replace(/^\s*([-*]|\d+\.)\s+/, ""));
        i += 1;
      }
      blocks.push({ kind: "list", ordered, items });
      continue;
    }
    const paragraph: string[] = [];
    while (i < lines.length && (lines[i] ?? "").trim() && !/^(#{1,3}\s|```|\s*([-*]|\d+\.)\s|\s*\|)/.test(lines[i] ?? "")) {
      paragraph.push(lines[i++] ?? "");
    }
    if (paragraph.length === 0) paragraph.push(lines[i++] ?? "");
    blocks.push({ kind: "paragraph", text: paragraph.join(" ") });
  }
  return blocks;
}

function renderInline(text: string): ReactNode[] {
  return text.split(INLINE).map((part, index) => {
    if (!part) return null;
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={index}>{part.slice(1, -1)}</code>;
    if (part.startsWith("_") && part.endsWith("_") && part.length > 2) return <em key={index}>{part.slice(1, -1)}</em>;
    const link = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(part);
    if (link) {
      const href = toBffHref(link[2] ?? "");
      if (!SAFE_HREF.test(href)) return <Fragment key={index}>{link[1]}</Fragment>;
      const external = href.startsWith("http");
      return (
        <a key={index} href={href} {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}>
          {link[1]}
        </a>
      );
    }
    return <Fragment key={index}>{part}</Fragment>;
  });
}

export function Markdown({ source, className = "md" }: { source: string; className?: string }) {
  return (
    <div className={className}>
      {parseMarkdown(source).map((block, index) => {
        switch (block.kind) {
          case "heading": {
            const Tag = `h${block.level}` as const;
            return <Tag key={index}>{renderInline(block.text)}</Tag>;
          }
          case "paragraph":
            return <p key={index}>{renderInline(block.text)}</p>;
          case "code":
            return (
              <pre key={index}>
                <code>{block.text}</code>
              </pre>
            );
          case "list": {
            const List = block.ordered ? "ol" : "ul";
            return (
              <List key={index}>
                {block.items.map((item, j) => (
                  <li key={j}>{renderInline(item)}</li>
                ))}
              </List>
            );
          }
          case "table":
            return (
              <div className="table-wrap" key={index}>
                <table className="table">
                  <thead>
                    <tr>
                      {block.header.map((h, j) => (
                        <th key={j} scope="col">
                          {renderInline(h)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {block.rows.map((row, r) => (
                      <tr key={r}>
                        {row.map((cell, c) => (
                          <td key={c}>{renderInline(cell)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
        }
      })}
    </div>
  );
}
