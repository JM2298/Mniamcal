const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "0.0.0.0"]);
const INTERNAL_BACKEND_HOSTS = new Set(["web", "nginx", "node", "db", "redis", "django-web", "django_nginx"]);

function isLoopbackHost(host: string): boolean {
  return LOOPBACK_HOSTS.has(host);
}

function normalizeHost(host: string): string {
  return host === "0.0.0.0" ? "localhost" : host.toLowerCase();
}

function shouldRewriteToApiBaseHost(host: string): boolean {
  const normalized = normalizeHost(host);
  return isLoopbackHost(normalized) || INTERNAL_BACKEND_HOSTS.has(normalized);
}

function normalizedApiBase(rawApiBaseUrl?: string): URL {
  const fallback = "https://dieta-backend.michalowicz.dev/";
  const candidate = (rawApiBaseUrl || fallback).trim() || fallback;
  const parsed = new URL(candidate);

  const hostname = parsed.hostname === "0.0.0.0" ? "localhost" : parsed.hostname;
  const normalizedPort =
    isLoopbackHost(hostname) && (parsed.port === "3000" || parsed.port === "5000")
      ? "8000"
      : parsed.port || (isLoopbackHost(hostname) ? "8000" : "");

  return new URL(`${parsed.protocol}//${hostname}${normalizedPort ? `:${normalizedPort}` : ""}`);
}

function withHostAndPort(url: URL, host: string, port?: string): URL {
  const cloned = new URL(url.toString());
  cloned.hostname = host;
  cloned.port = port || "";
  return cloned;
}

export function getBackendApiBaseUrl(rawApiBaseUrl?: string): string {
  return normalizedApiBase(rawApiBaseUrl).toString().replace(/\/$/, "");
}

export function buildBackendApiUrl(pathOrUrl: string, rawApiBaseUrl?: string): string {
  const apiBase = normalizedApiBase(rawApiBaseUrl);
  const value = (pathOrUrl || "").trim();

  if (!value) {
    return apiBase.toString();
  }

  try {
    const parsed = new URL(value, apiBase);
    const parsedHost = normalizeHost(parsed.hostname);

    if (shouldRewriteToApiBaseHost(parsedHost)) {
      parsed.protocol = apiBase.protocol;
      parsed.hostname = apiBase.hostname;
      parsed.port = apiBase.port;
    } else {
      parsed.hostname = parsedHost;
    }

    return parsed.toString();
  } catch {
    if (value.startsWith("/")) {
      return new URL(value, apiBase).toString();
    }

    return new URL(`/${value}`, apiBase).toString();
  }
}

export function resolveBackendAssetUrl(rawUrl?: string | null, rawApiBaseUrl?: string): string | null {
  const value = (rawUrl || "").trim();
  if (!value) {
    return null;
  }

  const apiBase = normalizedApiBase(rawApiBaseUrl);

  try {
    const parsed = new URL(value);
    const isMediaLikePath = parsed.pathname.startsWith("/media/") || parsed.pathname.startsWith("/static/");
    const parsedHost = parsed.hostname === "0.0.0.0" ? "localhost" : parsed.hostname;

    if (isLoopbackHost(parsedHost) && isMediaLikePath) {
      return withHostAndPort(parsed, "localhost", "8000").toString();
    }

    return withHostAndPort(parsed, parsedHost, parsed.port).toString();
  } catch {
    if (value.startsWith("/")) {
      return new URL(value, apiBase).toString();
    }

    return new URL(`/${value}`, apiBase).toString();
  }
}
