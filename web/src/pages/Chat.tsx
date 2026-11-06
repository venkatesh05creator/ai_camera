import { useEffect, useState } from 'react';
import { api, ApiError } from '../api';

interface Turn {
  q: string;
  text: string;
  streaming: boolean;
  evidence: Array<{ id: string; source: string; title: string; text: string }>;
  verifier: { valid_badges: string[]; invalid_badges: string[]; unsupported_sentences: string[] } | null;
  provider: string | null;
  model: string | null;
  error: string | null;
}

export function Chat() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [allowRemote, setAllowRemote] = useState(false);
  const [quota, setQuota] = useState<Array<{ provider: string; model: string; requests: number; input_tokens: number | null; output_tokens: number | null; errors: number; cooldown_until: string | null }> | null>(null);

  useEffect(() => {
    api.quota().then((q) => setQuota(q.rows)).catch(() => setQuota([]));
  }, []);

  async function ask(e: React.FormEvent) {
    e.preventDefault();
    const question = input.trim();
    if (!question || busy) return;
    setInput('');
    setBusy(true);
    const idx = turns.length;
    setTurns([...turns, {
      q: question, text: '', streaming: true, evidence: [],
      verifier: null, provider: null, model: null, error: null,
    }]);
    try {
      const verdict = await api.chatStream(question, allowRemote, (delta) => {
        setTurns((prev) => {
          const copy = [...prev];
          const t = copy[idx];
          if (!t) return prev;
          copy[idx] = { ...t, text: t.text + delta };
          return copy;
        });
      });
      setTurns((prev) => {
        const copy = [...prev];
        const t = copy[idx];
        if (!t) return prev;
        copy[idx] = {
          ...t, streaming: false, text: verdict.answer,
          evidence: verdict.evidence, verifier: verdict.verifier,
          provider: verdict.provider, model: verdict.model,
        };
        return copy;
      });
      const q = await api.quota().catch(() => null);
      if (q) setQuota(q.rows);
    } catch (err) {
      const msg = err instanceof ApiError
        ? `${err.message} (code: ${err.code})`
        : 'Chat failed — the assistant is not reachable.';
      setTurns((prev) => {
        const copy = [...prev];
        const t = copy[idx];
        if (!t) return prev;
        copy[idx] = { ...t, streaming: false, error: msg };
        return copy;
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-6">
      <h1 className="mb-1 text-xl font-bold">Assistant</h1>
      <p className="mb-4 text-sm" style={{ color: 'var(--muted)' }}>
        Answers cite evidence as badges [E1]… and are machine-verified before you see them.
        Unverifiable claims are flagged, never hidden.
      </p>

      <label className="mb-4 flex items-start gap-2 rounded-xl px-3 py-2 text-xs" style={{ background: 'var(--panel)', color: 'var(--muted)' }}>
        <input
          type="checkbox"
          checked={allowRemote}
          onChange={(e) => setAllowRemote(e.target.checked)}
          className="mt-0.5 h-4 w-4 accent-cyan-400"
        />
        <span>
          Allow metered cloud fallback for this question only (off by default).
          Local content never leaves this machine unless you opt in per request.
        </span>
      </label>

      <ul className="mb-4 flex flex-col gap-4" aria-live="polite">
        {turns.map((t, i) => (
          <li key={i} className="rounded-2xl p-4" style={{ background: 'var(--panel)' }}>
            <p className="mb-2 text-sm font-semibold">{t.q}</p>
            {t.error ? (
              <p role="alert" className="text-sm text-red-300">{t.error}</p>
            ) : (
              <>
                <p className="mb-3 whitespace-pre-wrap text-base">
                  {t.text}
                  {t.streaming && <span className="animate-pulse">▍</span>}
                </p>
                {t.verifier && (
                  <>
                    <p className="mb-2 text-xs" style={{ color: 'var(--muted)' }}>
                      {t.provider ? `via ${t.provider}/${t.model} · ` : ''}
                      verified badges: {t.verifier.valid_badges.join(', ') || 'none'}
                      {t.verifier.invalid_badges.length > 0 && (
                        <span className="text-red-300">
                          {' '}· hallucinated badges dropped: {t.verifier.invalid_badges.join(', ')}
                        </span>
                      )}
                    </p>
                    {t.verifier.unsupported_sentences.length > 0 && (
                      <div className="mb-2 rounded-lg px-3 py-2 text-xs text-amber-200" style={{ background: 'rgba(245,158,11,.12)' }}>
                        ⚠ These sentences had no evidence and are unverified:
                        <ul className="list-disc pl-4">
                          {t.verifier.unsupported_sentences.map((s, j) => (
                            <li key={j}>{s}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {t.evidence.length > 0 && (
                      <details>
                        <summary className="cursor-pointer text-xs" style={{ color: 'var(--muted)' }}>
                          Evidence ({t.evidence.length})
                        </summary>
                        <ul className="mt-1 flex flex-col gap-1">
                          {t.evidence.map((ev) => (
                            <li key={ev.id} className="rounded px-2 py-1 text-xs" style={{ background: 'var(--surface)' }}>
                              <code className="font-bold" style={{ color: 'var(--accent)' }}>[{ev.id}]</code>{' '}
                              <span style={{ color: 'var(--muted)' }}>{ev.source} · {ev.title}</span>
                              <span> — {ev.text}</span>
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </>
                )}
              </>
            )}
          </li>
        ))}
      </ul>

      <form onSubmit={ask} className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about today…"
          aria-label="Ask the assistant"
          className="flex-1 rounded-xl border px-3 py-2.5 text-base outline-none focus:ring-2"
          style={{ borderColor: 'var(--muted)', color: 'var(--text)', background: 'var(--panel)' }}
          disabled={busy}
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="rounded-xl bg-cyan-400 px-5 py-2.5 font-semibold text-slate-900 disabled:opacity-50"
        >
          {busy ? '…' : 'Ask'}
        </button>
      </form>

      <section className="mt-6 rounded-2xl p-4" style={{ background: 'var(--panel)' }} aria-label="Provider quota">
        <h2 className="mb-2 text-sm font-semibold">Provider quota (real counts, today)</h2>
        {quota === null ? (
          <p className="text-xs" style={{ color: 'var(--muted)' }}>Loading…</p>
        ) : quota.length === 0 ? (
          <p className="text-xs" style={{ color: 'var(--muted)' }}>No provider calls yet today.</p>
        ) : (
          <ul className="flex flex-col gap-1 text-xs">
            {quota.map((r, i) => (
              <li key={i} className="flex flex-wrap gap-x-4">
                <span>{r.provider}/{r.model}</span>
                <span style={{ color: 'var(--muted)' }}>{r.requests} req · {r.input_tokens ?? '?'} in · {r.output_tokens ?? '?'} out · {r.errors} err</span>
                {r.cooldown_until && <span className="text-amber-300">cooldown until {r.cooldown_until}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
