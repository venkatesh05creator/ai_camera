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
  // --- Phase 3: AI brain -----------------------------------------------------
  quota: () => request<{ rows: Array<{ provider: string; model: string; day: string; requests: number; input_tokens: number | null; output_tokens: number | null; errors: number; cooldown_until: string | null }>; day: string | null }>('/api/ai/quota'),
  chat: (question: string, allowRemote: boolean) =>
    request<{
      answer: string;
      question: string;
      evidence: Array<{ id: string; source: string; title: string; text: string }>;
      verifier: { valid_badges: string[]; invalid_badges: string[]; unsupported_sentences: string[] };
      provider: string;
      model: string;
    }>('/api/ai/chat', {
      method: 'POST',
      body: JSON.stringify({ messages: [{ role: 'user', content: question }], question, allow_remote: allowRemote }),
    }),
  chatStream: async (
    question: string,
    allowRemote: boolean,
    onDelta: (text: string) => void
  ): Promise<{
    answer: string;
    evidence: Array<{ id: string; source: string; title: string; text: string }>;
    verifier: { valid_badges: string[]; invalid_badges: string[]; unsupported_sentences: string[] };
    provider: string;
    model: string;
  }> => {
    const res = await fetch('/api/ai/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() },
      credentials: 'same-origin',
      body: JSON.stringify({ messages: [{ role: 'user', content: question }], question, allow_remote: allowRemote }),
    });
    if (!res.ok) {
      const data = (await res.json().catch(() => null)) as { error?: { code?: string; message?: string } } | null;
      const err = data?.error;
      throw new ApiError(res.status, err?.code ?? 'error', err?.message ?? `HTTP ${res.status}`);
    }
    if (!res.body) throw new ApiError(0, 'no_body', 'The stream was empty.');
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let verdict: {
      answer: string;
      evidence: Array<{ id: string; source: string; title: string; text: string }>;
      verifier: { valid_badges: string[]; invalid_badges: string[]; unsupported_sentences: string[] };
      provider: string;
      model: string;
    } | null = null;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';
      for (const line of lines) {
        if (!line.trim()) continue;
        const evt = JSON.parse(line) as {
          type: string; text?: string; code?: string; message?: string;
          answer?: string; provider?: string; model?: string;
          evidence?: Array<{ id: string; source: string; title: string; text: string }>;
          verifier?: { valid_badges: string[]; invalid_badges: string[]; unsupported_sentences: string[] };
        };
        if (evt.type === 'delta' && evt.text) onDelta(evt.text);
        else if (evt.type === 'verdict') {
          verdict = {
            answer: evt.answer ?? '',
            evidence: evt.evidence ?? [],
            verifier: evt.verifier ?? { valid_badges: [], invalid_badges: [], unsupported_sentences: [] },
            provider: evt.provider ?? 'unknown',
            model: evt.model ?? 'unknown',
          };
        } else if (evt.type === 'error') {
          throw new ApiError(0, evt.code ?? 'stream_error', evt.message ?? 'Chat failed');
        }
      }
    }
    if (!verdict) throw new ApiError(0, 'no_verdict', 'Chat ended without a verified answer.');
    return verdict;
  },
  memoryList: () =>
    request<{ items: Array<{ id: number; kind: string; text: string; created_at: string; updated_at: string }>; count: number }>('/api/memory'),
  memoryCreate: (kind: string, text: string) =>
    request<{ id: number; kind: string; text: string }>('/api/memory', {
      method: 'POST',
      body: JSON.stringify({ kind, text }),
    }),
  memoryUpdate: (id: number, text: string) =>
    request<{ id: number; kind: string; text: string }>(`/api/memory/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ kind: 'fact', text }),
    }),
  memoryDelete: (id: number) =>
    request<{ ok: boolean }>(`/api/memory/${id}`, { method: 'DELETE' }),
  memoryExportUrl: () => '/api/memory/export',
};
