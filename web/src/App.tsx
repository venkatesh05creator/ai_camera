import { AuthProvider, useAuth } from './auth';
import { LoginForm } from './pages/Login';
import { Home } from './pages/Home';

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

function Shell() {
  const { loading, error, me, status } = useAuth();

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
      <Home />
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
