import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../auth';
import { api, type Health } from '../api';

export function Home() {
  const { me, logout, refresh } = useAuth();
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [audit, setAudit] = useState<{ valid: boolean; entries: number } | null>(null);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [panicBusy, setPanicBusy] = useState(false);
  const [totpUri, setTotpUri] = useState<string | null>(null);
  const [totpCode, setTotpCode] = useState('');
  const [totpMsg, setTotpMsg] = useState<string | null>(null);

  const loadHealth = useCallback(async () => {
    try {
      setHealth(await api.getHealth());
      setHealthError(null);
    } catch {
      setHealthError('Health endpoint unreachable — is the backend running on :8000?');
    }
  }, []);

  const loadAudit = useCallback(async () => {
    try {
      const r = await api.auditVerify();
      setAudit({ valid: r.valid, entries: r.entries });
      setAuditError(null);
    } catch (e) {
      setAuditError(e instanceof Error ? e.message : 'Audit check failed');
    }
  }, []);

  useEffect(() => {
    loadHealth();
    loadAudit();
    const t = setInterval(loadHealth, 15000);
    return () => clearInterval(t);
  }, [loadHealth, loadAudit]);

  async function onPanic() {
    if (!window.confirm('Activate panic mode? All features will be blocked until you clear it.')) return;
    setPanicBusy(true);
    try {
      await api.panic('Activated from dashboard');
      await refresh();
    } catch (e) {
      window.alert(e instanceof Error ? e.message : 'Panic failed');
    } finally {
      setPanicBusy(false);
    }
  }

  async function onTotpSetup() {
    try {
      const r = await api.totpSetup();
      setTotpUri(r.provisioning_uri);
      setTotpMsg('Scan this in your authenticator app, then enter the code below to confirm.');
    } catch (e) {
      setTotpMsg(e instanceof Error ? e.message : 'Setup failed');
    }
  }

  async function onTotpEnable() {
    try {
      await api.totpEnable(totpCode);
      setTotpUri(null);
      setTotpCode('');
      setTotpMsg('Two-factor authentication is now ON. You will need a code at every sign-in.');
      await refresh();
    } catch (e) {
      setTotpMsg(e instanceof Error ? e.message : 'That code did not work');
    }
  }

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Aegis AI</h1>
          <p className="text-sm" style={{ color: 'var(--muted)' }}>
            Signed in as {me?.display_name} ({me?.role})
          </p>
        </div>
        <button
          onClick={logout}
          className="rounded-lg border px-3 py-1.5 text-sm"
          style={{ borderColor: 'var(--muted)' }}
        >
          Sign out
        </button>
      </header>

      {/* Health — real numbers from the server, or an honest "unreachable" */}
      <section className="mb-4 rounded-2xl p-5" style={{ background: 'var(--panel)' }} aria-label="System health">
        <h2 className="mb-3 font-semibold">System health</h2>
        {healthError ? (
          <p role="alert" className="text-sm text-red-300">{healthError}</p>
        ) : health ? (
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt style={{ color: 'var(--muted)' }}>Status</dt>
            <dd>{health.status}</dd>
            <dt style={{ color: 'var(--muted)' }}>Env</dt>
            <dd>{health.app_env}</dd>
            <dt style={{ color: 'var(--muted)' }}>Uptime</dt>
            <dd>{Math.round(health.uptime_seconds)}s</dd>
            <dt style={{ color: 'var(--muted)' }}>Python</dt>
            <dd>{health.python}</dd>
            <dt style={{ color: 'var(--muted)' }}>Database</dt>
            <dd>
              {health.db.reachable
                ? `reachable (${health.db.latency_ms} ms)`
                : `unreachable${health.db.error ? ` — ${health.db.error}` : ''}`}
            </dd>
            <dt style={{ color: 'var(--muted)' }}>Panic mode</dt>
            <dd>{health.panic_active ? 'ACTIVE' : 'off'}</dd>
          </dl>
        ) : (
          <p className="text-sm" style={{ color: 'var(--muted)' }}>Loading…</p>
        )}
      </section>

      {/* Audit */}
      <section className="mb-4 rounded-2xl p-5" style={{ background: 'var(--panel)' }} aria-label="Audit trail">
        <h2 className="mb-3 font-semibold">Audit trail</h2>
        {auditError ? (
          <p role="alert" className="text-sm text-red-300">{auditError}</p>
        ) : audit ? (
          <p className="text-sm">
            {audit.valid ? '✅ Hash chain intact' : '❌ Chain broken'}
            {' · '}{audit.entries} entries
          </p>
        ) : (
          <p className="text-sm" style={{ color: 'var(--muted)' }}>Loading…</p>
        )}
      </section>

      {/* 2FA */}
      <section className="mb-4 rounded-2xl p-5" style={{ background: 'var(--panel)' }} aria-label="Two factor">
        <h2 className="mb-3 font-semibold">Two-factor authentication</h2>
        {me?.totp_enabled ? (
          <p className="text-sm">Enabled. Codes are required at every sign-in.</p>
        ) : (
          <>
            <p className="mb-3 text-sm" style={{ color: 'var(--muted)' }}>
              Not enabled. Strongly recommended — it protects this device even if the password leaks.
            </p>
            {!totpUri ? (
              <button onClick={onTotpSetup} className="rounded-lg bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-900">
                Start enrollment
              </button>
            ) : (
              <div>
                <p className="mb-2 break-all rounded-lg px-3 py-2 text-xs" style={{ background: 'var(--surface)' }}>
                  {totpUri}
                </p>
                <div className="flex gap-2">
                  <input
                    value={totpCode}
                    onChange={(e) => setTotpCode(e.target.value)}
                    inputMode="numeric"
                    placeholder="6-digit code"
                    className="w-36 rounded-lg border px-3 py-2 text-base tracking-widest"
                    style={{ borderColor: 'var(--muted)', color: 'var(--text)', background: 'var(--surface)' }}
                    aria-label="6-digit code"
                  />
                  <button onClick={onTotpEnable} className="rounded-lg bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-900">
                    Confirm
                  </button>
                </div>
              </div>
            )}
          </>
        )}
        {totpMsg && <p className="mt-3 text-sm" style={{ color: 'var(--muted)' }}>{totpMsg}</p>}
      </section>

      {/* Panic */}
      <section className="mb-4 rounded-2xl p-5" style={{ background: 'var(--panel)' }} aria-label="Panic switch">
        <h2 className="mb-3 font-semibold">Panic switch</h2>
        <p className="mb-3 text-sm" style={{ color: 'var(--muted)' }}>
          Blocks everything except health checks and sign-in. Use if someone forces access to this device.
        </p>
        <button
          onClick={onPanic}
          disabled={panicBusy}
          className="rounded-lg bg-red-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {panicBusy ? 'Activating…' : '🚨 Activate panic mode'}
        </button>
      </section>

      {/* Later phases — honest empty states, no fake data */}
      <section className="mb-4 rounded-2xl p-5" style={{ background: 'var(--panel)' }} aria-label="Cameras, phase 4">
        <h2 className="mb-3 font-semibold">Cameras</h2>
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          No cameras configured yet — they arrive in Phase 4. No feeds, counts, or alerts are shown until then.
        </p>
      </section>

      <section className="mb-4 rounded-2xl p-5" style={{ background: 'var(--panel)' }} aria-label="Assistant, phase 5">
        <h2 className="mb-3 font-semibold">Assistant</h2>
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          The local LLM arrives in Phase 5. No model is running yet — nothing will pretend otherwise.
        </p>
      </section>
    </main>
  );
}
