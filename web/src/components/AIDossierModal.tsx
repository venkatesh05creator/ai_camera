import React, { useState, useEffect } from 'react';
import {
  X,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Globe,
  Camera,
  Clock,
  Sparkles,
  ExternalLink,
  RefreshCw,
  FileText,
  UserCheck,
  AlertTriangle,
  Building,
  CheckCircle2,
} from 'lucide-react';
import { AIPersonDossier } from '../types';
import { api } from '../services/api';

interface AIDossierModalProps {
  personId: string;
  personName: string;
  isOpen: boolean;
  onClose: () => void;
}

export const AIDossierModal: React.FC<AIDossierModalProps> = ({
  personId,
  personName,
  isOpen,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<'security' | 'online' | 'sightings' | 'copilot'>('security');
  const [dossier, setDossier] = useState<AIPersonDossier | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanningOnline, setScanningOnline] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copilotQuery, setCopilotQuery] = useState('');
  const [copilotAnswer, setCopilotAnswer] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && personId) {
      loadDossier();
    }
  }, [isOpen, personId]);

  const loadDossier = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getPersonDossier(personId, true);
      setDossier(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load AI Dossier');
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerOnlineScan = async () => {
    setScanningOnline(true);
    try {
      await api.triggerOnlineLookup(personId);
      await loadDossier();
    } catch (err: any) {
      setError(err.message || 'Online intelligence scan failed');
    } finally {
      setScanningOnline(false);
    }
  };

  const handleAskCopilot = async (q: string) => {
    setCopilotAnswer(null);
    try {
      const res = await api.askCopilot(`Regarding ${personName}: ${q}`);
      setCopilotAnswer(res.answer);
    } catch (err: any) {
      setCopilotAnswer(`Query failed: ${err.message}`);
    }
  };

  if (!isOpen) return null;

  const riskLevel = dossier?.security_assessment.risk_level || 'LOW';
  const riskColor = riskLevel === 'LOW' ? '#10b981' : riskLevel === 'MEDIUM' ? '#f59e0b' : '#ef4444';

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(5, 8, 14, 0.85)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '900px',
          maxHeight: '90vh',
          background: 'var(--bg-card, #11141c)',
          border: '1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))',
          borderRadius: '16px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 30px rgba(99, 102, 241, 0.15)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: '20px 24px',
            borderBottom: '1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'linear-gradient(90deg, rgba(99, 102, 241, 0.08) 0%, transparent 100%)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div
              style={{
                width: '46px',
                height: '46px',
                borderRadius: '12px',
                background: 'linear-gradient(135deg, #6366f1 0%, #3b82f6 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 0 20px rgba(99, 102, 241, 0.4)',
              }}
            >
              <Sparkles size={24} color="#ffffff" />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-main, #f1f5f9)', margin: 0 }}>
                  {personName}
                </h2>
                <span
                  style={{
                    background: `${riskColor}22`,
                    color: riskColor,
                    border: `1px solid ${riskColor}44`,
                    fontSize: '0.72rem',
                    padding: '2px 8px',
                    borderRadius: '6px',
                    fontWeight: 700,
                    letterSpacing: '0.04em',
                  }}
                >
                  RISK: {riskLevel} ({dossier?.security_assessment.risk_score || 10}/100)
                </span>
                {dossier?.has_active_consent && (
                  <span
                    style={{
                      background: 'rgba(16, 185, 129, 0.15)',
                      color: '#34d399',
                      border: '1px solid rgba(16, 185, 129, 0.3)',
                      fontSize: '0.72rem',
                      padding: '2px 8px',
                      borderRadius: '6px',
                      fontWeight: 600,
                    }}
                  >
                    CONSENT VERIFIED
                  </span>
                )}
              </div>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted, #94a3b8)', margin: '4px 0 0' }}>
                AI Surveillance Intelligence Dossier & Online Background Analysis
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={handleTriggerOnlineScan}
              disabled={scanningOnline}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                background: 'rgba(99, 102, 241, 0.15)',
                border: '1px solid rgba(99, 102, 241, 0.3)',
                color: '#818cf8',
                padding: '6px 12px',
                borderRadius: '8px',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <RefreshCw size={14} className={scanningOnline ? 'spin-icon' : ''} />
              {scanningOnline ? 'Scanning OSINT...' : 'Run Web Scan'}
            </button>
            <button
              onClick={onClose}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted, #94a3b8)',
                cursor: 'pointer',
                padding: '6px',
                borderRadius: '8px',
              }}
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div
          style={{
            display: 'flex',
            padding: '0 24px',
            borderBottom: '1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))',
            background: 'rgba(0, 0, 0, 0.2)',
            gap: '8px',
          }}
        >
          {[
            { id: 'security', label: 'Security & Telemetry', icon: Shield },
            { id: 'online', label: 'Online / Directory Intelligence', icon: Globe },
            { id: 'sightings', label: 'Camera Timeline', icon: Camera },
            { id: 'copilot', label: 'AI Copilot Q&A', icon: Sparkles },
          ].map((t) => {
            const Icon = t.icon;
            const isTabActive = activeTab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id as any)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '12px 14px',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: isTabActive ? '2px solid #6366f1' : '2px solid transparent',
                  color: isTabActive ? '#818cf8' : 'var(--text-muted, #94a3b8)',
                  fontWeight: isTabActive ? 600 : 500,
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                }}
              >
                <Icon size={16} />
                {t.label}
              </button>
            );
          })}
        </div>

        {/* Modal Body */}
        <div style={{ padding: '24px', overflowY: 'auto', flex: 1 }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
              <RefreshCw size={28} className="spin-icon" style={{ margin: '0 auto 12px' }} />
              <p>Synthesizing AI Intelligence Dossier...</p>
            </div>
          ) : error ? (
            <div style={{ padding: '20px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '10px', color: '#f87171' }}>
              <AlertTriangle size={20} style={{ marginBottom: '8px' }} />
              <p>{error}</p>
            </div>
          ) : dossier ? (
            <>
              {/* TAB 1: Security & Telemetry */}
              {activeTab === 'security' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {/* Executive AI Narrative Card */}
                  <div
                    style={{
                      padding: '18px',
                      background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(59, 130, 246, 0.05) 100%)',
                      border: '1px solid rgba(99, 102, 241, 0.3)',
                      borderRadius: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                      <Sparkles size={18} color="#818cf8" />
                      <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#818cf8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        AI Synthesis & Behavioral Analysis
                      </span>
                    </div>
                    <p style={{ fontSize: '0.9rem', color: 'var(--text-main, #f1f5f9)', lineHeight: 1.6, margin: 0 }}>
                      {dossier.ai_executive_summary}
                    </p>
                  </div>

                  {/* 3 Metric Cards */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px' }}>
                    <div style={{ padding: '16px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--border-subtle)', borderRadius: '10px' }}>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Total Sightings</span>
                      <div style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--text-main)', marginTop: '4px' }}>
                        {dossier.surveillance_telemetry.total_sightings}
                      </div>
                      <span style={{ fontSize: '0.72rem', color: '#10b981' }}>Across all verified cameras</span>
                    </div>

                    <div style={{ padding: '16px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--border-subtle)', borderRadius: '10px' }}>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Recorded Dwell Time</span>
                      <div style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--text-main)', marginTop: '4px' }}>
                        {dossier.surveillance_telemetry.estimated_dwell_minutes}m
                      </div>
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Cumulative presence</span>
                    </div>

                    <div style={{ padding: '16px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--border-subtle)', borderRadius: '10px' }}>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Biometric Templates</span>
                      <div style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--text-main)', marginTop: '4px' }}>
                        {dossier.templates_count}
                      </div>
                      <span style={{ fontSize: '0.72rem', color: '#818cf8' }}>FaceNet 512-dim (AES-GCM)</span>
                    </div>
                  </div>

                  {/* Risk Assessment Breakdown */}
                  <div style={{ padding: '18px', background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--border-subtle)', borderRadius: '12px' }}>
                    <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <ShieldCheck size={18} color={riskColor} />
                      Security Risk Assessment & Compliance
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {dossier.security_assessment.risk_factors.map((factor, idx) => (
                        <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                          <CheckCircle2 size={16} color={riskColor} />
                          <span>{factor}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: Online & Directory Intelligence */}
              {activeTab === 'online' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {/* Verified Digital Identity Header */}
                  <div style={{ padding: '20px', background: 'rgba(59, 130, 246, 0.08)', border: '1px solid rgba(59, 130, 246, 0.3)', borderRadius: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                      <Globe size={22} color="#60a5fa" />
                      <div>
                        <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#f1f5f9', margin: 0 }}>
                          Online & Corporate Directory Verification
                        </h3>
                        <span style={{ fontSize: '0.75rem', color: '#93c5fd' }}>
                          Public record scan, directory validation, and external affiliation checks
                        </span>
                      </div>
                    </div>
                    <p style={{ fontSize: '0.88rem', color: 'var(--text-main)', lineHeight: 1.6, margin: 0 }}>
                      {dossier.online_intelligence?.online_summary || 'Online intelligence report compiled.'}
                    </p>
                  </div>

                  {/* Verified Channels */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      Verified Online Indicators
                    </h4>
                    {dossier.online_intelligence?.verified_channels.map((chan, idx) => (
                      <div
                        key={idx}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '12px 16px',
                          background: 'rgba(255, 255, 255, 0.03)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: '8px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <Building size={16} color="#818cf8" />
                          <div>
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block' }}>{chan.type}</span>
                            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main)' }}>{chan.value}</span>
                          </div>
                        </div>
                        <span
                          style={{
                            background: chan.verified ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                            color: chan.verified ? '#34d399' : '#f87171',
                            fontSize: '0.7rem',
                            padding: '3px 8px',
                            borderRadius: '6px',
                            fontWeight: 600,
                          }}
                        >
                          {chan.verified ? 'VERIFIED' : 'UNCONFIRMED'}
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* Clearance and Sanctions Details */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                    <div style={{ padding: '14px', background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--border-subtle)', borderRadius: '8px' }}>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Clearance Tier</span>
                      <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-main)', marginTop: '4px' }}>
                        {dossier.online_intelligence?.clearance_tier || 'Standard Access'}
                      </div>
                    </div>
                    <div style={{ padding: '14px', background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--border-subtle)', borderRadius: '8px' }}>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Public Records & Sanctions</span>
                      <div style={{ fontSize: '0.95rem', fontWeight: 600, color: '#34d399', marginTop: '4px' }}>
                        {dossier.online_intelligence?.public_records_check || 'Clean Record'}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 3: Camera Timeline */}
              {activeTab === 'sightings' && (
                <div>
                  <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '14px', textTransform: 'uppercase' }}>
                    Recent Sensor Sightings & Verification History
                  </h4>
                  {dossier.surveillance_telemetry.recent_sightings.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
                      No camera events recorded yet for this person.
                    </div>
                  ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)', textAlign: 'left' }}>
                          <th style={{ padding: '8px 12px' }}>Camera Zone</th>
                          <th style={{ padding: '8px 12px' }}>Timestamp</th>
                          <th style={{ padding: '8px 12px' }}>Confidence</th>
                          <th style={{ padding: '8px 12px' }}>Review Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dossier.surveillance_telemetry.recent_sightings.map((s, idx) => (
                          <tr key={idx} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                            <td style={{ padding: '10px 12px', color: 'var(--text-main)', fontWeight: 600 }}>{s.camera_name}</td>
                            <td style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>
                              {new Date(s.timestamp).toLocaleTimeString()} ({new Date(s.timestamp).toLocaleDateString()})
                            </td>
                            <td style={{ padding: '10px 12px', color: '#10b981', fontWeight: 600 }}>{s.confidence}%</td>
                            <td style={{ padding: '10px 12px' }}>
                              <span style={{ background: 'rgba(99, 102, 241, 0.1)', color: '#818cf8', padding: '2px 8px', borderRadius: '4px', fontSize: '0.72rem' }}>
                                {s.review_status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}

              {/* TAB 4: Copilot Q&A */}
              {activeTab === 'copilot' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div style={{ padding: '14px', background: 'rgba(99, 102, 241, 0.08)', borderRadius: '8px', border: '1px solid rgba(99, 102, 241, 0.2)' }}>
                    <span style={{ fontSize: '0.8rem', color: '#818cf8', fontWeight: 600, display: 'block', marginBottom: '8px' }}>
                      Ask AI Copilot about {personName}:
                    </span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {[
                        'Summarize visit patterns and frequency',
                        'Check for after-hours sightings',
                        'Validate online corporate clearance',
                        'Audit consent expiration status',
                      ].map((prompt, idx) => (
                        <button
                          key={idx}
                          onClick={() => {
                            setCopilotQuery(prompt);
                            handleAskCopilot(prompt);
                          }}
                          style={{
                            background: 'rgba(255, 255, 255, 0.04)',
                            border: '1px solid var(--border-subtle)',
                            color: 'var(--text-main)',
                            padding: '4px 10px',
                            borderRadius: '6px',
                            fontSize: '0.75rem',
                            cursor: 'pointer',
                          }}
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '8px' }}>
                    <input
                      type="text"
                      placeholder="Type custom security inquiry..."
                      value={copilotQuery}
                      onChange={(e) => setCopilotQuery(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleAskCopilot(copilotQuery)}
                      style={{
                        flex: 1,
                        background: 'rgba(0, 0, 0, 0.3)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: '8px',
                        padding: '10px 14px',
                        color: 'var(--text-main)',
                        fontSize: '0.85rem',
                        outline: 'none',
                      }}
                    />
                    <button
                      onClick={() => handleAskCopilot(copilotQuery)}
                      style={{
                        background: 'linear-gradient(135deg, #6366f1 0%, #3b82f6 100%)',
                        border: 'none',
                        borderRadius: '8px',
                        color: '#ffffff',
                        padding: '0 16px',
                        fontWeight: 600,
                        fontSize: '0.85rem',
                        cursor: 'pointer',
                      }}
                    >
                      Ask
                    </button>
                  </div>

                  {copilotAnswer && (
                    <div style={{ padding: '16px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--border-subtle)', borderRadius: '10px' }}>
                      <span style={{ fontSize: '0.75rem', color: '#818cf8', fontWeight: 700, textTransform: 'uppercase', display: 'block', marginBottom: '6px' }}>
                        Copilot Response:
                      </span>
                      <p style={{ fontSize: '0.9rem', color: 'var(--text-main)', lineHeight: 1.6, margin: 0 }}>
                        {copilotAnswer}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Modal Footer */}
        <div
          style={{
            padding: '16px 24px',
            borderTop: '1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'rgba(0, 0, 0, 0.2)',
          }}
        >
          <span style={{ fontSize: '0.75rem', color: 'var(--text-faint)' }}>
            Encrypted Biometrics • Strict Privacy Protocol • Aegis AI 2.0
          </span>
          <button
            onClick={onClose}
            style={{
              background: 'rgba(255, 255, 255, 0.06)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-main)',
              padding: '8px 18px',
              borderRadius: '8px',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
