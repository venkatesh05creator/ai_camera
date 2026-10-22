import React from 'react';
import { Camera, Users, Clock, BarChart3, Settings, Video, ShieldCheck, AlertCircle, Sparkles } from 'lucide-react';

export type NavTab = 'live' | 'ai' | 'people' | 'events' | 'reports' | 'cameras' | 'settings';

interface SidebarProps {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  activeAlertsCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, onTabChange, activeAlertsCount }) => {
  const navItems = [
    { id: 'live' as NavTab, label: 'Live Monitoring', icon: Video, badge: 'LIVE' },
    { id: 'ai' as NavTab, label: 'AI Copilot & Intel', icon: Sparkles, badge: 'AI' },
    { id: 'people' as NavTab, label: 'People Directory', icon: Users },
    { id: 'events' as NavTab, label: 'Events & Alerts', icon: Clock, count: activeAlertsCount },
    { id: 'reports' as NavTab, label: 'Reports & Analytics', icon: BarChart3 },
    { id: 'cameras' as NavTab, label: 'Camera Devices', icon: Camera },
    { id: 'settings' as NavTab, label: 'Settings & Audit', icon: Settings },
  ];

  return (
    <aside className="app-sidebar">
      {/* Brand Header */}
      <div className="sidebar-header" style={{ padding: '24px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div style={{ width: '38px', height: '38px', borderRadius: '10px', background: 'linear-gradient(135deg, #6366f1 0%, #3b82f6 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 16px rgba(99, 102, 241, 0.4)' }}>
          <ShieldCheck size={22} color="#ffffff" />
        </div>
        <div>
          <h1 style={{ fontSize: '1.05rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-main)', lineHeight: 1.2 }}>
            Aegis AI
          </h1>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>
            Surveillance OS
          </span>
        </div>
      </div>

      {/* Nav List */}
      <nav style={{ padding: '16px 12px', display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          const Icon = item.icon;

          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '11px 14px',
                borderRadius: '10px',
                background: isActive ? 'linear-gradient(90deg, rgba(99, 102, 241, 0.18) 0%, rgba(99, 102, 241, 0.05) 100%)' : 'transparent',
                color: isActive ? '#818cf8' : 'var(--text-muted)',
                border: isActive ? '1px solid rgba(99, 102, 241, 0.3)' : '1px solid transparent',
                fontWeight: isActive ? 600 : 500,
                fontSize: '0.88rem',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.18s ease',
              }}
            >
              <Icon size={19} color={isActive ? '#818cf8' : 'var(--text-faint)'} />
              <span style={{ flex: 1 }}>{item.label}</span>

              {item.badge && (
                <span style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.4)', fontSize: '0.65rem', padding: '1px 6px', borderRadius: '4px', fontWeight: 700, letterSpacing: '0.05em' }}>
                  {item.badge}
                </span>
              )}

              {item.count !== undefined && item.count > 0 && (
                <span style={{ background: '#ef4444', color: '#ffffff', fontSize: '0.7rem', padding: '1px 7px', borderRadius: '10px', fontWeight: 700 }}>
                  {item.count}
                </span>
              )}
            </button>
          );
        })}

        {/* 3D Holographic Iron Man HUD Link */}
        <a
          href="/hud"
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '11px 14px',
            borderRadius: '10px',
            background: 'linear-gradient(90deg, rgba(6, 182, 212, 0.15) 0%, rgba(59, 130, 246, 0.1) 100%)',
            color: '#38bdf8',
            border: '1px solid rgba(56, 189, 248, 0.35)',
            fontWeight: 600,
            fontSize: '0.88rem',
            textDecoration: 'none',
            boxShadow: '0 0 12px rgba(56, 189, 248, 0.15)',
            marginTop: '8px',
          }}
        >
          <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: '#38bdf8', boxShadow: '0 0 8px #38bdf8' }} />
          <span style={{ flex: 1 }}>Holographic HUD</span>
          <span style={{ background: 'rgba(56, 189, 248, 0.25)', color: '#38bdf8', fontSize: '0.65rem', padding: '1px 6px', borderRadius: '4px', fontWeight: 700 }}>3D HUD</span>
        </a>
      </nav>

      {/* Privacy Guarantee Footer */}
      <div className="sidebar-footer" style={{ margin: '14px', padding: '14px', borderRadius: '10px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981' }} className="pulse-online" />
          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#34d399' }}>Privacy Protocol Active</span>
        </div>
        <p style={{ fontSize: '0.72rem', color: 'var(--text-faint)', lineHeight: 1.4 }}>
          Strangers stay anonymous. Only consenting enrolled profiles are verified.
        </p>
      </div>
    </aside>
  );
};
