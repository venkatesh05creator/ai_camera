import React, { useState } from 'react';
import { 
  Camera as CameraIcon, 
  Plus, 
  Trash2, 
  Check, 
  Radio, 
  ShieldCheck, 
  RefreshCw, 
  Lock, 
  ExternalLink 
} from 'lucide-react';
import { Camera as CameraType } from '../types';

interface CameraManagementModuleProps {
  cameras?: CameraType[];
  selectedCamera?: CameraType | null;
  onSelectCamera?: (cam: CameraType) => void;
  onRegisterCamera?: (cam: Partial<CameraType> & { connection_secret?: string }) => Promise<void>;
  onDeleteCamera?: (id: string) => Promise<void>;
  onBackToCommandCenter?: () => void;
}

export const CameraManagementModule: React.FC<CameraManagementModuleProps> = ({
  cameras = [],
  selectedCamera = null,
  onSelectCamera = () => {},
  onRegisterCamera = async () => {},
  onDeleteCamera = async () => {},
  onBackToCommandCenter,
}) => {
  const [newCamName, setNewCamName] = useState('');
  const [newCamSourceType, setNewCamSourceType] = useState<'rtsp' | 'webcam' | 'ip_camera' | 'mobile'>('rtsp');
  const [newCamStreamUrl, setNewCamStreamUrl] = useState('');
  const [newCamLocation, setNewCamLocation] = useState('Entrance Gate');
  const [newCamPassword, setNewCamPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCamName.trim()) return;
    setIsSubmitting(true);
    setFeedback(null);
    try {
      await onRegisterCamera({
        name: newCamName.trim(),
        source_type: newCamSourceType,
        stream_url: newCamStreamUrl.trim() || undefined,
        location_label: newCamLocation.trim(),
        connection_secret: newCamPassword.trim() || undefined,
      });
      setFeedback('Camera registered successfully with encrypted credentials.');
      setNewCamName('');
      setNewCamStreamUrl('');
      setNewCamPassword('');
    } catch (err: any) {
      setFeedback(`Registration failed: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 160px)', background: '#070f26', borderRadius: 14, border: '1px solid rgba(0, 210, 255, 0.25)', overflow: 'hidden' }}>
      {/* Top Header */}
      <div style={{ padding: '12px 18px', background: 'rgba(10, 20, 50, 0.95)', borderBottom: '1px solid rgba(0, 210, 255, 0.2)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 34, height: 34, borderRadius: 8, background: 'linear-gradient(135deg, #0284c7 0%, #2563eb 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <CameraIcon size={18} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: '0.96rem', fontWeight: 700, color: '#ffffff' }}>Camera Hardware & Stream Management</span>
              <span style={{ fontSize: '0.66rem', padding: '2px 6px', borderRadius: 4, background: 'rgba(0, 210, 255, 0.15)', color: '#00d2ff', fontWeight: 600 }}>
                {cameras.length} Nodes Connected
              </span>
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
              RTSP streams • ONVIF IP nodes • USB hardware webcams • AES-256-GCM encrypted passwords
            </div>
          </div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 18, display: 'flex', flexDirection: 'column', gap: 16 }}>
        {feedback && (
          <div style={{ padding: '8px 14px', borderRadius: 6, background: feedback.includes('failed') ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)', border: feedback.includes('failed') ? '1px solid #ef4444' : '1px solid #10b981', color: feedback.includes('failed') ? '#fca5a5' : '#86efac', fontSize: '0.78rem' }}>
            {feedback}
          </div>
        )}

        {/* Add Camera Card */}
        <div style={{ background: 'rgba(11, 22, 53, 0.75)', border: '1px solid rgba(0, 210, 255, 0.25)', borderRadius: 12, padding: 16 }}>
          <h3 style={{ margin: '0 0 12px 0', fontSize: '0.88rem', fontWeight: 700, color: '#00d2ff', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Plus size={15} /> Register New Authorized Camera
          </h3>
          <form onSubmit={handleSubmit} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, alignItems: 'end' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.7rem', color: '#94a3b8', marginBottom: 4 }}>Camera Name</label>
              <input
                required
                type="text"
                placeholder="e.g. South Boundary CCTV"
                value={newCamName}
                onChange={(e) => setNewCamName(e.target.value)}
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, background: 'rgba(7, 14, 35, 0.8)', border: '1px solid rgba(0, 210, 255, 0.2)', color: '#fff', fontSize: '0.78rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.7rem', color: '#94a3b8', marginBottom: 4 }}>Protocol / Source Type</label>
              <select
                value={newCamSourceType}
                onChange={(e) => setNewCamSourceType(e.target.value as any)}
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, background: 'rgba(7, 14, 35, 0.8)', border: '1px solid rgba(0, 210, 255, 0.2)', color: '#fff', fontSize: '0.78rem' }}
              >
                <option value="rtsp">RTSP Streaming Feed (rtsp://)</option>
                <option value="webcam">Workstation USB / Integrated Webcam</option>
                <option value="ip_camera">IP Network Camera (ONVIF/HTTP)</option>
                <option value="mobile">Authenticated Mobile Device</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.7rem', color: '#94a3b8', marginBottom: 4 }}>Stream URL / Device Node</label>
              <input
                type="text"
                placeholder={newCamSourceType === 'webcam' ? '0' : 'rtsp://192.168.1.120:554/live'}
                value={newCamStreamUrl}
                onChange={(e) => setNewCamStreamUrl(e.target.value)}
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, background: 'rgba(7, 14, 35, 0.8)', border: '1px solid rgba(0, 210, 255, 0.2)', color: '#fff', fontSize: '0.78rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.7rem', color: '#94a3b8', marginBottom: 4 }}>Location Label</label>
              <input
                type="text"
                placeholder="e.g. North Gate Facility"
                value={newCamLocation}
                onChange={(e) => setNewCamLocation(e.target.value)}
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, background: 'rgba(7, 14, 35, 0.8)', border: '1px solid rgba(0, 210, 255, 0.2)', color: '#fff', fontSize: '0.78rem' }}
              />
            </div>

            <div>
              <label style={{ fontSize: '0.7rem', color: '#94a3b8', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                <Lock size={11} /> Password / Token (Encrypted)
              </label>
              <input
                type="password"
                placeholder="Stream authentication secret"
                value={newCamPassword}
                onChange={(e) => setNewCamPassword(e.target.value)}
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, background: 'rgba(7, 14, 35, 0.8)', border: '1px solid rgba(0, 210, 255, 0.2)', color: '#fff', fontSize: '0.78rem' }}
              />
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              style={{
                height: 33,
                background: 'linear-gradient(135deg, #00d2ff 0%, #2563eb 100%)',
                border: 'none',
                borderRadius: 6,
                padding: '0 16px',
                color: '#fff',
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: isSubmitting ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 6
              }}
            >
              <Plus size={14} /> {isSubmitting ? 'Registering...' : 'Register Camera'}
            </button>
          </form>
        </div>

        {/* Existing Cameras Table */}
        <div style={{ background: 'rgba(11, 22, 53, 0.75)', border: '1px solid rgba(0, 210, 255, 0.25)', borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', background: 'rgba(7, 14, 35, 0.9)', borderBottom: '1px solid rgba(0, 210, 255, 0.15)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.84rem', fontWeight: 700, color: '#fff' }}>Registered Surveillance Cameras ({cameras.length})</span>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.76rem' }}>
              <thead>
                <tr style={{ background: 'rgba(255, 255, 255, 0.02)', color: '#94a3b8', borderBottom: '1px solid rgba(0, 210, 255, 0.1)' }}>
                  <th style={{ padding: '10px 14px' }}>Camera Name</th>
                  <th style={{ padding: '10px 14px' }}>Type</th>
                  <th style={{ padding: '10px 14px' }}>Location</th>
                  <th style={{ padding: '10px 14px' }}>Resolution & FPS</th>
                  <th style={{ padding: '10px 14px' }}>Connection State</th>
                  <th style={{ padding: '10px 14px', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {cameras.map((c) => {
                  const isPrimary = selectedCamera?.id === c.id;
                  return (
                    <tr key={c.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)', color: '#fff' }}>
                      <td style={{ padding: '10px 14px', fontWeight: 600 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <CameraIcon size={14} color="#00d2ff" />
                          <span>{c.name}</span>
                          {isPrimary && (
                            <span style={{ fontSize: '0.62rem', padding: '1px 5px', borderRadius: 4, background: 'rgba(16, 185, 129, 0.2)', color: '#34d399' }}>
                              Primary
                            </span>
                          )}
                        </div>
                      </td>
                      <td style={{ padding: '10px 14px', textTransform: 'uppercase', color: '#94a3b8', fontSize: '0.7rem' }}>
                        {c.source_type}
                      </td>
                      <td style={{ padding: '10px 14px', color: '#cbd5e1' }}>
                        {c.location_label || 'Default Location'}
                      </td>
                      <td style={{ padding: '10px 14px', color: '#cbd5e1' }}>
                        {c.resolution || '1280x720'} • {c.fps ? `${c.fps} FPS` : '30 FPS'}
                      </td>
                      <td style={{ padding: '10px 14px' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '2px 8px', borderRadius: 4, background: c.status === 'online' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)', color: c.status === 'online' ? '#34d399' : '#f87171', fontWeight: 600, fontSize: '0.68rem' }}>
                          <span style={{ width: 5, height: 5, borderRadius: '50%', background: c.status === 'online' ? '#10b981' : '#ef4444' }} />
                          {c.status.toUpperCase()}
                        </span>
                      </td>
                      <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 6 }}>
                          {!isPrimary && (
                            <button
                              onClick={() => onSelectCamera(c)}
                              style={{ padding: '4px 8px', borderRadius: 4, background: 'rgba(0, 210, 255, 0.15)', border: '1px solid rgba(0, 210, 255, 0.3)', color: '#00d2ff', fontSize: '0.68rem', cursor: 'pointer' }}
                            >
                              Make Primary
                            </button>
                          )}
                          <button
                            onClick={() => onDeleteCamera(c.id)}
                            title="Remove camera"
                            style={{ padding: '4px 8px', borderRadius: 4, background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#f87171', fontSize: '0.68rem', cursor: 'pointer' }}
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
