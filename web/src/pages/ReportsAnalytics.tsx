import React, { useEffect, useState } from 'react';
import { ReportSummary } from '../types';
import { api } from '../services/api';
import { BarChart3, Download, ShieldCheck, Eye, Activity, CheckCircle, Video, Clock, Sparkles, RefreshCw } from 'lucide-react';

export const ReportsAnalytics: React.FC = () => {
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [aiBriefing, setAiBriefing] = useState<string | null>(null);
  const [generatingBriefing, setGeneratingBriefing] = useState(false);

  useEffect(() => {
    api.getReportSummary().then(setSummary).catch(() => {});
  }, []);

  const handleDownloadCsv = () => {
    window.location.href = '/api/v1/reports/export';
  };

  const handleGenerateAiBriefing = async () => {
    setGeneratingBriefing(true);
    try {
      const res = await api.askCopilot('Generate a formal executive surveillance intelligence report for today.');
      setAiBriefing(res.answer);
    } catch (err: any) {
      setAiBriefing(`Failed to generate briefing: ${err.message}`);
    } finally {
      setGeneratingBriefing(false);
    }
  };

  if (!summary) {
    return <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading analytics summary...</div>;
  }

  const kpis = [
    { label: 'Total Events', value: summary.total_events, icon: Activity, color: '#6366f1' },
    { label: 'Verified Persons', value: summary.total_verified_matches, icon: ShieldCheck, color: '#10b981' },
    { label: 'Anonymous Tracks', value: summary.total_persons_detected - summary.total_verified_matches, icon: Eye, color: '#f59e0b' },
    { label: 'Active Cameras', value: summary.active_cameras_count, icon: Video, color: '#06b6d4' },
    { label: 'Enrolled Profiles', value: summary.total_enrolled_profiles, icon: CheckCircle, color: '#8b5cf6' },
    { label: 'Avg Alert Response', value: `${summary.avg_alert_response_seconds}s`, icon: Clock, color: '#ec4899' },
  ];

  return (
    <div className="page-scroll-container reports-analytics-container">
      {/* Top Bar with Export Action */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0 }}>System Metrics & Analytics</h3>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: '2px 0 0' }}>Aggregated telemetry for compliance and privacy verification</p>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={handleGenerateAiBriefing}
            disabled={generatingBriefing}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: 'linear-gradient(135deg, #6366f1 0%, #3b82f6 100%)',
              border: 'none',
              borderRadius: '8px',
              color: '#ffffff',
              padding: '8px 16px',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: '0 0 16px rgba(99, 102, 241, 0.3)',
            }}
          >
            <Sparkles size={16} className={generatingBriefing ? 'spin-icon' : ''} />
            <span>{generatingBriefing ? 'Synthesizing...' : 'Generate AI Briefing'}</span>
          </button>

          <button onClick={handleDownloadCsv} className="btn-primary">
            <Download size={16} />
            <span>Export Event Log (CSV)</span>
          </button>
        </div>
      </div>

      {/* AI Briefing Box if generated */}
      {aiBriefing && (
        <div
          style={{
            padding: '20px',
            background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(59, 130, 246, 0.05) 100%)',
            border: '1px solid rgba(99, 102, 241, 0.3)',
            borderRadius: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sparkles size={18} color="#818cf8" />
              <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#818cf8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Executive AI Intelligence Briefing
              </span>
            </div>
            <button
              onClick={() => setAiBriefing(null)}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.8rem' }}
            >
              ✕ Dismiss
            </button>
          </div>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-main)', lineHeight: 1.6, margin: 0 }}>
            {aiBriefing}
          </p>
        </div>
      )}

      {/* KPI Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '14px' }}>
        {kpis.map((kpi, idx) => {
          const Icon = kpi.icon;
          return (
            <div key={idx} className="glass-card" style={{ padding: '18px 16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>{kpi.label}</span>
                <Icon size={18} color={kpi.color} />
              </div>
              <p style={{ fontSize: '1.6rem', fontWeight: 700, margin: 0, color: 'var(--text-main)' }} className="mono">
                {kpi.value}
              </p>
            </div>
          );
        })}
      </div>

      {/* Breakdown Grids */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '18px' }}>
        {/* Events by Camera */}
        <div className="glass-card" style={{ padding: '20px' }}>
          <h4 style={{ fontSize: '0.98rem', fontWeight: 700, marginBottom: '16px' }}>Activity by Camera Device</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {Object.keys(summary.events_by_camera).length === 0 ? (
              <span style={{ fontSize: '0.82rem', color: 'var(--text-faint)' }}>No camera activity recorded yet.</span>
            ) : (
              Object.entries(summary.events_by_camera).map(([cam, cnt]) => {
                const pct = summary.total_events > 0 ? (cnt / summary.total_events) * 100 : 0;
                return (
                  <div key={cam}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '4px' }}>
                      <span style={{ fontWeight: 600 }}>{cam}</span>
                      <span className="mono" style={{ color: 'var(--text-muted)' }}>{cnt} ({pct.toFixed(0)}%)</span>
                    </div>
                    <div style={{ width: '100%', height: '6px', background: 'rgba(255,255,255,0.06)', borderRadius: '9999px', overflow: 'hidden' }}>
                      <div style={{ width: `${pct}%`, height: '100%', background: 'linear-gradient(90deg, #6366f1, #06b6d4)', borderRadius: '9999px' }} />
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Events by Event Type */}
        <div className="glass-card" style={{ padding: '20px' }}>
          <h4 style={{ fontSize: '0.98rem', fontWeight: 700, marginBottom: '16px' }}>Detection Event Breakdown</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {Object.entries(summary.events_by_type).map(([etype, cnt]) => {
              const pct = summary.total_events > 0 ? (cnt / summary.total_events) * 100 : 0;
              return (
                <div key={etype}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '4px' }}>
                    <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>{etype}</span>
                    <span className="mono" style={{ color: 'var(--text-muted)' }}>{cnt} ({pct.toFixed(0)}%)</span>
                  </div>
                  <div style={{ width: '100%', height: '6px', background: 'rgba(255,255,255,0.06)', borderRadius: '9999px', overflow: 'hidden' }}>
                    <div style={{ width: `${pct}%`, height: '100%', background: etype === 'person' ? '#f59e0b' : etype === 'motion' ? '#6366f1' : '#10b981', borderRadius: '9999px' }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
