import { useState } from 'react';
import { AuthProvider, useAuth } from './auth';
import { LoginForm } from './pages/Login';
import { Home } from './pages/Home';
import { Chat } from './pages/Chat';
import { Memory } from './pages/Memory';
import { Cameras } from './pages/Cameras';
import { CameraFeed } from './pages/CameraFeed';
import { People } from './pages/People';

function PanicGate({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  if (status?.panic_active) {
    return (
      <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col items-center justify-center px-4 text-center">
        <h1 className="mb-2 text-2xl font-bold text-red-400">Panic mode active</h1>
        <p className="mb-6 text-sm" style={{ color: 'var(--muted)' }}>
          All features are blocked. Sign in, then clear panic from a trusted device or the API.
        </p>
        <p className="text-xs" style={{ color: 'var(--muted)' }}>
          POST /api/system/panic/clear (owner, with CSRF token)
        </p>
      </main>
    );
  }
  return <>{children}</>;
}

type Page = 'home' | 'chat' | 'memory' | 'cameras' | 'feed' | 'people';

function Nav({ page, setPage }: { page: Page; setPage: (p: Page) => void }) {
  const { me, logout } = useAuth();
  return (
    <nav className="sticky top-0 z-10 border-b backdrop-blur" style={{ borderColor: 'var(--panel)', background: 'var(--surface)' }} aria-label="Primary">
      <div className="mx-auto flex w-full max-w-2xl items-center gap-1 px-4 py-2">
        {(['home', 'chat', 'memory', 'cameras', 'feed', 'people'] as Page[]).map((p) => (
          <button
            key={p}
            onClick={() => setPage(p)}
            aria-current={page === p ? 'page' : undefined}
            className="rounded-lg px-3 py-1.5 text-sm font-medium capitalize"
            style={
              page === p
                ? { background: 'var(--panel)', color: 'var(--accent)' }
                : { color: 'var(--muted)' }
            }
          >
            {p === 'feed' ? 'Phone' : p}
          </button>
        ))}
        <span className="ml-auto flex items-center gap-3">
          <span className="hidden text-xs sm:inline" style={{ color: 'var(--muted)' }}>
            {me?.display_name}
          </span>
          <button onClick={logout} className="rounded-lg border px-2 py-1 text-xs" style={{ borderColor: 'var(--muted)' }}>
            Sign out
          </button>
        </span>
      </div>
    </nav>
  );
}

function Shell() {
  const { loading, error, me, status } = useAuth();
  const [page, setPage] = useState<Page>('home');

  if (loading) {
    return (
      <main className="flex min-h-dvh items-center justify-center">
        <p className="text-sm" style={{ color: 'var(--muted)' }}>Starting…</p>
      </main>
    );
  }
  if (error && !status) {
    return (
      <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col items-center justify-center px-4 text-center">
        <h1 className="mb-2 text-xl font-bold">Cannot reach Aegis</h1>
        <p className="mb-4 text-sm" style={{ color: 'var(--muted)' }}>
          {error}
        </p>
        <p className="text-xs" style={{ color: 'var(--muted)' }}>
          Start the backend, then reload. Nothing is faked here — if it is unreachable, this page says so.
        </p>
      </main>
    );
  }
  if (!me) return <LoginForm />;
  return (
    <PanicGate>
      <Nav page={page} setPage={setPage} />
      {page === 'home' && <Home />}
      {page === 'chat' && <Chat />}
      {page === 'memory' && <Memory />}
      {page === 'cameras' && <Cameras />}
      {page === 'feed' && <CameraFeed />}
      {page === 'people' && <People />}
    </PanicGate>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}
