/**
 * Minimal API client. Same-origin only; credentials via cookie
 * (HttpOnly session cookie set by the server). CSRF token is read
 * from the double-submit cookie and sent as a header on mutations.
 */

export interface Me {
  id: number;
  email: string;
  display_name: string;
  role: string;
  totp_enabled: boolean;
}

export interface Status {
  needs_bootstrap: boolean;
  app_env: string;
  panic_active: boolean;
}

export interface Health {
  status: string;
  app_env: string;
  uptime_seconds: number;
  python: string;
  panic_active: boolean;
  db: { reachable: boolean; latency_ms?: number; error?: string };
}

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)aegis_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : '';
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  const extra = init.headers as Record<string, string> | undefined;
  if (extra) {
    for (const [k, v] of Object.entries(extra)) headers[k] = v;
  }
  const method = (init.method ?? 'GET').toUpperCase();
  if (method !== 'GET' && method !== 'HEAD') {
    headers['X-CSRF-Token'] = csrfToken();
  }
  const res = await fetch(path, { ...init, headers, credentials: 'same-origin' });
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const err = (data as { error?: { code?: string; message?: string } } | null)?.error;
    if (err) throw new ApiError(res.status, err.code ?? 'error', err.message ?? 'Request failed');
    throw new ApiError(res.status, 'http_error', `HTTP ${res.status}`);
  }
  return data as T;
}

export const api = {
  getStatus: () => request<Status>('/api/auth/status'),
  getHealth: () => request<Health>('/healthz', { method: 'GET' }),
  getMe: () => request<Me>('/api/auth/me'),
  bootstrap: (email: string, password: string, display_name: string) =>
    request<Me>('/api/auth/bootstrap', {
      method: 'POST',
      body: JSON.stringify({ email, password, display_name }),
    }),
  login: (email: string, password: string, remember_me = false, totp_code = '') =>
    request<Me>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password, remember_me, totp_code }),
    }),
  logout: () =>
    request<{ ok: boolean }>('/api/auth/logout', { method: 'POST', body: '{}' }),
  totpSetup: () =>
    request<{ provisioning_uri: string }>('/api/auth/totp/setup', {
      method: 'POST',
      body: '{}',
    }),
  totpEnable: (code: string) =>
    request<{ ok: boolean }>('/api/auth/totp/enable', {
      method: 'POST',
      body: JSON.stringify({ code }),
    }),
  totpDisable: (code: string) =>
    request<{ ok: boolean }>('/api/auth/totp/disable', {
      method: 'POST',
      body: JSON.stringify({ code }),
    }),
  panic: (reason: string) =>
    request<{ ok: boolean }>('/api/system/panic', {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  panicClear: () =>
    request<{ ok: boolean }>('/api/system/panic/clear', { method: 'POST', body: '{}' }),
  auditVerify: () =>
    request<{ valid: boolean; entries: number; first_broken_id: number | null; problem: string | null }>(
      '/api/system/audit/verify'
    ),
};
