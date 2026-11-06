import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../api';

export function CameraFeed() {
  const [cameraId, setCameraId] = useState('');
  const [token, setToken] = useState('');
  const [active, setActive] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const busyRef = useRef(false);

  const stop = useCallback(() => {
    setActive(false);
    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => stop, [stop]);

  async function captureOnce() {
    const video = videoRef.current;
    if (!video || !cameraId || busyRef.current) return;
    const canvas = canvasRef.current ?? document.createElement('canvas');
    canvas.width = 640;
    canvas.height = 480;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, 640, 480);
    const blob: Blob | null = await new Promise((res) => canvas.toBlob(res, 'image/jpeg', 0.7));
    if (!blob) return;
    busyRef.current = true;
    try {
      const r = await api.ingestFrame(Number(cameraId), token, blob);
      setResult(`motion ${(r.motion_score * 100).toFixed(1)}% · ${r.persons} person(s) @ ${new Date().toLocaleTimeString()}`);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? `${e.message} (code: ${e.code})` : 'Frame rejected');
    } finally {
      busyRef.current = false;
    }
  }

  async function start() {
    setError(null);
    setResult(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' }, audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
      setActive(true);
      timerRef.current = window.setInterval(captureOnce, 3000);
      captureOnce();
    } catch {
      setError('Camera access denied — allow the browser camera permission, or use a desktop webcam instead.');
    }
  }

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-6">
      <h1 className="mb-1 text-xl font-bold">Phone camera</h1>
      <p className="mb-4 text-sm" style={{ color: 'var(--muted)' }}>
        This phone streams authenticated frames to Aegis (one every 3s, each HMAC-signed
        with your camera token — anything rejected is shown, nothing is uploaded silently).
      </p>

      <div className="mb-4 grid gap-2">
        <label className="block text-sm">
          Camera ID
          <input
            value={cameraId}
            onChange={(e) => setCameraId(e.target.value.replace(/\D/g, ''))}
            inputMode="numeric"
            placeholder="e.g. 1"
            className="mt-1 w-full rounded-xl border px-3 py-2 text-base"
            style={{ borderColor: 'var(--muted)', color: 'var(--text)', background: 'var(--panel)' }}
            aria-label="Camera ID"
          />
        </label>
        <label className="block text-sm">
          Camera token (shown once when the camera was created)
          <input
            value={token}
            onChange={(e) => setToken(e.target.value)}
            type="password"
            className="mt-1 w-full rounded-xl border px-3 py-2 text-base"
            style={{ borderColor: 'var(--muted)', color: 'var(--text)', background: 'var(--panel)' }}
            aria-label="Camera token"
            autoComplete="off"
          />
        </label>
      </div>

      <div className="mb-4 flex gap-2">
        {!active ? (
          <button onClick={start} disabled={!cameraId || !token}
            className="rounded-xl bg-cyan-400 px-5 py-2.5 font-semibold text-slate-900 disabled:opacity-50">
            Start streaming
          </button>
        ) : (
          <button onClick={stop}
            className="rounded-xl bg-red-500 px-5 py-2.5 font-semibold text-white">
            Stop
          </button>
        )}
      </div>

      {active && (
        <div className="mb-4 overflow-hidden rounded-2xl" style={{ background: 'var(--panel)' }}>
          <video ref={videoRef} autoPlay playsInline muted className="w-full" aria-label="Camera preview" />
        </div>
      )}

      {result && <p className="text-sm" style={{ color: 'var(--muted)' }}>{result}</p>}
      {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
    </main>
  );
}
