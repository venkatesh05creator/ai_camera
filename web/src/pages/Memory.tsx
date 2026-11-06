import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';

interface Item {
  id: number;
  kind: string;
  text: string;
  created_at: string;
}

export function Memory() {
  const [items, setItems] = useState<Item[]>([]);
  const [newText, setNewText] = useState('');
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await api.memoryList();
      setItems(r.items);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load memory');
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!newText.trim()) return;
    try {
      await api.memoryCreate('fact', newText.trim());
      setNewText('');
      await load();
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : 'Could not save');
    }
  }

  async function remove(id: number) {
    if (!window.confirm('Delete this memory forever? It cannot be recovered.')) return;
    try {
      await api.memoryDelete(id);
      await load();
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : 'Delete failed');
    }
  }

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-6">
      <h1 className="mb-1 text-xl font-bold">Memory</h1>
      <p className="mb-4 text-sm" style={{ color: 'var(--muted)' }}>
        Facts you teach Aegis. AES-256-GCM encrypted on this device, usable as chat evidence.
      </p>

      {error && <p role="alert" className="mb-4 rounded-lg px-3 py-2 text-sm" style={{ background: 'rgba(239,68,68,.15)', color: '#fca5a5' }}>{error}</p>}

      <form onSubmit={add} className="mb-6 flex gap-2">
        <input
          value={newText}
          onChange={(e) => setNewText(e.target.value)}
          maxLength={2000}
          placeholder="e.g. My dog is named Milo"
          aria-label="New fact"
          className="flex-1 rounded-xl border px-3 py-2.5 text-base outline-none focus:ring-2"
          style={{ borderColor: 'var(--muted)', color: 'var(--text)', background: 'var(--panel)' }}
        />
        <button type="submit" className="rounded-xl bg-cyan-400 px-5 py-2.5 font-semibold text-slate-900">
          Teach
        </button>
      </form>

      <ul className="flex flex-col gap-2">
        {items.map((item) => (
          <li key={item.id} className="flex items-start justify-between gap-3 rounded-xl px-4 py-3" style={{ background: 'var(--panel)' }}>
            <div>
              <p className="text-sm font-medium">{item.text}</p>
              <p className="text-xs" style={{ color: 'var(--muted)' }}>{item.kind} · {item.created_at.slice(0, 10)}</p>
            </div>
            <button onClick={() => remove(item.id)} className="shrink-0 rounded-lg border px-2 py-1 text-xs" style={{ borderColor: 'var(--muted)' }}>
              Delete
            </button>
          </li>
        ))}
      </ul>
      {items.length === 0 && (
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          No memory yet. Add a fact above — the assistant can only cite what you teach it (plus today's audit log).
        </p>
      )}

      <a
        href={api.memoryExportUrl()}
        className="mt-4 inline-block rounded-lg border px-3 py-1.5 text-xs"
        style={{ borderColor: 'var(--muted)' }}
      >
        Export all (JSON download)
      </a>
    </main>
  );
}
