import React, { useEffect, useState } from 'react';
import { Camera, Alert } from './types';
import { api, getAuthToken } from './services/api';
import { LoginModal } from './components/LoginModal';
import { UnifiedCommandCenter } from './pages/UnifiedCommandCenter';

export const App: React.FC = () => {
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
    <div style={{ width: '100vw', minHeight: '100vh', background: '#060b18', overflowX: 'hidden' }}>
      <UnifiedCommandCenter
        cameras={cameras}
        alerts={alerts}
        activeAlertsCount={activeAlertsCount}
        onRefreshCameras={fetchInitialData}
      />

      {/* Secure Authentication Modal */}
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
