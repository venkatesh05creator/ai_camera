import React, { useEffect, useState } from 'react';
import { DetectionEvent } from '../types';
import { api, getAuthToken } from '../services/api';
import { Clock, Filter, CheckCircle, XCircle, AlertTriangle, Eye, ShieldCheck, Video, Sparkles } from 'lucide-react';
import { AIDossierModal } from '../components/AIDossierModal';

export const EventsTimeline: React.FC = () => {
  const [events, setEvents] = useState<DetectionEvent[]>([]);
  const [filterType, setFilterType] = useState<string>('all');
  const [activeSnapshot, setActiveSnapshot] = useState<string | null>(null);
  const [dossierTarget, setDossierTarget] = useState<{ id: string; name: string } | null>(null);

  const fetchEvents = () => {
    api.getEvents({ limit: 100, event_type: filterType === 'all' ? undefined : filterType })
      .then(setEvents)
      .catch(() => {});
  };

  useEffect(() => {
    fetchEvents();
  }, [filterType]);

  const handleReview = async (id: string, status: 'confirmed' | 'false_positive') => {
    try {
      await api.reviewEvent(id, status);
      fetchEvents();
    } catch (err: any) {
      alert(`Error updating event: ${err.message}`);
    }
  };

  return (
    <div className="page-scroll-container events-timeline-container">
      {/* Top Filter Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {['all', 'person', 'motion', 'alert'].map((type) => {
            const isSel = filterType === type;
            return (
              <button
                key={type}
                onClick={() => setFilterType(type)}
                style={{
                  padding: '7px 14px',
                  borderRadius: '8px',
                  background: isSel ? 'var(--accent-primary)' : 'var(--bg-card)',
                  color: isSel ? '#ffffff' : 'var(--text-muted)',
                  border: isSel ? '1px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
                  cursor: 'pointer',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  textTransform: 'capitalize',
                  transition: 'all 0.15s ease',
                }}
              >
                {type === 'all' ? 'All Events' : type}
              </button>
            );
          })}
        </div>

        <button onClick={fetchEvents} className="btn-secondary" style={{ fontSize: '0.8rem' }}>
          Refresh Timeline
        </button>
      </div>

      {/* Events Stream Table */}
      <div className="glass-card" style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
        {events.length === 0 ? (
          <div style={{ padding: '60px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
            <Clock size={48} color="var(--text-faint)" style={{ margin: '0 auto 12px' }} />
            <p style={{ fontWeight: 600 }}>No Events Recorded</p>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-faint)' }}>Motion and person tracks will appear here in chronological order.</p>
          </div>
        ) : (
          events.map((ev) => {
            const isVerified = Boolean(ev.person_name);
            return (
              <div
                key={ev.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '14px 20px',
                  borderBottom: '1px solid var(--border-subtle)',
                  gap: '16px',
                  transition: 'background 0.15s ease',
                }}
              >
                {/* Event Type Badge & Time */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px', width: '240px' }}>
                  <div style={{
                    width: '36px', height: '36px', borderRadius: '8px',
                    background: isVerified ? 'rgba(16, 185, 129, 0.15)' : ev.event_type === 'person' ? 'rgba(245, 158, 11, 0.15)' : 'rgba(99, 102, 241, 0.15)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    {isVerified ? <ShieldCheck size={18} color="#34d399" /> : ev.event_type === 'person' ? <Eye size={18} color="#fbbf24" /> : <Video size={18} color="#818cf8" />}
                  </div>

                  <div>
                    <span className={`badge-tag ${isVerified ? 'badge-success' : ev.event_type === 'person' ? 'badge-warning' : 'badge-accent'}`}>
                      {isVerified ? 'VERIFIED' : ev.event_type.toUpperCase()}
                    </span>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-faint)', display: 'block', marginTop: '2px' }} className="mono">
                      {new Date(ev.occurred_at).toLocaleTimeString()} • {new Date(ev.occurred_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                {/* Identity & Camera Details */}
                <div style={{ flex: 1 }}>
                  <p style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main)', margin: 0 }}>
                    {isVerified ? ev.person_name : ev.track_id ? `Anonymous Track [${ev.track_id}]` : 'Motion Detection Triggered'}
                  </p>
                  <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                    {ev.camera_name || 'Primary Camera'} • Confidence: {(ev.confidence * 100).toFixed(1)}%
                  </span>
                </div>

                {/* Review Status Indicator */}
                <div style={{ width: '130px' }}>
                  <span style={{
                    fontSize: '0.74rem', fontWeight: 600, padding: '3px 8px', borderRadius: '6px',
                    background: ev.review_status === 'confirmed' ? 'rgba(16, 185, 129, 0.1)' : ev.review_status === 'false_positive' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(255,255,255,0.05)',
                    color: ev.review_status === 'confirmed' ? '#34d399' : ev.review_status === 'false_positive' ? '#f87171' : 'var(--text-muted)',
                  }}>
                    {ev.review_status.toUpperCase()}
                  </span>
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {ev.person_id && ev.person_name && (
                    <button
                      onClick={() => setDossierTarget({ id: ev.person_id!, name: ev.person_name! })}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        background: 'rgba(99, 102, 241, 0.15)',
                        border: '1px solid rgba(99, 102, 241, 0.3)',
                        color: '#818cf8',
                        borderRadius: '6px',
                        padding: '6px 10px',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      <Sparkles size={12} />
                      AI Dossier
                    </button>
                  )}

                  {ev.snapshot_url && (
                    <button
                      onClick={() => setActiveSnapshot(ev.snapshot_url || null)}
                      className="btn-secondary"
                      style={{ padding: '6px 10px', fontSize: '0.75rem' }}
                    >
                      Snapshot
                    </button>
                  )}

                  {ev.review_status !== 'confirmed' && (
                    <button
                      onClick={() => handleReview(ev.id, 'confirmed')}
                      style={{ background: 'none', border: '1px solid rgba(16, 185, 129, 0.3)', color: '#34d399', borderRadius: '6px', padding: '6px 10px', fontSize: '0.75rem', cursor: 'pointer', fontWeight: 600 }}
                    >
                      Confirm
                    </button>
                  )}

                  {ev.review_status !== 'false_positive' && (
                    <button
                      onClick={() => handleReview(ev.id, 'false_positive')}
                      style={{ background: 'none', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#f87171', borderRadius: '6px', padding: '6px 10px', fontSize: '0.75rem', cursor: 'pointer', fontWeight: 600 }}
                    >
                      Flag False
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Snapshot Modal */}
      {activeSnapshot && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }}>
          <div className="glass-card" style={{ padding: '20px', maxWidth: '720px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
              <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Event Snapshot Capture</span>
              <button onClick={() => setActiveSnapshot(null)} style={{ background: 'none', border: 'none', color: '#fff', fontSize: '1.2rem', cursor: 'pointer' }}>✕</button>
            </div>
            <img
              src={`${activeSnapshot}${activeSnapshot.includes('?') ? '&' : '?'}token=${encodeURIComponent(getAuthToken() || '')}`}
              alt="Snapshot"
              style={{ width: '100%', maxHeight: '480px', objectFit: 'contain', borderRadius: '8px' }}
            />
          </div>
        </div>
      )}

      {/* AI Intelligence Dossier Modal */}
      {dossierTarget && (
        <AIDossierModal
          isOpen={Boolean(dossierTarget)}
          personId={dossierTarget.id}
          personName={dossierTarget.name}
          onClose={() => setDossierTarget(null)}
        />
      )}
    </div>
  );
};
