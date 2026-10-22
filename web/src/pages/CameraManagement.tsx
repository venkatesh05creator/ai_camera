import React, { useState } from 'react';
import { Camera } from '../types';
import { api } from '../services/api';
import { Camera as CameraIcon, Plus, Trash2, Video, Globe, Smartphone, Laptop, CheckCircle, RefreshCw } from 'lucide-react';

interface CameraManagementProps {
  cameras: Camera[];
  onRefresh: () => void;
}

export const CameraManagement: React.FC<CameraManagementProps> = ({ cameras, onRefresh }) => {
  const [showModal, setShowModal] = useState(false);
  const [camName, setCamName] = useState('');
  const [camType, setCamType] = useState<'webcam' | 'rtsp' | 'ip_camera' | 'mobile'>('webcam');
  const [camLocation, setCamLocation] = useState('');
  const [streamUrl, setStreamUrl] = useState('');

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!camName.trim()) return;

    try {
      await api.registerCamera({
        name: camName,
        source_type: camType,
        location_label: camLocation,
        stream_url: streamUrl || '0',
      });
      setShowModal(false);
      setCamName('');
      setCamLocation('');
      setStreamUrl('');
      onRefresh();
    } catch (err: any) {
      alert(`Failed to add camera: ${err.message}`);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Are you sure you want to disconnect and remove "${name}"?`)) return;
    try {
      await api.deleteCamera(id);
      onRefresh();
    } catch (err: any) {
      alert(`Error deleting camera: ${err.message}`);
    }
  };

  const getIcon = (type: string) => {
    if (type === 'mobile') return <Smartphone size={18} color="#06b6d4" />;
    if (type === 'rtsp' || type === 'ip_camera') return <Globe size={18} color="#818cf8" />;
    return <Laptop size={18} color="#10b981" />;
  };

  return (
    <div className="page-scroll-container camera-management-container">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0 }}>Registered Camera Inventory</h3>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: '2px 0 0' }}>Manage webcams, network RTSP feeds, and paired mobile cameras</p>
        </div>

        <button onClick={() => setShowModal(true)} className="btn-primary">
          <Plus size={16} />
          <span>Add New Camera</span>
        </button>
      </div>

      {/* Camera Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
        {cameras.map((cam) => (
          <div key={cam.id} className="glass-card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '38px', height: '38px', borderRadius: '8px', background: 'rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {getIcon(cam.source_type)}
                </div>
                <div>
                  <h4 style={{ fontSize: '0.98rem', fontWeight: 700, margin: 0 }}>{cam.name}</h4>
                  <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>{cam.location_label || 'Default Location'}</span>
                </div>
              </div>

              <span className="badge-tag badge-success">
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981' }} className="pulse-online" />
                <span>ONLINE</span>
              </span>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.02)', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--border-subtle)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.75rem' }}>
              <div>
                <span style={{ color: 'var(--text-faint)' }}>SOURCE TYPE</span>
                <p style={{ fontWeight: 600, margin: '2px 0 0', textTransform: 'uppercase' }}>{cam.source_type}</p>
              </div>
              <div>
                <span style={{ color: 'var(--text-faint)' }}>FRAME RESOLUTION</span>
                <p style={{ fontWeight: 600, margin: '2px 0 0' }} className="mono">{cam.resolution}</p>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '8px', borderTop: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-faint)' }} className="mono">
                Stream: {cam.stream_url || 'Default Device Index'}
              </span>

              <button
                onClick={() => handleDelete(cam.id, cam.name)}
                style={{ background: 'none', border: 'none', color: '#f87171', cursor: 'pointer', padding: '4px', display: 'flex', alignItems: 'center' }}
                title="Remove Camera"
              >
                <Trash2 size={16} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Add Camera Modal */}
      {showModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }}>
          <form onSubmit={handleRegister} className="glass-card" style={{ width: '460px', padding: '26px', background: 'var(--bg-card)' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, margin: '0 0 16px' }}>Register Camera Node</h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>Camera Name *</label>
                <input
                  type="text"
                  required
                  value={camName}
                  onChange={(e) => setCamName(e.target.value)}
                  placeholder="e.g. Front Entrance Camera"
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', background: 'var(--bg-main)', border: '1px solid var(--border-subtle)', color: '#fff', fontSize: '0.85rem' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>Source Type</label>
                <select
                  value={camType}
                  onChange={(e) => setCamType(e.target.value as any)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', background: 'var(--bg-main)', border: '1px solid var(--border-subtle)', color: '#fff', fontSize: '0.85rem' }}
                >
                  <option value="webcam">Local / USB Webcam</option>
                  <option value="rtsp">CCTV / RTSP Stream</option>
                  <option value="ip_camera">Network IP Camera (HTTP/ONVIF)</option>
                  <option value="mobile">Android / iOS Mobile Device</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>Location Label</label>
                <input
                  type="text"
                  value={camLocation}
                  onChange={(e) => setCamLocation(e.target.value)}
                  placeholder="e.g. Hallway / East Gate"
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', background: 'var(--bg-main)', border: '1px solid var(--border-subtle)', color: '#fff', fontSize: '0.85rem' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>Stream URL or Device Index</label>
                <input
                  type="text"
                  value={streamUrl}
                  onChange={(e) => setStreamUrl(e.target.value)}
                  placeholder="0 (for webcam) or rtsp://user:pass@192.168.1.50:554/live"
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', background: 'var(--bg-main)', border: '1px solid var(--border-subtle)', color: '#fff', fontSize: '0.85rem' }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' }}>
              <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">
                Cancel
              </button>
              <button type="submit" className="btn-primary">
                Register Device
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
