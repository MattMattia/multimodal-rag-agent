import "server-only";

import { type DataSource, SOURCE_HEADER } from "../contracts";
import { ShowcaseError } from "../showcase-engine";

/**
 * BFF → FastAPI client. `FASTAPI_URL` and `API_KEY` are read on the server at request time only
 * (never `NEXT_PUBLIC_*`), so they can change per deployment without a rebuild and never reach the browser.
 */
const DEFAULT_TIMEOUT_MS = 3000;
/**
 * Bad Gateway / Gateway Timeout mean "no live backend behind the proxy" (e.g. a sleeping host).
 * A 503 is passed through: a live backend may return it deliberately.
 */
const GATEWAY_UNAVAILABLE = new Set([502, 504]);
const PASSTHROUGH_HEADERS = ["content-type", "content-disposition", "cache-control", "content-length"];

export interface BackendConfig {
  baseUrl: string | null;
  apiKey: string | null;
  timeoutMs: number;
}

export function backendConfig(): BackendConfig {
  const baseUrl = process.env.FASTAPI_URL?.trim().replace(/\/+$/, "") || null;
  const apiKey = process.env.API_KEY?.trim() || null;
  const timeout = Number(process.env.FASTAPI_TIMEOUT_MS);
  return { baseUrl, apiKey, timeoutMs: Number.isFinite(timeout) && timeout > 0 ? timeout : DEFAULT_TIMEOUT_MS };
}

export type BackendResult =
  | { kind: "live"; response: Response }
  | { kind: "unreachable"; reason: string }
  /** The browser closed the request: nobody is waiting for an answer, so no fallback runs. */
  | { kind: "aborted" };

export interface CallOptions {
  method?: "GET" | "POST" | "DELETE";
  json?: unknown;
  body?: BodyInit;
  headers?: Record<string, string>;
  /** Milliseconds to wait for the response headers (the body may stream for longer). */
  timeoutMs?: number;
  /** The incoming request's signal: when the client disconnects, the upstream call (and stream) is cancelled. */
  signal?: AbortSignal;
}

/** Server-side diagnostic for every fallback; it names the path and reason, never the URL or the key. */
function logFallback(path: string, reason: string): void {
  console.warn(`[bff] FastAPI unavailable for ${path.split("?")[0]} (${reason}); serving the showcase engine`);
}

/** Calls `${FASTAPI_URL}/api/v1${path}`; network failures, timeouts and gateway errors become "unreachable". */
export async function callBackend(path: string, options: CallOptions = {}): Promise<BackendResult> {
  const config = backendConfig();
  if (options.signal?.aborted) return { kind: "aborted" };
  if (!config.baseUrl) {
    logFallback(path, "backend URL not configured");
    return { kind: "unreachable", reason: "FASTAPI_URL is not configured" };
  }

  const headers: Record<string, string> = { Accept: "application/json, text/event-stream, */*", ...options.headers };
  if (config.apiKey) headers["X-API-Key"] = config.apiKey;
  let body = options.body;
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  }

  const controller = new AbortController();
  let timedOut = false;
  // The timeout only covers the headers phase; the client signal stays linked for the whole body stream.
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, options.timeoutMs ?? config.timeoutMs);
  const onClientAbort = () => controller.abort();
  options.signal?.addEventListener("abort", onClientAbort, { once: true });
  try {
    const response = await fetch(`${config.baseUrl}/api/v1${path}`, {
      method: options.method ?? "GET",
      headers,
      body,
      signal: controller.signal,
      cache: "no-store",
      redirect: "manual",
    });
    if (GATEWAY_UNAVAILABLE.has(response.status)) {
      await response.body?.cancel();
      options.signal?.removeEventListener("abort", onClientAbort);
      logFallback(path, `gateway returned ${response.status}`);
      return { kind: "unreachable", reason: `gateway returned ${response.status}` };
    }
    return { kind: "live", response };
  } catch (error) {
    options.signal?.removeEventListener("abort", onClientAbort);
    if (options.signal?.aborted && !timedOut) return { kind: "aborted" };
    const reason = timedOut ? "timeout" : error instanceof Error ? error.message : "network error";
    logFallback(path, reason);
    return { kind: "unreachable", reason };
  } finally {
    clearTimeout(timer);
  }
}

function withSource(headers: Headers, source: DataSource): Headers {
  headers.set(SOURCE_HEADER, source);
  headers.set("Cache-Control", headers.get("Cache-Control") ?? "no-store");
  return headers;
}

/** Streams a live backend response through unchanged (status, body and relevant headers). */
export function passThrough(response: Response): Response {
  const headers = new Headers();
  for (const name of PASSTHROUGH_HEADERS) {
    const value = response.headers.get(name);
    if (value) headers.set(name, value);
  }
  return new Response(response.body, { status: response.status, headers: withSource(headers, "fastapi") });
}

export function showcaseJson(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: withSource(new Headers({ "Content-Type": "application/json" }), "showcase"),
  });
}

export function showcaseResponse(body: BodyInit, contentType: string, extra: Record<string, string> = {}): Response {
  return new Response(body, {
    status: 200,
    headers: withSource(new Headers({ "Content-Type": contentType, ...extra }), "showcase"),
  });
}

/** Response for a request the client already abandoned (nginx's 499 convention); it is never read. */
export function clientClosed(): Response {
  return new Response(null, { status: 499 });
}

/** JSON error produced by the BFF itself (validation), shaped like FastAPI's `{"detail": ...}`. */
export function bffError(status: number, detail: string): Response {
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

/**
 * Live-first with showcase fallback. Any HTTP answer from a live backend (2xx, 4xx, 5xx other than gateway
 * errors) is passed through; only an unreachable backend triggers the showcase engine.
 */
export async function liveOrShowcase(
  path: string,
  options: CallOptions,
  fallback: () => Response | Promise<Response>,
): Promise<Response> {
  const result = await callBackend(path, options);
  if (result.kind === "live") return passThrough(result.response);
  if (result.kind === "aborted") return clientClosed();
  try {
    return await fallback();
  } catch (error) {
    if (error instanceof ShowcaseError) {
      const response = showcaseJson({ detail: error.message }, error.status);
      return response;
    }
    throw error;
  }
}
