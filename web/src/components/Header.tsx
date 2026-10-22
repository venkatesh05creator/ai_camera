import React, { useEffect, useState } from 'react';
import { Bell, Shield, User as UserIcon } from 'lucide-react';
import { NavTab } from './Sidebar';

import { UserDetailsModal } from './UserDetailsModal';

interface HeaderProps {
  activeTab: NavTab;
  camerasCount: number;
  activeAlertsCount: number;
}

export const Header: React.FC<HeaderProps> = ({ activeTab, camerasCount, activeAlertsCount }) => {
  const [timeStr, setTimeStr] = useState('');
  const [showUserDetails, setShowUserDetails] = useState(false);

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTimeStr(now.toUTCString().replace('GMT', 'UTC'));
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, []);

  const titles: Record<NavTab, { title: string; subtitle: string }> = {
    live: { title: 'Live Camera Operations', subtitle: 'Real-time multi-camera monitoring, motion and detection overlays' },
    ai: { title: 'AI Intelligence Copilot & OSINT', subtitle: 'Natural language surveillance analysis, online profile lookup, and situational intelligence' },
    people: { title: 'People & Consent Directory', subtitle: 'Authorized enrollment registry and voluntary profile verification' },
    events: { title: 'Detection Events & Alerts', subtitle: 'Chronological activity stream and review queue' },
    reports: { title: 'Surveillance Analytics & Reports', subtitle: 'Detection KPIs, camera uptime, and verifiable audit records' },
    cameras: { title: 'Camera Device Inventory', subtitle: 'Registered webcams, RTSP streams, and mobile camera nodes' },
    hud: { title: 'J.A.R.V.I.S. Holographic 3D HUD', subtitle: 'Real-time quantum reactor core, two-way neural voice copilot, live market intelligence & executive automation' },
    settings: { title: 'System Hardening & Audit Logs', subtitle: 'Data retention policies and cryptographic key status' },
  };

  const current = titles[activeTab];

  return (
    <>
      <header className="app-header">
        <div className="header-left">
          <h2 className="header-title">
            {current.title}
          </h2>
          <p className="header-subtitle" style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: 0 }}>
            {current.subtitle}
          </p>
        </div>

        <div className="header-right-actions">
          {/* UTC Clock */}
          <div style={{ fontSize: '0.78rem', color: 'var(--text-faint)', padding: '6px 12px', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '8px', border: '1px solid var(--border-subtle)' }} className="mono header-utc-clock">
            {timeStr}
          </div>

          {/* Live Cameras Count Badge */}
          <div className="header-camera-badge">
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981' }} className="pulse-online" />
            <span className="header-camera-badge-text">{camerasCount} {camerasCount === 1 ? 'Camera' : 'Cameras'} Online</span>
          </div>

          {/* Alerts Bell */}
          <div style={{ position: 'relative', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
            <Bell size={18} color="var(--text-muted)" />
            {activeAlertsCount > 0 && (
              <span style={{ position: 'absolute', top: '-4px', right: '-4px', width: '8px', height: '8px', borderRadius: '50%', background: '#ef4444' }} className="pulse-alert" />
            )}
          </div>

          {/* User Avatar Badge - Clickable to open User Details Modal */}
          <button
            onClick={() => setShowUserDetails(true)}
            title="Click to view User Profile & System Security Details"
            className="header-user-btn"
          >
            <div style={{ width: '26px', height: '26px', borderRadius: '50%', background: '#6366f1', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <UserIcon size={14} color="#ffffff" />
            </div>
            <span className="header-user-label">Owner / Admin</span>
          </button>
        </div>
      </header>

      {/* User Details Modal Dialog */}
      <UserDetailsModal isOpen={showUserDetails} onClose={() => setShowUserDetails(false)} />
    </>
  );
};
