import React, { useEffect, useState } from 'react';
import { Camera, Alert } from './types';
import { api, getAuthToken } from './services/api';
import { NavTab, Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { LoginModal } from './components/LoginModal';
import { LiveMonitoring } from './pages/LiveMonitoring';
import { AICopilotView } from './pages/AICopilotView';
import { PeopleDirectory } from './pages/PeopleDirectory';
import { EventsTimeline } from './pages/EventsTimeline';
import { ReportsAnalytics } from './pages/ReportsAnalytics';
import { CameraManagement } from './pages/CameraManagement';
import { SettingsAudit } from './pages/SettingsAudit';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<NavTab>('live');
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(!!getAuthToken());
  const [showLoginModal, setShowLoginModal] = useState<boolean>(!getAuthToken());

  const fetchInitialData = async () => {
    try {
      await api.ensureAuthenticated();
      setIsAuthenticated(true);
      setShowLoginModal(false);
      const [cams, alrts] = await Promise.all([
        api.getCameras().catch(() => []),
        api.getAlerts().catch(() => []),
      ]);
      setCameras(cams);
      setAlerts(alrts);
    } catch (err) {
      console.warn('Authentication or initial data fetch required:', err);
      setIsAuthenticated(false);
      setShowLoginModal(true);
    }
  };

  useEffect(() => {
    const handleAuthChange = () => {
      setIsAuthenticated(false);
      setShowLoginModal(true);
    };
    window.addEventListener('auth:unauthorized', handleAuthChange);
    window.addEventListener('auth:logout', handleAuthChange);
    return () => {
      window.removeEventListener('auth:unauthorized', handleAuthChange);
      window.removeEventListener('auth:logout', handleAuthChange);
    };
  }, []);

  useEffect(() => {
    fetchInitialData();
    const interval = setInterval(() => {
      if (getAuthToken()) {
        fetchInitialData();
      }
    }, 8000);
    return () => clearInterval(interval);
  }, []);

  // WebSocket for real-time notifications
  useEffect(() => {
    const token = getAuthToken();
    if (!token) return;

    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.host;
    const wsUrl = `${wsProto}//${wsHost}/api/v1/stream/ws?token=${encodeURIComponent(token)}`;

    let socket: WebSocket | null = null;
    try {
      socket = new WebSocket(wsUrl);
      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'alert') {
            api.getAlerts().then(setAlerts).catch(() => {});
          }
        } catch {
          // ignore parse errors
        }
      };
    } catch {
      // ws fallback
    }

    return () => {
      if (socket) socket.close();
    };
  }, [isAuthenticated]);

  const activeAlertsCount = alerts.filter((a) => a.status === 'active').length;

  return (
    <div className="app-container">
      {/* Persistent Navigation Sidebar */}
      <Sidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        activeAlertsCount={activeAlertsCount}
      />

      {/* Main Content Area */}
      <div className="main-content-col">
        <Header
          activeTab={activeTab}
          camerasCount={cameras.filter((c) => c.status === 'online').length}
          activeAlertsCount={activeAlertsCount}
        />

        <main className="app-main-viewport">
          {activeTab === 'live' && (
            <LiveMonitoring cameras={cameras} onOpenEvents={() => setActiveTab('events')} />
          )}
          {activeTab === 'ai' && <AICopilotView />}
          {activeTab === 'people' && <PeopleDirectory />}
          {activeTab === 'events' && <EventsTimeline />}
          {activeTab === 'reports' && <ReportsAnalytics />}
          {activeTab === 'cameras' && (
            <CameraManagement cameras={cameras} onRefresh={fetchInitialData} />
          )}
          {activeTab === 'settings' && <SettingsAudit />}
        </main>
      </div>

      {/* Secure Authentication & Initial Owner Setup Modal */}
      <LoginModal
        isOpen={showLoginModal}
        onSuccess={() => {
          setShowLoginModal(false);
          setIsAuthenticated(true);
          fetchInitialData();
        }}
      />
    </div>
  );
};

export default App;
