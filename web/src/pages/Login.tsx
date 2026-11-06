import { useState, type FormEvent } from 'react';
import { useAuth } from '../auth';
import { ApiError } from '../api';

export function LoginForm() {
  const { login, bootstrap, status } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [totpCode, setTotpCode] = useState('');
  const [needsTotp, setNeedsTotp] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isBootstrap = status?.needs_bootstrap === true;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (isBootstrap) {
        await bootstrap(email, password, displayName || email.split('@')[0]);
      } else {
        await login(email, password, rememberMe, totpCode);
      }
    } catch (err) {
      if (err instanceof ApiError && err.code === 'totp_required') {
        setNeedsTotp(true);
        setError('This account uses two-factor authentication. Enter the 6-digit code from your authenticator app.');
      } else {
        setError(err instanceof Error ? err.message : 'Something went wrong');
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col items-center justify-center px-4">
      <form
        onSubmit={onSubmit}
        className="w-full rounded-2xl p-6 shadow-lg"
        style={{ background: 'var(--panel)' }}
        aria-label={isBootstrap ? 'Create owner account' : 'Sign in'}
      >
        <h1 className="mb-1 text-2xl font-bold tracking-tight">Aegis AI</h1>
        <p className="mb-6 text-sm" style={{ color: 'var(--muted)' }}>
          {isBootstrap
            ? 'First run: creating the owner account for this device. There is no server — everything stays on this machine.'
            : 'Signed out. Your sessions expire after 30 minutes of inactivity.'}
        </p>

        {isBootstrap && (
          <label className="mb-4 block">
            <span className="mb-1 block text-sm font-medium">Display name</span>
            <input
              required
              minLength={1}
              maxLength={120}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full rounded-lg border px-3 py-2 text-base outline-none focus:ring-2"
              style={{ borderColor: 'var(--muted)', color: 'var(--text)', background: 'var(--surface)' }}
              autoComplete="name"
            />
          </label>
        )}

        <label className="mb-4 block">
          <span className="mb-1 block text-sm font-medium">Email</span>
          <input
            required
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border px-3 py-2 text-base outline-none focus:ring-2"
            style={{ borderColor: 'var(--muted)', color: 'var(--text)', background: 'var(--surface)' }}
            autoComplete="username"
          />
        </label>

        <label className="mb-4 block">
          <span className="mb-1 block text-sm font-medium">Password (min 12 characters)</span>
          <input
            required
            type="password"
            minLength={12}
            maxLength={200}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border px-3 py-2 text-base outline-none focus:ring-2"
            style={{ borderColor: 'var(--muted)', color: 'var(--text)', background: 'var(--surface)' }}
            autoComplete={isBootstrap ? 'new-password' : 'current-password'}
          />
        </label>

        {needsTotp && (
          <label className="mb-4 block">
            <span className="mb-1 block text-sm font-medium">Two-factor code</span>
            <input
              required
              inputMode="numeric"
              pattern="[0-9 ]{6,7}"
              autoComplete="one-time-code"
              value={totpCode}
              onChange={(e) => setTotpCode(e.target.value)}
              className="w-full rounded-lg border px-3 py-2 text-base tracking-widest outline-none focus:ring-2"
              style={{ borderColor: 'var(--muted)', color: 'var(--text)', background: 'var(--surface)' }}
            />
          </label>
        )}

        {!isBootstrap && (
          <label className="mb-6 flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="h-4 w-4 accent-cyan-400"
            />
            Keep me signed in for 7 days
          </label>
        )}

        {error && (
          <p role="alert" className="mb-4 rounded-lg px-3 py-2 text-sm" style={{ background: 'rgba(239,68,68,.15)', color: '#fca5a5' }}>
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-cyan-400 px-4 py-2.5 text-base font-semibold text-slate-900 transition disabled:opacity-50"
        >
          {busy ? 'Working…' : isBootstrap ? 'Create owner account' : 'Sign in'}
        </button>
      </form>
      <p className="mt-4 text-xs" style={{ color: 'var(--muted)' }}>
        Runs only on this device · no telemetry · no account recovery by email
      </p>
    </main>
  );
}
