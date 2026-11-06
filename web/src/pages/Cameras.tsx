import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../api';

type Camera = {
  id: number; name: string; kind: string; source: string;
  enabled: boolean; retention_days: number; running: boolean;
  health: { status: string; error?: string | null; fps?: number | null };
};

export function Cameras() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [events, setEvents] = useState<Record<number, Array<{
    id: number; ts: string; kind: string; person_count: number;
    motion_score: number; snapshot_status: string; has_snapshot: boolean;
  }>>>({});
  const [snaps, setSnaps] = useState<Record<string, string>>({});
  const [notifs, setNotifs] = useState<Array<{ id: number; title: string; body: string; is_read: boolean }>>([]);
  const [newToken, setNewToken] = useState<{ name: string; token: string } | null>(null);
  const [form, setForm] = useState({ name: '', kind: 'webcam', source: '' });
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [cams, n] = await Promise.all([api.cameras(), api.notifications()]);
      setCameras(cams);
      setNotifs(n.items);
      setError(null);
      for (const c of cams) {
        const ev = await api.cameraEvents(c.id).catch(() => null);
        if (ev) setEvents((prev) => ({ ...prev, [c.id]: ev.items }));
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not load cameras');
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    try {
      const c = await api.cameraCreate(form.name, form.kind, form.source);
      setNewToken({ name: c.name, token: c.token });
      setForm({ name: '', kind: 'webcam', source: '' });
      await load();
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : 'Create failed');
    }
  }

  async function toggle(c: Camera) {
    try {
      if (c.running) await api.cameraStop(c.id);
      else await api.cameraStart(c.id);
      await load();
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : 'Toggle failed');
    }
  }

  async function showSnap(cameraId: number, eventId: number) {
    const key = `${cameraId}:${eventId}`;
    if (snaps[key]) return;
    try {
      const blob = await api.cameraSnapshot(cameraId, eventId);
      setSnaps((prev) => ({ ...prev, [key]: URL.createObjectURL(blob) }));
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : 'Snapshot failed');
    }
  }

  async function purge() {
    if (!window.confirm('Purge expired camera events now?')) return;
    const r = await api.purgeCameras();
    setError(`Purged ${r.removed.events} events, ${r.removed.notifications} notifications.`);
    await load();
  }

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-6">
      <h1 className="mb-1 text-xl font-bold">Cameras</h1>
      <p className="mb-4 text-sm" style={{ color: 'var(--muted)' }}>
        Motion-gated person detection, encrypted snapshots with faces blurred. No face recognition
        until consent enrolment (Phase 5).
      </p>

      {error && <p role="alert" className="mb-4 rounded-lg px-3 py-2 text-sm" style={{ background: 'rgba(239,68,68,.15)', color: '#fca5a5' }}>{error}</p>}

      {newToken && (
        <div className="mb-4 rounded-xl px-4 py-3 text-sm" style={{ background: 'var(--panel)' }}>
          <p className="font-semibold">Token for “{newToken.name}” — save it now (never shown again):</p>
          <code className="block break-all rounded bg-black/30 px-2 py-1 text-xs">{newToken.token}</code>
        </div>
      )}

      <form onSubmit={create} className="mb-6 grid gap-2 rounded-2xl p-4" style={{ background: 'var(--panel)' }}>
        <h2 className="text-sm font-semibold">Add camera</h2>
        <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="Name (e.g. Desk)" maxLength={120}
          className="rounded-xl border px-3 py-2 text-base" style={{ borderColor: 'var(--muted)', color: 'var(--text)', background: 'var(--surface)' }}
          aria-label="Camera name" />
        <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}
          className="rounded-xl border px-3 py-2 text-base" style={{ borderColor: 'var(--muted)', color: 'var(--text)', background: 'var(--surface)' }}
          aria-label="Camera kind">
          <option value="webcam">Webcam (this machine)</option>
          <option value="phone">Phone (PWA frames)</option>
          <option value="rtsp">RTSP / IP camera</option>
        </select>
        <input required value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })}
          placeholder={form.kind === 'rtsp' ? 'rtsp://camera/stream' : form.kind === 'webcam' ? '0 (index)' : 'label / description'}
          maxLength={500}
          className="rounded-xl border px-3 py-2 text-base" style={{ borderColor: 'var(--muted)', color: 'var(--text)', background: 'var(--surface)' }}
          aria-label="Camera source" />
        <button type="submit" className="rounded-xl bg-cyan-400 px-5 py-2.5 font-semibold text-slate-900">Add camera</button>
      </form>

      <ul className="flex flex-col gap-3">
        {cameras.map((c) => (
          <li key={c.id} className="rounded-2xl p-4" style={{ background: 'var(--panel)' }}>
            <div className="mb-1 flex items-center justify-between">
              <span className="font-semibold">#{c.id} {c.name} <span className="text-xs" style={{ color: 'var(--muted)' }}>({c.kind})</span></span>
              <span className={`rounded-full px-2 py-0.5 text-xs ${c.health.status === 'online' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-red-500/20 text-red-300'}`}>
                {c.health.status}{c.running ? ' · live' : ''}
              </span>
            </div>
            <p className="text-xs" style={{ color: 'var(--muted)' }}>
              source: {c.source} · retention {c.retention_days}d
              {c.health.fps ? ` · ${c.health.fps} fps` : ''}
              {c.health.error ? ` · error: ${c.health.error}` : ''}
            </p>
            <div className="mt-2 flex gap-2">
              <button onClick={() => toggle(c)} className="rounded-lg bg-cyan-400 px-3 py-1.5 text-xs font-semibold text-slate-900">
                {c.running ? 'Stop' : 'Start'}
              </button>
            </div>
            {(events[c.id]?.length ?? 0) > 0 && (
              <details className="mt-2">
                <summary className="cursor-pointer text-xs" style={{ color: 'var(--muted)' }}>
                  Events ({events[c.id]?.length})
                </summary>
                <ul className="mt-1 flex flex-col gap-1">
                  {events[c.id]?.slice(0, 8).map((ev) => (
                    <li key={ev.id} className="flex flex-wrap items-center gap-2 text-xs">
                      <span>{new Date(ev.ts).toLocaleString()}</span>
                      <span>{ev.kind}: {ev.person_count} person(s), motion {(ev.motion_score * 100).toFixed(1)}%</span>
                      {ev.has_snapshot ? (
                        <button onClick={() => showSnap(c.id, ev.id)} className="rounded border px-1.5 py-0.5" style={{ borderColor: 'var(--muted)' }}>View snapshot</button>
                      ) : (
                        <span style={{ color: 'var(--muted)' }}>snapshot: {ev.snapshot_status}</span>
                      )}
                      {snaps[`${c.id}:${ev.id}`] && <img src={snaps[`${c.id}:${ev.id}`]} alt="snapshot" className="w-full rounded-lg" />}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </li>
        ))}
      </ul>
      {cameras.length === 0 && (
        <p className="text-sm" style={{ color: 'var(--muted)' }}>No cameras yet. Add a webcam, a phone, or an RTSP feed above.</p>
      )}

      <section className="mt-6 rounded-2xl p-4" style={{ background: 'var(--panel)' }} aria-label="Notifications">
        <h2 className="mb-2 text-sm font-semibold">Notifications</h2>
        {notifs.length === 0 ? (
          <p className="text-xs" style={{ color: 'var(--muted)' }}>None yet — person events and camera failures will appear here.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {notifs.slice(0, 10).map((n) => (
              <li key={n.id} className="flex items-start justify-between gap-3 text-xs">
                <span><strong>{n.title}</strong> — {n.body}</span>
                {!n.is_read && (
                  <button onClick={() => api.notificationRead(n.id).then(load)}
                    className="shrink-0 rounded border px-1.5 py-0.5" style={{ borderColor: 'var(--muted)' }}>Mark read</button>
                )}
              </li>
            ))}
          </ul>
        )}
        <button onClick={purge} className="mt-3 rounded-lg border px-3 py-1.5 text-xs" style={{ borderColor: 'var(--muted)' }}>
          Purge expired events now
        </button>
      </section>
    </main>
  );
}
