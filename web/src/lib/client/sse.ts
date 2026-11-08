import type { AgentStreamEvent } from "../contracts";

const KNOWN_TYPES = new Set(["tool_start", "tool_end", "token", "metadata"]);

/**
 * Incremental Server-Sent Events parser for the agent stream. Feed it decoded text chunks as they
 * arrive; it returns the complete `data:` events and keeps partial frames buffered.
 */
export class SseParser {
  private buffer = "";

  feed(chunk: string): AgentStreamEvent[] {
    this.buffer += chunk.replace(/\r\n/g, "\n");
    const frames = this.buffer.split("\n\n");
    this.buffer = frames.pop() ?? "";
    return frames.flatMap(parseFrame);
  }

  flush(): AgentStreamEvent[] {
    const rest = this.buffer;
    this.buffer = "";
    return rest.trim() ? parseFrame(rest) : [];
  }
}

function parseFrame(frame: string): AgentStreamEvent[] {
  const data = frame
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).replace(/^ /, ""))
    .join("\n");
  if (!data) return [];
  try {
    const event = JSON.parse(data) as { type?: unknown };
    return typeof event.type === "string" && KNOWN_TYPES.has(event.type) ? [event as AgentStreamEvent] : [];
  } catch {
    return [];
  }
}

export async function* readAgentStream(response: Response, signal?: AbortSignal): AsyncGenerator<AgentStreamEvent> {
  if (!response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();
  try {
    while (!signal?.aborted) {
      const { value, done } = await reader.read();
      if (done) break;
      yield* parser.feed(decoder.decode(value, { stream: true }));
    }
    yield* parser.feed(decoder.decode());
    yield* parser.flush();
  } finally {
    reader.releaseLock();
  }
}
