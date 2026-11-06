import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../api';

interface Person {
  id: number;
  name: string;
  consent_ts: string;
  has_template: boolean;
  samples_count: number;
  quality: number | null;
}

export function People() {
  const [people, setPeople] = useState<Person[]>([]);
  const [name, setName] = useState('');
  const [consent, setConsent] = useState('');
  const [enrolFor, setEnrolFor] = useState<number | null>(null);
  const [enrolError, setEnrolError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await api.people();
      setPeople(r.people);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not load people');
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.personCreate(name, consent);
      setName('');
      setConsent('');
      await load();
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : 'Create failed');
    }
  }

  async function uploadImages(personId: number, files: FileList | null) {
    if (!files) return;
    setEnrolError(null);
    const images: string[] = [];
    for (const file of Array.from(files)) {
      const buf = await file.arrayBuffer();
      const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)));
      images.push(b64);
    }
    try {
      await api.personEnrol(personId, images);
      setEnrolFor(null);
      await load();
    } catch (e2) {
      setEnrolError(e2 instanceof Error ? e2.message : 'Enrolment failed');
    }
  }

  async function withdraw(p: Person) {
    if (!window.confirm(`Withdraw consent for ${p.name}? The face template will be permanently deleted.`)) return;
    try {
      await api.personWithdraw(p.id);
      await load();
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : 'Withdraw failed');
    }
  }

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-6">
      <h1 className="mb-1 text-xl font-bold">People</h1>
      <p className="mb-4 text-sm" style={{ color: 'var(--muted)' }}>
        Only people who typed consent can be recognised. Everyone else is “unknown”.
        Templates are AES-256-GCM encrypted and deleted the moment consent is withdrawn.
      </p>

      {error && <p role="alert" className="mb-4 rounded-lg px-3 py-2 text-sm" style={{ background: 'rgba(239,68,68,.15)', color: '#fca5a5' }}>{error}</p>}

      <form onSubmit={create} className="mb-6 grid gap-2 rounded-2xl p-4" style={{ background: 'var(--panel)' }}>
        <h2 className="text-sm font-semibold">Add a person (consent first)</h2>
        <input required value={name} onChange={(e) => setName(e.target.value)}
          placeholder="Name" maxLength={120}
          className="rounded-xl border px-3 py-2 text-base" style={{ borderColor: 'var(--muted)', color: 'var(--text)', background: 'var(--surface)' }}
          aria-label="Person name" autoComplete="off" />
        <textarea required value={consent} onChange={(e) => setConsent(e.target.value)}
          minLength={20} rows={3}
          placeholder="Type the consent statement, e.g. “I, Venki, consent for this device to store an encrypted face template under my name.”"
          className="rounded-xl border px-3 py-2 text-base" style={{ borderColor: 'var(--muted)', color: 'var(--text)', background: 'var(--surface)' }}
          aria-label="Consent statement" />
        <button type="submit" className="rounded-xl bg-cyan-400 px-5 py-2.5 font-semibold text-slate-900">Save consent</button>
      </form>

      <ul className="flex flex-col gap-3">
        {people.map((p) => (
          <li key={p.id} className="rounded-2xl p-4" style={{ background: 'var(--panel)' }}>
            <div className="mb-1 flex items-center justify-between">
              <span className="font-semibold">#{p.id} {p.name}</span>
              <span className="rounded-full px-2 py-0.5 text-xs" style={{ background: 'var(--surface)', color: 'var(--muted)' }}>
                {p.has_template ? `enrolled · ${p.samples_count} samples` : 'no template yet'}
              </span>
            </div>
            <p className="text-xs" style={{ color: 'var(--muted)' }}>
              consent {new Date(p.consent_ts).toLocaleString()}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <button onClick={() => setEnrolFor(enrolFor === p.id ? null : p.id)}
                className="rounded-lg bg-cyan-400 px-3 py-1.5 text-xs font-semibold text-slate-900">
                {p.has_template ? 'Re-enrol' : 'Enrol face'}
              </button>
              <button onClick={() => withdraw(p)}
                className="rounded-lg border px-3 py-1.5 text-xs" style={{ borderColor: 'var(--muted)' }}>
                Withdraw consent
              </button>
            </div>
            {enrolFor === p.id && (
              <div className="mt-2">
                <label className="block rounded-lg border border-dashed px-3 py-2 text-xs" style={{ borderColor: 'var(--muted)', color: 'var(--muted)' }}>
                  Pick 3+ clear, front-facing photos (JPEG). They are processed locally and never stored — only an averaged embedding is kept.
                  <input type="file" accept="image/jpeg" multiple
                    onChange={(e) => uploadImages(p.id, e.target.files)}
                    className="mt-1 block w-full text-xs" aria-label="Enrolment photos" />
                </label>
                {enrolError && <p role="alert" className="mt-1 text-xs text-red-300">{enrolError}</p>}
              </div>
            )}
          </li>
        ))}
      </ul>
      {people.length === 0 && (
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          No people yet. Without enrolment, every face is reported as “unknown”.
        </p>
      )}
    </main>
  );
}
