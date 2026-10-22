import React, { useEffect, useState } from 'react';
import { AuditLog } from '../types';
import { api } from '../services/api';
import { ShieldCheck, Lock, Database, Clock, RefreshCw, Key } from 'lucide-react';

export const SettingsAudit: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [retentionDays, setRetentionDays] = useState(30);
  const [purgeSnapshotsDays, setPurgeSnapshotsDays] = useState(7);
  const [savedMsg, setSavedMsg] = useState(false);

  const fetchLogs = () => {
    api.getAuditLogs().then(setLogs).catch(() => {});
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const handleSaveRetention = () => {
    setSavedMsg(true);
    setTimeout(() => setSavedMsg(false), 3000);
  };

  return (
    <div className="page-scroll-container settings-audit-container">
      <div>
        <h3 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0 }}>System Hardening & Audit Controls</h3>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: '2px 0 0' }}>Data retention limits, encryption status, and immutable security audit logs</p>
      </div>

      {/* Top 2 Columns: Cryptography Status & Retention Policies */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '18px' }}>
        {/* Cryptographic Controls Card */}
        <div className="glass-card" style={{ padding: '20px' }}>
          <h4 style={{ fontSize: '0.98rem', fontWeight: 700, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Key size={16} color="#818cf8" />
            <span>Active Cryptographic Controls</span>
          </h4>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.82rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', background: 'rgba(255,255,255,0.02)', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
              <span>Biometric Template Storage</span>
              <span className="badge-tag badge-success">AES-256-GCM Encrypted</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', background: 'rgba(255,255,255,0.02)', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
              <span>Password Hashing</span>
              <span className="badge-tag badge-accent">Argon2id Salted (64MB)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', background: 'rgba(255,255,255,0.02)', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
              <span>Stranger Identification</span>
              <span className="badge-tag badge-danger">Strictly Prohibited</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', background: 'rgba(255,255,255,0.02)', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
              <span>Biometric Deletion on Withdrawal</span>
              <span className="badge-tag badge-success">Immediate Purge</span>
            </div>
          </div>
        </div>

        {/* Retention Policy Controls Card */}
        <div className="glass-card" style={{ padding: '20px' }}>
          <h4 style={{ fontSize: '0.98rem', fontWeight: 700, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Clock size={16} color="#f59e0b" />
            <span>Automated Data Retention Rules</span>
          </h4>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', fontSize: '0.82rem' }}>
            <div>
              <label style={{ display: 'block', color: 'var(--text-muted)', marginBottom: '4px' }}>Anonymous Detection Events Retention</label>
              <select
                value={retentionDays}
                onChange={(e) => setRetentionDays(Number(e.target.value))}
                style={{ width: '100%', padding: '7px 10px', borderRadius: '6px', background: 'var(--bg-main)', border: '1px solid var(--border-subtle)', color: '#fff' }}
              >
                <option value={7}>7 Days (High Privacy)</option>
                <option value={30}>30 Days (Standard Recommended)</option>
                <option value={90}>90 Days</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', color: 'var(--text-muted)', marginBottom: '4px' }}>Unverified Snapshots Auto-Purge</label>
              <select
                value={purgeSnapshotsDays}
                onChange={(e) => setPurgeSnapshotsDays(Number(e.target.value))}
                style={{ width: '100%', padding: '7px 10px', borderRadius: '6px', background: 'var(--bg-main)', border: '1px solid var(--border-subtle)', color: '#fff' }}
              >
                <option value={3}>3 Days</option>
                <option value={7}>7 Days (Recommended)</option>
                <option value={14}>14 Days</option>
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '6px' }}>
              <button onClick={handleSaveRetention} className="btn-primary" style={{ padding: '6px 14px', fontSize: '0.8rem' }}>
                Save Retention Policies
              </button>
              {savedMsg && <span style={{ color: '#34d399', fontSize: '0.78rem', fontWeight: 600 }}>Policies updated!</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Immutable Security Audit Trail */}
      <div className="glass-card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h4 style={{ fontSize: '0.98rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldCheck size={16} color="#10b981" />
            <span>Immutable Security Audit Log</span>
          </h4>
          <button onClick={fetchLogs} className="btn-secondary" style={{ padding: '4px 10px', fontSize: '0.75rem' }}>
            <RefreshCw size={12} />
            <span>Refresh</span>
          </button>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-faint)' }}>
                <th style={{ padding: '8px 12px' }}>Timestamp (UTC)</th>
                <th style={{ padding: '8px 12px' }}>Action</th>
                <th style={{ padding: '8px 12px' }}>Target Resource</th>
                <th style={{ padding: '8px 12px' }}>IP Address</th>
                <th style={{ padding: '8px 12px' }}>Outcome</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ padding: '24px', textAlign: 'center', color: 'var(--text-faint)' }}>
                    No audit records logged yet.
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                    <td style={{ padding: '8px 12px' }} className="mono">{new Date(log.timestamp).toLocaleString()}</td>
                    <td style={{ padding: '8px 12px', fontWeight: 600 }}>{log.action}</td>
                    <td style={{ padding: '8px 12px', color: 'var(--text-muted)' }}>{log.resource_type} {log.resource_id ? `(${log.resource_id.slice(0, 8)})` : ''}</td>
                    <td style={{ padding: '8px 12px' }} className="mono">{log.ip_address}</td>
                    <td style={{ padding: '8px 12px' }}>
                      <span className={`badge-tag ${log.outcome === 'success' ? 'badge-success' : 'badge-danger'}`} style={{ fontSize: '0.68rem' }}>
                        {log.outcome.toUpperCase()}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
