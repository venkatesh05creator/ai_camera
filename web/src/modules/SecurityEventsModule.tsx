import React, { useState } from 'react';
import { 
  ShieldAlert, 
  CheckCircle2, 
  AlertCircle, 
  Search, 
  Filter, 
  Camera, 
  Eye, 
  Clock 
} from 'lucide-react';
import { Alert, DetectionEvent } from '../types';

interface SecurityEventsModuleProps {
  alerts?: Alert[];
  onReviewEvent?: (id: string, status: 'confirmed' | 'false_positive') => Promise<void>;
  onAcknowledgeAlert?: (id: string) => Promise<void>;
  onBackToCommandCenter?: () => void;
}

export const SecurityEventsModule: React.FC<SecurityEventsModuleProps> = ({
  alerts = [],
  onReviewEvent = async () => {},
  onAcknowledgeAlert = async () => {},
  onBackToCommandCenter,
}) => {
  const [filterSeverity, setFilterSeverity] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const filteredAlerts = alerts.filter((a) => {
    const matchesSev = filterSeverity === 'all' || a.severity === filterSeverity;
    const matchesQ = !searchQuery || a.title.toLowerCase().includes(searchQuery.toLowerCase()) || a.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSev && matchesQ;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 160px)', background: '#070f26', borderRadius: 14, border: '1px solid rgba(0, 210, 255, 0.25)', overflow: 'hidden' }}>
      {/* Top Header */}
      <div style={{ padding: '12px 18px', background: 'rgba(10, 20, 50, 0.95)', borderBottom: '1px solid rgba(0, 210, 255, 0.2)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 34, height: 34, borderRadius: 8, background: 'linear-gradient(135deg, #ef4444 0%, #b91c1c 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <ShieldAlert size={18} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: '0.96rem', fontWeight: 700, color: '#ffffff' }}>Security Events & Investigation Center</span>
              <span style={{ fontSize: '0.66rem', padding: '2px 6px', borderRadius: 4, background: 'rgba(239, 68, 68, 0.2)', color: '#f87171', fontWeight: 600 }}>
                {alerts.length} Incidents Logged
              </span>
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
              Perimeter security • Potential safety incidents • Human verification workflow • Zero automated criminality declarations
            </div>
          </div>
        </div>

        {/* Severity Filter Pills */}
        <div style={{ display: 'flex', background: 'rgba(7, 14, 35, 0.8)', padding: 3, borderRadius: 6, border: '1px solid rgba(0, 210, 255, 0.2)', gap: 4 }}>
          {['all', 'critical', 'high', 'medium', 'low'].map((sev) => (
            <button
              key={sev}
              onClick={() => setFilterSeverity(sev)}
              style={{
                padding: '4px 10px',
                borderRadius: 4,
                fontSize: '0.7rem',
                textTransform: 'uppercase',
                fontWeight: filterSeverity === sev ? 700 : 500,
                background: filterSeverity === sev ? 'rgba(0, 210, 255, 0.25)' : 'transparent',
                border: 'none',
                color: filterSeverity === sev ? '#00d2ff' : '#94a3b8',
                cursor: 'pointer'
              }}
            >
              {sev}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Search */}
        <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(11, 22, 53, 0.8)', border: '1px solid rgba(0, 210, 255, 0.25)', borderRadius: 8, padding: '6px 12px', gap: 8 }}>
          <Search size={14} color="#00d2ff" />
          <input
            type="text"
            placeholder="Search incident titles or descriptions (e.g. perimeter, movement, unexpected visitor)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ flex: 1, background: 'transparent', border: 'none', color: '#fff', fontSize: '0.78rem', outline: 'none' }}
          />
        </div>

        {/* Events Table */}
        <div style={{ background: 'rgba(11, 22, 53, 0.75)', border: '1px solid rgba(0, 210, 255, 0.25)', borderRadius: 12, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.76rem' }}>
            <thead>
              <tr style={{ background: 'rgba(255, 255, 255, 0.02)', color: '#94a3b8', borderBottom: '1px solid rgba(0, 210, 255, 0.1)' }}>
                <th style={{ padding: '10px 14px' }}>Incident Description</th>
                <th style={{ padding: '10px 14px' }}>Severity</th>
                <th style={{ padding: '10px 14px' }}>Recorded Time</th>
                <th style={{ padding: '10px 14px' }}>Status</th>
                <th style={{ padding: '10px 14px', textAlign: 'right' }}>Human Review Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredAlerts.map((alert) => {
                const isCrit = alert.severity === 'critical';
                const isHigh = alert.severity === 'high';
                return (
                  <tr key={alert.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)', color: '#fff' }}>
                    <td style={{ padding: '10px 14px' }}>
                      <div style={{ fontWeight: 700, color: isCrit ? '#f87171' : isHigh ? '#f59e0b' : '#38bdf8', marginBottom: 2 }}>
                        {alert.title}
                      </div>
                      <div style={{ color: '#94a3b8', fontSize: '0.7rem' }}>
                        {alert.description || 'Automated sensor event requiring operator verification'}
                      </div>
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <span style={{
                        padding: '2px 8px',
                        borderRadius: 4,
                        fontSize: '0.66rem',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        background: isCrit ? 'rgba(239, 68, 68, 0.2)' : isHigh ? 'rgba(245, 158, 11, 0.2)' : 'rgba(0, 210, 255, 0.2)',
                        color: isCrit ? '#f87171' : isHigh ? '#fcd34d' : '#38bdf8'
                      }}>
                        {alert.severity}
                      </span>
                    </td>
                    <td style={{ padding: '10px 14px', color: '#cbd5e1' }}>
                      {new Date(alert.created_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <span style={{ fontSize: '0.68rem', color: alert.status === 'active' ? '#f59e0b' : '#34d399', fontWeight: 600 }}>
                        {alert.status.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 6 }}>
                        <button
                          onClick={() => onAcknowledgeAlert(alert.id)}
                          style={{ padding: '4px 10px', borderRadius: 4, background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.3)', color: '#34d399', fontSize: '0.68rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}
                        >
                          <CheckCircle2 size={11} /> Confirm
                        </button>
                        <button
                          onClick={() => onReviewEvent(alert.event_id, 'false_positive')}
                          style={{ padding: '4px 10px', borderRadius: 4, background: 'rgba(255, 255, 255, 0.06)', border: '1px solid rgba(255, 255, 255, 0.15)', color: '#94a3b8', fontSize: '0.68rem', cursor: 'pointer' }}
                        >
                          False Positive
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
  );
};
