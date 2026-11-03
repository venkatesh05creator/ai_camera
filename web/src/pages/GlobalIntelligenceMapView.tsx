import React, { useEffect, useState } from 'react';
import { 
  Globe, 
  Flame, 
  Activity, 
  Video, 
  CloudSun, 
  Coins, 
  Rocket, 
  RefreshCw, 
  MapPin, 
  ExternalLink,
  Layers,
  Search,
  Filter,
  AlertTriangle
} from 'lucide-react';
import { getAuthToken } from '../services/api';

interface MapMarker {
  id: string;
  layer: 'disaster' | 'camera' | 'traffic' | 'weather';
  title: string;
  subtitle: string;
  latitude: number;
  longitude: number;
  severity: string;
  badge: string;
  source: string;
  url?: string;
  occurred_at: string;
}

interface EconomicData {
  forex_usd_base: Record<string, number>;
  forex_date: string;
  market_briefing: string;
}

interface AsteroidItem {
  id: string;
  name: string;
  estimated_diameter_m: string;
  is_hazardous: boolean;
  miss_distance_km: number;
  relative_speed_kmh: number;
  close_approach_date: string;
  source_name: string;
  source_url: string;
}

export const GlobalIntelligenceMapView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'map' | 'disasters' | 'traffic' | 'space' | 'economics'>('map');
  const [markers, setMarkers] = useState<MapMarker[]>([]);
  const [filteredMarkers, setFilteredMarkers] = useState<MapMarker[]>([]);
  const [selectedMarker, setSelectedMarker] = useState<MapMarker | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Layer filters
  const [layerFilters, setLayerFilters] = useState({
    disaster: true,
    transport: true,
    camera: true,
    weather: true,
  });

  const [loading, setLoading] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<string>('');
  const [economics, setEconomics] = useState<EconomicData | null>(null);
  const [asteroids, setAsteroids] = useState<AsteroidItem[]>([]);

  const fetchGlobalData = async () => {
    setLoading(true);
    const token = getAuthToken();
    const headers = {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/json',
    };

    try {
      // 1. Unified Markers
      const res = await fetch(
        `/api/v1/global/map-markers?include_disasters=${layerFilters.disaster}&include_traffic=${layerFilters.transport}&include_cameras=${layerFilters.camera}&include_weather=${layerFilters.weather}`,
        { headers }
      );
      if (res.ok) {
        const json = await res.json();
        setMarkers(json.markers || []);
      }

      // 2. Economics
      const econRes = await fetch('/api/v1/global/economics', { headers });
      if (econRes.ok) {
        const econJson = await econRes.json();
        setEconomics(econJson);
      }

      // 3. Space / Asteroids
      const spaceRes = await fetch('/api/v1/global/space/asteroids', { headers });
      if (spaceRes.ok) {
        const spaceJson = await spaceRes.json();
        setAsteroids(spaceJson.asteroids || []);
      }

      setLastRefreshed(new Date().toLocaleTimeString());
    } catch (err) {
      console.error('Failed to fetch global intelligence feeds:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGlobalData();
    const interval = setInterval(fetchGlobalData, 30000); // Poll every 30s
    return () => clearInterval(interval);
  }, [layerFilters]);

  // Filter markers by search
  useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredMarkers(markers);
    } else {
      const q = searchQuery.toLowerCase();
      setFilteredMarkers(
        markers.filter(
          (m) =>
            m.title.toLowerCase().includes(q) ||
            m.subtitle.toLowerCase().includes(q) ||
            m.layer.toLowerCase().includes(q)
        )
      );
    }
  }, [searchQuery, markers]);

  // Helper to convert Lat/Lon to approximate percentage on equirectangular map projection
  const getCoordinatesPercent = (lat: number, lon: number) => {
    const x = ((lon + 180) / 360) * 100;
    const y = ((90 - lat) / 180) * 100;
    return {
      left: `${Math.max(2, Math.min(98, x))}%`,
      top: `${Math.max(4, Math.min(96, y))}%`,
    };
  };

  const getMarkerColor = (layer: string, severity: string) => {
    if (layer === 'disaster') {
      return severity === 'critical' ? '#ef4444' : severity === 'high' ? '#f97316' : '#eab308';
    }
    if (layer === 'transport') return '#38bdf8';
    if (layer === 'camera') return '#10b981';
    if (layer === 'weather') return '#a855f7';
    return '#6366f1';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '16px', padding: '20px' }}>
      {/* Top Header Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Globe size={24} color="#6366f1" />
            <h2 style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
              Global Intelligence & Worldwide Tracking
            </h2>
          </div>
          <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Real-time public hazard feeds, aviation transponders, open observatories & macroeconomic indicators.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {lastRefreshed && (
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              Updated: {lastRefreshed}
            </span>
          )}
          <button
            onClick={fetchGlobalData}
            disabled={loading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              borderRadius: '8px',
              background: 'rgba(99, 102, 241, 0.15)',
              border: '1px solid rgba(99, 102, 241, 0.3)',
              color: '#818cf8',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontWeight: 600,
              fontSize: '0.82rem',
            }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            {loading ? 'Refreshing...' : 'Live Sync'}
          </button>
        </div>
      </div>

      {/* Domain Navigation Tabs */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '10px' }}>
        {[
          { id: 'map', label: 'Interactive World Radar', icon: Globe },
          { id: 'disasters', label: 'USGS Hazards & Quakes', icon: Flame },
          { id: 'traffic', label: 'Municipal Traffic Feeds', icon: Activity },
          { id: 'space', label: 'Space Asteroids & NEOs', icon: Rocket },
          { id: 'economics', label: 'Forex & Markets', icon: Coins },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px',
                borderRadius: '8px',
                background: isActive ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                color: isActive ? '#818cf8' : 'var(--text-muted)',
                border: isActive ? '1px solid rgba(99, 102, 241, 0.3)' : '1px solid transparent',
                fontWeight: isActive ? 600 : 500,
                fontSize: '0.85rem',
                cursor: 'pointer',
              }}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* VIEW 1: INTERACTIVE MAP RADAR */}
      {activeTab === 'map' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '16px', flex: 1, minHeight: '520px' }}>
          {/* Main Map Projection Canvas */}
          <div
            style={{
              position: 'relative',
              borderRadius: '14px',
              border: '1px solid var(--border-subtle)',
              background: '#0a0d18 radial-gradient(circle at center, #111827 0%, #07090e 100%)',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {/* Map Controls Overlay */}
            <div
              style={{
                position: 'absolute',
                top: 14,
                left: 14,
                right: 14,
                zIndex: 20,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                pointerEvents: 'none',
              }}
            >
              {/* Search Box */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  background: 'rgba(15, 23, 42, 0.85)',
                  backdropFilter: 'blur(10px)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '8px',
                  padding: '6px 12px',
                  pointerEvents: 'auto',
                  width: '260px',
                }}
              >
                <Search size={14} color="#94a3b8" />
                <input
                  type="text"
                  placeholder="Filter locations, traffic, quakes..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#fff',
                    fontSize: '0.82rem',
                    outline: 'none',
                    width: '100%',
                  }}
                />
              </div>

              {/* Layer Toggles */}
              <div
                style={{
                  display: 'flex',
                  gap: '6px',
                  background: 'rgba(15, 23, 42, 0.85)',
                  backdropFilter: 'blur(10px)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '8px',
                  padding: '4px 8px',
                  pointerEvents: 'auto',
                }}
              >
                {[
                  { key: 'disaster', label: 'Hazards', color: '#ef4444' },
                  { key: 'transport', label: 'Aviation', color: '#38bdf8' },
                  { key: 'camera', label: 'Webcams', color: '#10b981' },
                  { key: 'weather', label: 'Weather', color: '#a855f7' },
                ].map((item) => (
                  <button
                    key={item.key}
                    onClick={() =>
                      setLayerFilters((prev: any) => ({ ...prev, [item.key]: !prev[item.key] }))
                    }
                    style={{
                      background: (layerFilters as any)[item.key]
                        ? `${item.color}22`
                        : 'transparent',
                      border: `1px solid ${(layerFilters as any)[item.key] ? item.color : 'transparent'}`,
                      color: (layerFilters as any)[item.key] ? item.color : '#64748b',
                      borderRadius: '6px',
                      padding: '4px 8px',
                      fontSize: '0.74rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Simulated Geospatial Grid Background */}
            <div
              style={{
                flex: 1,
                position: 'relative',
                backgroundImage: `
                  linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
                  linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px)
                `,
                backgroundSize: '40px 40px',
              }}
            >
              {/* World Map SVG Overlay */}
              <svg
                viewBox="0 0 1000 500"
                style={{
                  position: 'absolute',
                  width: '100%',
                  height: '100%',
                  opacity: 0.18,
                  pointerEvents: 'none',
                }}
              >
                {/* Simplified Continents Contours */}
                <path
                  d="M150,120 Q180,80 240,110 T300,160 L280,240 Q240,290 200,260 T140,200 Z"
                  fill="#6366f1"
                />
                <path
                  d="M480,100 Q540,80 600,120 T620,200 L560,260 Q500,280 470,220 Z"
                  fill="#6366f1"
                />
                <path
                  d="M620,110 Q720,90 820,130 T880,240 L800,320 Q700,310 650,220 Z"
                  fill="#6366f1"
                />
                <path
                  d="M260,300 Q310,320 320,400 T270,470 L230,420 Q220,340 260,300 Z"
                  fill="#6366f1"
                />
                <path
                  d="M750,340 Q840,330 870,400 T800,460 L730,420 Z"
                  fill="#6366f1"
                />
              </svg>

              {/* Real-Time Markers Plotting */}
              {filteredMarkers.map((m) => {
                const pos = getCoordinatesPercent(m.latitude, m.longitude);
                const color = getMarkerColor(m.layer, m.severity);
                const isSelected = selectedMarker?.id === m.id;

                return (
                  <div
                    key={m.id}
                    onClick={() => setSelectedMarker(m)}
                    style={{
                      position: 'absolute',
                      left: pos.left,
                      top: pos.top,
                      transform: 'translate(-50%, -50%)',
                      cursor: 'pointer',
                      zIndex: isSelected ? 30 : 10,
                      transition: 'transform 0.2s',
                    }}
                    title={`${m.title} (${m.source})`}
                  >
                    <div
                      style={{
                        width: isSelected ? '18px' : '12px',
                        height: isSelected ? '18px' : '12px',
                        borderRadius: '50%',
                        backgroundColor: color,
                        border: '2px solid #ffffff',
                        boxShadow: `0 0 ${isSelected ? '14px' : '6px'} ${color}`,
                      }}
                    />
                  </div>
                );
              })}
            </div>

            {/* Bottom Status Ticker */}
            <div
              style={{
                padding: '8px 16px',
                background: 'rgba(15, 23, 42, 0.95)',
                borderTop: '1px solid var(--border-subtle)',
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: '0.78rem',
                color: 'var(--text-muted)',
              }}
            >
              <span>Active Telemetry Points: <strong>{markers.length}</strong></span>
              <span>Sources: USGS Hazards • Municipal Traffic • Open-Meteo • NASA NeoWs</span>
            </div>
          </div>

          {/* Right Inspection & Telemetry Details Sidebar */}
          <div
            style={{
              borderRadius: '14px',
              border: '1px solid var(--border-subtle)',
              background: 'var(--bg-card)',
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              gap: '14px',
              overflowY: 'auto',
            }}
          >
            {selectedMarker ? (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <span
                    style={{
                      padding: '3px 8px',
                      borderRadius: '4px',
                      fontSize: '0.7rem',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      background: `${getMarkerColor(selectedMarker.layer, selectedMarker.severity)}22`,
                      color: getMarkerColor(selectedMarker.layer, selectedMarker.severity),
                    }}
                  >
                    {selectedMarker.layer} • {selectedMarker.badge}
                  </span>
                  <button
                    onClick={() => setSelectedMarker(null)}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: 'var(--text-muted)',
                      cursor: 'pointer',
                      fontSize: '0.9rem',
                    }}
                  >
                    ✕
                  </button>
                </div>

                <div>
                  <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-main)', margin: '0 0 6px' }}>
                    {selectedMarker.title}
                  </h3>
                  <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: 0 }}>
                    {selectedMarker.subtitle}
                  </p>
                </div>

                <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '12px', borderRadius: '8px', fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div><strong>Coordinates:</strong> {selectedMarker.latitude}°N, {selectedMarker.longitude}°E</div>
                  <div><strong>Severity:</strong> <span style={{ textTransform: 'capitalize', color: getMarkerColor(selectedMarker.layer, selectedMarker.severity) }}>{selectedMarker.severity}</span></div>
                  <div><strong>Verified Source:</strong> {selectedMarker.source}</div>
                  <div><strong>Reported Time:</strong> {new Date(selectedMarker.occurred_at).toLocaleString()}</div>
                </div>

                {selectedMarker.url && (
                  <a
                    href={selectedMarker.url}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px',
                      padding: '8px 12px',
                      borderRadius: '8px',
                      background: 'rgba(99, 102, 241, 0.15)',
                      color: '#818cf8',
                      textDecoration: 'none',
                      fontWeight: 600,
                      fontSize: '0.82rem',
                    }}
                  >
                    <ExternalLink size={14} /> Open Verified Source
                  </a>
                )}
              </>
            ) : (
              <div style={{ textAlign: 'center', padding: '40px 10px', color: 'var(--text-muted)' }}>
                <MapPin size={32} style={{ margin: '0 auto 12px', opacity: 0.5 }} />
                <h4 style={{ margin: '0 0 6px', color: 'var(--text-main)', fontSize: '0.95rem' }}>Select a Marker</h4>
                <p style={{ fontSize: '0.8rem', margin: 0 }}>
                  Click any marker on the world radar to inspect real-time earthquake magnitude, traffic delay, or webcam coordinates.
                </p>
              </div>
            )}

            {/* Top Critical Alerts Quick Feed */}
            <div style={{ marginTop: 'auto', borderTop: '1px solid var(--border-subtle)', paddingTop: '12px' }}>
              <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase' }}>
                Active Hazards & Alerts ({markers.filter((m) => m.severity === 'critical' || m.severity === 'high').length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {markers
                  .filter((m) => m.severity === 'critical' || m.severity === 'high')
                  .slice(0, 3)
                  .map((alert) => (
                    <div
                      key={alert.id}
                      onClick={() => setSelectedMarker(alert)}
                      style={{
                        padding: '8px',
                        borderRadius: '6px',
                        background: 'rgba(239, 68, 68, 0.08)',
                        border: '1px solid rgba(239, 68, 68, 0.2)',
                        cursor: 'pointer',
                        fontSize: '0.78rem',
                      }}
                    >
                      <div style={{ color: '#ef4444', fontWeight: 600 }}>{alert.title}</div>
                      <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>{alert.source}</div>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* VIEW 2: USGS DISASTERS FEED */}
      {activeTab === 'disasters' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ background: 'var(--bg-card)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-subtle)' }}>
            <h3 style={{ margin: '0 0 6px', color: 'var(--text-main)', fontSize: '1.1rem' }}>
              Global Seismic Activity (USGS Real-Time)
            </h3>
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Live seismic sensors capturing quakes worldwide within the last 24 hours.
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '12px' }}>
            {markers
              .filter((m) => m.layer === 'disaster')
              .map((q) => (
                <div
                  key={q.id}
                  style={{
                    background: 'var(--bg-card)',
                    borderRadius: '12px',
                    border: '1px solid var(--border-subtle)',
                    padding: '14px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span
                      style={{
                        padding: '2px 8px',
                        borderRadius: '4px',
                        background: `${getMarkerColor('disaster', q.severity)}22`,
                        color: getMarkerColor('disaster', q.severity),
                        fontWeight: 700,
                        fontSize: '0.75rem',
                      }}
                    >
                      {q.badge}
                    </span>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      {new Date(q.occurred_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <h4 style={{ margin: 0, fontSize: '0.95rem', color: 'var(--text-main)' }}>{q.title}</h4>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{q.subtitle}</div>
                  {q.url && (
                    <a
                      href={q.url}
                      target="_blank"
                      rel="noreferrer"
                      style={{
                        marginTop: '4px',
                        fontSize: '0.76rem',
                        color: '#818cf8',
                        textDecoration: 'none',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                      }}
                    >
                      <ExternalLink size={12} /> View USGS ShakeMap
                    </a>
                  )}
                </div>
              ))}
          </div>
        </div>
      )}

      {/* VIEW 3: TRAFFIC & HIGHWAYS */}
      {activeTab === 'traffic' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ background: 'var(--bg-card)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-subtle)' }}>
            <h3 style={{ margin: '0 0 6px', color: 'var(--text-main)', fontSize: '1.1rem' }}>
              Municipal Traffic & Highway Feeds
            </h3>
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Verified open municipal sensor feeds reporting flow speeds, congestion delays, and active roadway cameras.
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '12px' }}>
            {markers
              .filter((m) => m.layer === 'traffic')
              .map((f) => (
                <div
                  key={f.id}
                  style={{
                    background: 'var(--bg-card)',
                    borderRadius: '12px',
                    border: '1px solid var(--border-subtle)',
                    padding: '14px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 700, color: '#f97316', fontSize: '0.9rem' }}>
                      🚗 {f.title}
                    </span>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Live DOT Feed</span>
                  </div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>{f.subtitle}</div>
                  <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                    Coords: {f.latitude}°N, {f.longitude}°E
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* VIEW 4: SPACE & ASTEROIDS */}
      {activeTab === 'space' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ background: 'var(--bg-card)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-subtle)' }}>
            <h3 style={{ margin: '0 0 6px', color: 'var(--text-main)', fontSize: '1.1rem' }}>
              Near Earth Object Close Approaches (NASA NeoWs)
            </h3>
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Tracking planetary defense asteroids passing Earth orbit today.
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '12px' }}>
            {asteroids.map((ast) => (
              <div
                key={ast.id}
                style={{
                  background: 'var(--bg-card)',
                  borderRadius: '12px',
                  border: '1px solid var(--border-subtle)',
                  padding: '14px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h4 style={{ margin: 0, fontSize: '0.95rem', color: 'var(--text-main)' }}>🚀 {ast.name}</h4>
                  {ast.is_hazardous && (
                    <span style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#ef4444', padding: '2px 6px', borderRadius: '4px', fontSize: '0.7rem', fontWeight: 700 }}>
                      HAZARDOUS
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  <div><strong>Estimated Diameter:</strong> {ast.estimated_diameter_m}</div>
                  <div><strong>Miss Distance:</strong> {ast.miss_distance_km.toLocaleString()} km</div>
                  <div><strong>Velocity:</strong> {ast.relative_speed_kmh.toLocaleString()} km/h</div>
                </div>
                {ast.source_url && (
                  <a
                    href={ast.source_url}
                    target="_blank"
                    rel="noreferrer"
                    style={{ fontSize: '0.76rem', color: '#818cf8', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '4px' }}
                  >
                    <ExternalLink size={12} /> NASA Orbit Simulator
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* VIEW 5: FOREX & MACROECONOMICS */}
      {activeTab === 'economics' && economics && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ background: 'var(--bg-card)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-subtle)' }}>
            <h3 style={{ margin: '0 0 6px', color: 'var(--text-main)', fontSize: '1.1rem' }}>
              Global Currency Reference Rates (European Central Bank / Frankfurter)
            </h3>
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Base: 1 USD • Date: {economics.forex_date}
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px' }}>
            {Object.entries(economics.forex_usd_base).map(([curr, rate]) => (
              <div
                key={curr}
                style={{
                  background: 'var(--bg-card)',
                  borderRadius: '10px',
                  border: '1px solid var(--border-subtle)',
                  padding: '14px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>1 USD to</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)' }}>{curr}</div>
                </div>
                <div style={{ fontSize: '1.1rem', fontWeight: 600, color: '#10b981' }}>{rate}</div>
              </div>
            ))}
          </div>

          {economics.market_briefing && (
            <div style={{ background: 'var(--bg-card)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-subtle)' }}>
              <h4 style={{ margin: '0 0 8px', color: 'var(--text-main)', fontSize: '0.95rem' }}>Market & Commodity Telemetry</h4>
              <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                {economics.market_briefing}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

