import React, { useEffect, useState } from 'react';
import { User } from '../types';
import { api } from '../services/api';
import { X, Shield, Key, Lock, CheckCircle2, RefreshCw, LogOut, User as UserIcon, Clock, HardDrive, Laptop } from 'lucide-react';

interface UserDetailsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const UserDetailsModal: React.FC<UserDetailsModalProps> = ({ isOpen, onClose }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshSuccess, setRefreshSuccess] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      api.getMe()
        .then((u) => {
          setUser(u);
          setLoading(false);
        })
        .catch(() => {
          setUser(null);
          setLoading(false);
        });
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleRefreshSession = async () => {
    setLoading(true);
    try {
      const refreshed = await api.getMe();
      setUser(refreshed);
      setRefreshSuccess(true);
      setTimeout(() => setRefreshSuccess(false), 3000);
    } catch (err: any) {
      alert(`Session refresh error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    api.logout();
    onClose();
  };

  const permissions = [
    { name: 'Live Camera Streams & Remote PTZ', granted: true },
    { name: 'Camera Inventory Registration & Secret Management', granted: true },
    { name: 'People Directory & Biometric Enrollment', granted: true },
    { name: 'Consent Management & Biometric Revocation', granted: true },
    { name: 'Cryptographic Storage & AES-256-GCM Vault Access', granted: true },
    { name: 'Immutable Security Audit Logs Explorer', granted: true },
    { name: 'Data Retention Policies & Purge Scheduling', granted: true },
  ];

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(5, 7, 10, 0.75)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
      }}
      onClick={onClose}
    >
      <div
        className="glass-card"
        style={{
          width: '100%',
          maxWidth: '560px',
          background: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)',
          borderRadius: '16px',
          overflow: 'hidden',
          boxShadow: '0 24px 60px rgba(0,0,0,0.8)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header Banner */}
        <div
          style={{
            background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.25) 0%, rgba(16, 185, 129, 0.15) 100%)',
            borderBottom: '1px solid var(--border-subtle)',
            padding: '24px',
            position: 'relative',
          }}
        >
          <button
            onClick={onClose}
            style={{
              position: 'absolute',
              top: '16px',
              right: '16px',
              background: 'rgba(255, 255, 255, 0.08)',
              border: 'none',
              borderRadius: '8px',
              width: '32px',
              height: '32px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-muted)',
              cursor: 'pointer',
            }}
          >
            <X size={18} />
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div
              style={{
                width: '64px',
                height: '64px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 8px 24px rgba(99, 102, 241, 0.4)',
                border: '2px solid rgba(255, 255, 255, 0.2)',
              }}
            >
              <UserIcon size={32} color="#ffffff" />
            </div>

            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>
                  {user?.display_name || 'Security Director'}
                </h3>
                <span
                  style={{
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    padding: '2px 8px',
                    borderRadius: '12px',
                    background: 'rgba(16, 185, 129, 0.2)',
                    color: '#34d399',
                    border: '1px solid rgba(16, 185, 129, 0.3)',
                  }}
                >
                  Active Session
                </span>
              </div>
              <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: 'var(--text-muted)' }} className="mono">
                {user?.email || 'admin@surveillance.local'}
              </p>
            </div>
          </div>
        </div>

        {/* Modal Content */}
        <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px', maxHeight: '68vh', overflowY: 'auto' }}>
          {/* Status & Security Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div style={{ padding: '12px 14px', borderRadius: '10px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#818cf8', fontSize: '0.78rem', fontWeight: 600 }}>
                <Shield size={14} />
                <span>USER ROLE</span>
              </div>
              <p style={{ margin: '6px 0 0', fontSize: '0.92rem', fontWeight: 700, color: '#f8fafc', textTransform: 'capitalize' }}>
                {user?.role || 'owner'} (Superadmin)
              </p>
            </div>

            <div style={{ padding: '12px 14px', borderRadius: '10px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#34d399', fontSize: '0.78rem', fontWeight: 600 }}>
                <Lock size={14} />
                <span>AUTH STANDARD</span>
              </div>
              <p style={{ margin: '6px 0 0', fontSize: '0.92rem', fontWeight: 700, color: '#f8fafc' }}>
                Argon2id + JWT
              </p>
            </div>
          </div>

          {/* Role Permissions Section */}
          <div>
            <h4 style={{ fontSize: '0.85rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', margin: '0 0 10px', letterSpacing: '0.04em' }}>
              Effective Permissions (Full Operator Authority)
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {permissions.map((p, idx) => (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    background: 'rgba(255,255,255,0.015)',
                    border: '1px solid rgba(255,255,255,0.04)',
                    fontSize: '0.8rem',
                    color: 'var(--text-main)',
                  }}
                >
                  <CheckCircle2 size={15} color="#10b981" />
                  <span>{p.name}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Session Details */}
          <div style={{ padding: '14px', borderRadius: '10px', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.78rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)' }}>
              <span>User ID</span>
              <span className="mono" style={{ color: 'var(--text-main)' }}>{user?.id || 'usr-master'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)' }}>
              <span>Workstation Scope</span>
              <span style={{ color: '#34d399' }}>Local Trusted Network (127.0.0.1)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)' }}>
              <span>Biometric Vault Key</span>
              <span className="mono" style={{ color: '#818cf8' }}>AES-256-GCM (Hardware Bound)</span>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div
          style={{
            padding: '16px 24px',
            borderTop: '1px solid var(--border-subtle)',
            background: 'rgba(0, 0, 0, 0.2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={handleRefreshSession}
              disabled={loading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 14px',
                borderRadius: '8px',
                background: 'rgba(99, 102, 241, 0.15)',
                color: '#818cf8',
                border: '1px solid rgba(99, 102, 241, 0.3)',
                cursor: 'pointer',
                fontSize: '0.82rem',
                fontWeight: 600,
              }}
            >
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
              <span>{refreshSuccess ? 'Session Refreshed!' : 'Refresh Session'}</span>
            </button>

            <button
              onClick={handleLogout}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 14px',
                borderRadius: '8px',
                background: 'rgba(239, 68, 68, 0.15)',
                color: '#f87171',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                cursor: 'pointer',
                fontSize: '0.82rem',
                fontWeight: 600,
              }}
            >
              <LogOut size={14} />
              <span>Sign Out</span>
            </button>
          </div>

          <button
            onClick={onClose}
            style={{
              padding: '8px 18px',
              borderRadius: '8px',
              background: 'rgba(255, 255, 255, 0.08)',
              color: 'var(--text-main)',
              border: '1px solid var(--border-subtle)',
              cursor: 'pointer',
              fontSize: '0.82rem',
              fontWeight: 600,
            }}
          >
            Close Details
          </button>
        </div>
      </div>
    </div>
  );
};
