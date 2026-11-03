import React, { useState } from 'react';
import { 
  Video, 
  Globe, 
  Maximize2, 
  RefreshCw, 
  ShieldCheck, 
  Camera as CameraIcon, 
  VideoOff, 
  LayoutGrid, 
  Eye, 
  Radio 
} from 'lucide-react';
import { Camera as CameraType } from '../types';

interface LiveMonitoringModuleProps {
  cameras?: CameraType[];
  selectedCamera?: CameraType | null;
  onSelectCamera?: (cam: CameraType) => void;
  publicCameras?: any[];
  selectedPublicCamera?: any | null;
  onSelectPublicCamera?: (pub: any) => void;
  isLocalWebcamActive?: boolean;
  localVideoRef?: React.MutableRefObject<HTMLVideoElement | null>;
  localStreamRef?: React.MutableRefObject<MediaStream | null>;
  startLocalWebcam?: () => void;
  webcamError?: string | null;
  onBackToCommandCenter?: () => void;
}

export const LiveMonitoringModule: React.FC<LiveMonitoringModuleProps> = ({
  cameras = [],
  selectedCamera = null,
  onSelectCamera = () => {},
  publicCameras = [],
  selectedPublicCamera = null,
  onSelectPublicCamera = () => {},
  isLocalWebcamActive = false,
  localVideoRef,
  localStreamRef,
  startLocalWebcam = () => {},
  webcamError = null,
  onBackToCommandCenter,
}) => {
  const [gridLayout, setGridLayout] = useState<'1x1' | '2x2' | '3x3'>('2x2');
  const [showOverlays, setShowOverlays] = useState<boolean>(true);
  const [snapshotTick, setSnapshotTick] = useState<number>(Date.now());

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 160px)', background: '#070f26', borderRadius: 14, border: '1px solid rgba(0, 210, 255, 0.25)', overflow: 'hidden' }}>
      {/* Top Controls Toolbar */}
      <div style={{ padding: '12px 18px', background: 'rgba(10, 20, 50, 0.95)', borderBottom: '1px solid rgba(0, 210, 255, 0.2)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {onBackToCommandCenter && (
            <button
              onClick={onBackToCommandCenter}
              style={{
                background: 'rgba(255,255,255,0.08)',
                border: '1px solid rgba(255,255,255,0.15)',
                color: '#38bdf8',
                borderRadius: 6,
                padding: '4px 8px',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer',
                marginRight: 6,
              }}
            >
              ← Back
            </button>
          )}
          <div style={{ width: 34, height: 34, borderRadius: 8, background: 'linear-gradient(135deg, #10b981 0%, #0284c7 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Video size={18} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: '0.96rem', fontWeight: 700, color: '#ffffff' }}>Live Multi-Camera Wall</span>
              <span style={{ fontSize: '0.66rem', padding: '2px 6px', borderRadius: 4, background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', fontWeight: 600 }}>
                ● Real-Time Streams
              </span>
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
              Authorized hardware webcam • Verified open municipal feeds • Live connection health & freshness
            </div>
          </div>
        </div>

        {/* Layout Buttons & Overlays Toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ display: 'flex', background: 'rgba(7, 14, 35, 0.8)', padding: 2, borderRadius: 6, border: '1px solid rgba(0, 210, 255, 0.2)' }}>
            {(['1x1', '2x2', '3x3'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setGridLayout(mode)}
                style={{
                  padding: '4px 10px',
                  borderRadius: 4,
                  fontSize: '0.72rem',
                  fontWeight: gridLayout === mode ? 700 : 500,
                  background: gridLayout === mode ? 'rgba(0, 210, 255, 0.25)' : 'transparent',
                  border: 'none',
                  color: gridLayout === mode ? '#00d2ff' : '#94a3b8',
                  cursor: 'pointer'
                }}
              >
                {mode}
              </button>
            ))}
          </div>

          <button
            onClick={() => setShowOverlays(!showOverlays)}
            style={{
              padding: '5px 10px',
              borderRadius: 6,
              fontSize: '0.72rem',
              fontWeight: 600,
              background: showOverlays ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255,255,255,0.06)',
              border: showOverlays ? '1px solid #10b981' : '1px solid rgba(255,255,255,0.15)',
              color: showOverlays ? '#34d399' : '#94a3b8',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 4
            }}
          >
            <Eye size={13} /> {showOverlays ? 'Overlays ON' : 'Overlays OFF'}
          </button>

          <button
            onClick={() => setSnapshotTick(Date.now())}
            title="Refresh stream snapshots"
            style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 6, color: '#cbd5e1', padding: '5px 10px', fontSize: '0.72rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}
          >
            <RefreshCw size={13} /> Refresh
          </button>
        </div>
      </div>

      {/* Video Grid Canvas */}
      <div 
        style={{ 
          flex: 1, 
          overflowY: 'auto', 
          padding: 14, 
          display: 'grid', 
          gridTemplateColumns: gridLayout === '1x1' ? '1fr' : gridLayout === '2x2' ? 'repeat(auto-fit, minmax(360px, 1fr))' : 'repeat(auto-fit, minmax(280px, 1fr))', 
          gap: 12, 
          alignContent: 'start' 
        }}
      >
        {/* TILE 1: Authorized Workstation / Laptop Webcam */}
        <div style={{ background: '#000000', borderRadius: 10, border: '1px solid rgba(16, 185, 129, 0.4)', overflow: 'hidden', position: 'relative', display: 'flex', flexDirection: 'column' }}>
          <div className="pro-video-player aspect-16-9" style={{ position: 'relative', background: '#000', width: '100%', height: '100%' }}>
            {(isLocalWebcamActive || localStreamRef?.current) ? (
              <video
                ref={(el) => {
                  if (localVideoRef) localVideoRef.current = el;
                  if (el && localStreamRef?.current && el.srcObject !== localStreamRef.current) {
                    el.srcObject = localStreamRef.current;
                    el.play().catch(() => {});
                  }
                }}
                autoPlay
                playsInline
                muted
                style={{ width: '100%', height: '100%', objectFit: 'cover', transform: 'scaleX(-1)' }}
              />
            ) : (
              <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: 'radial-gradient(circle, #0c1836 0%, #030712 100%)', color: '#94a3b8', padding: 14, textAlign: 'center' }}>
                <VideoOff size={32} color="#f59e0b" style={{ marginBottom: 6 }} />
                <div style={{ color: '#fff', fontSize: '0.8rem', fontWeight: 700, marginBottom: 4 }}>Laptop Webcam</div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8', maxWidth: 220, marginBottom: 10 }}>{webcamError || 'Camera initializing...'}</div>
                <button onClick={startLocalWebcam} style={{ background: 'linear-gradient(135deg, #0284c7 0%, #2563eb 100%)', color: '#fff', border: 'none', borderRadius: 6, padding: '4px 12px', fontSize: '0.7rem', cursor: 'pointer', fontWeight: 700 }}>
                  Retry Camera
                </button>
              </div>
            )}

            {/* Live Badge */}
            <div style={{ position: 'absolute', top: 8, left: 8, background: 'rgba(0,0,0,0.75)', borderRadius: 4, padding: '2px 8px', fontSize: '0.68rem', color: '#34d399', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981' }} />
              LIVE WEBCAM
            </div>

            {/* Overlays */}
            {showOverlays && (
              <div style={{ position: 'absolute', bottom: 8, left: 8, right: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0,0,0,0.75)', padding: '4px 8px', borderRadius: 4, fontSize: '0.66rem', color: '#94a3b8' }}>
                <span style={{ color: '#fff', fontWeight: 600 }}>Workstation Node 0</span>
                <span>1280x720 • 30 FPS • Local Hardware</span>
              </div>
            )}
          </div>
        </div>

        {/* TILES: Public Live Webcams (Times Square, Shibuya, etc.) */}
        {publicCameras.map((pub) => (
          <div key={pub.id} style={{ background: '#000000', borderRadius: 10, border: '1px solid rgba(0, 210, 255, 0.25)', overflow: 'hidden', position: 'relative', display: 'flex', flexDirection: 'column' }}>
            <div className="pro-video-player aspect-16-9" style={{ position: 'relative', background: '#000', width: '100%', height: '100%' }}>
              {pub.embed_url ? (
                <iframe
                  src={pub.embed_url}
                  title={pub.name}
                  style={{ width: '100%', height: '100%', border: 'none', background: '#000' }}
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                />
              ) : pub.preview_url ? (
                <img
                  src={`${pub.preview_url}${pub.preview_url.includes('?') ? '&' : '?'}t=${snapshotTick}`}
                  alt={pub.name}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  onError={(e) => {
                    (e.target as HTMLElement).style.display = 'none';
                  }}
                />
              ) : (
                <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#64748b', fontSize: '0.74rem' }}>
                  <Radio size={28} color="#00d2ff" style={{ marginBottom: 6 }} />
                  <span>{pub.name}</span>
                </div>
              )}

              {/* Status Badge */}
              <div style={{ position: 'absolute', top: 8, left: 8, background: 'rgba(0,0,0,0.75)', borderRadius: 4, padding: '2px 8px', fontSize: '0.68rem', color: pub.stream_type === 'EMBED_PLAYER' ? '#00d2ff' : '#f59e0b', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 5 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: pub.stream_type === 'EMBED_PLAYER' ? '#00d2ff' : '#f59e0b' }} />
                {pub.stream_type === 'EMBED_PLAYER' ? 'LIVE STREAM' : `SNAPSHOT (${pub.refresh_interval_s || 60}s)`}
              </div>

              {/* Overlays */}
              {showOverlays && (
                <div style={{ position: 'absolute', bottom: 8, left: 8, right: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0,0,0,0.75)', padding: '4px 8px', borderRadius: 4, fontSize: '0.66rem', color: '#94a3b8' }}>
                  <span style={{ color: '#fff', fontWeight: 600 }}>{pub.name}</span>
                  <span>{pub.location || 'Global Open Feed'}</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
