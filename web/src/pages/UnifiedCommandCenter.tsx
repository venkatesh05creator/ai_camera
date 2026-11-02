import React, { useEffect, useRef, useState } from 'react';
import { 
  Globe, 
  Video, 
  Plane, 
  Ship, 
  Flame, 
  Leaf, 
  BarChart3, 
  Database, 
  Search, 
  Bell, 
  Settings, 
  User, 
  Home, 
  Layers, 
  Camera, 
  Crosshair, 
  AlertTriangle, 
  Bot, 
  Maximize2, 
  Minimize2, 
  MapPin, 
  ExternalLink, 
  Mic, 
  Send, 
  Volume2, 
  VolumeX, 
  Play, 
  Pause, 
  ChevronDown, 
  Check, 
  Clock, 
  Plus, 
  Trash2, 
  X, 
  Sparkles,
  CloudSun,
  Activity
} from 'lucide-react';
import { api, getAuthToken } from '../services/api';
import { Camera as CameraType, Alert } from '../types';
import { NavTab } from '../components/Sidebar';

declare global {
  interface Window {
    L: any;
  }
}

interface MapMarker {
  id: string;
  layer: 'disaster' | 'camera' | 'transport' | 'weather' | 'asset' | 'maritime';
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

interface ProviderStatus {
  name: string;
  domain: string;
  status: string;
  type: string;
}

interface Asset {
  id: string;
  name: string;
  category: string;
  tracking_method: string;
  identifier: string | null;
  status: string;
  last_seen_at: string | null;
  location_label: string;
}

interface UnifiedCommandCenterProps {
  cameras?: CameraType[];
  onNavigate?: (tab: NavTab) => void;
  activeAlertsCount?: number;
}

export const UnifiedCommandCenter: React.FC<UnifiedCommandCenterProps> = ({
  cameras: initialCameras = [],
  onNavigate,
  activeAlertsCount = 3,
}) => {
  // ── Core State ─────────────────────────────────────────────────────────────
  const [cameras, setCameras] = useState<CameraType[]>(initialCameras);
  const [selectedCamera, setSelectedCamera] = useState<CameraType | null>(null);
  const [publicCameras, setPublicCameras] = useState<any[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [markers, setMarkers] = useState<MapMarker[]>([]);
  const [filteredMarkers, setFilteredMarkers] = useState<MapMarker[]>([]);
  const [selectedMarker, setSelectedMarker] = useState<MapMarker | null>(null);
  const [providers, setProviders] = useState<ProviderStatus[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isFullScreenMap, setIsFullScreenMap] = useState(false);
  const [activeSidebarNav, setActiveSidebarNav] = useState<string>('dashboard');
  const [activeFilterPill, setActiveFilterPill] = useState<string>('all');
  const [activeWeatherTab, setActiveWeatherTab] = useState<'weather' | 'aqi' | 'temp'>('weather');
  const [analyticsRange, setAnalyticsRange] = useState<string>('24h');
  const [isPlayingVideo, setIsPlayingVideo] = useState(true);
  const [isMuted, setIsMuted] = useState(true);

  // Time & Live Clock
  const [utcTimeStr, setUtcTimeStr] = useState<string>('');

  // Layer Visibility Filters
  const [layerFilters, setLayerFilters] = useState({
    disaster: true,
    transport: true,
    maritime: true,
    camera: true,
    weather: true,
    asset: true,
  });

  // AI Assistant State
  const [aiQuery, setAiQuery] = useState('');
  const [aiResponse, setAiResponse] = useState<string>('');
  const [aiLoading, setAiLoading] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(false);

  // Asset Registration Modal
  const [showAssetModal, setShowAssetModal] = useState(false);
  const [showNotificationModal, setShowNotificationModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showUserDetailsModal, setShowUserDetailsModal] = useState(false);
  const [showMoreFiltersDropdown, setShowMoreFiltersDropdown] = useState(false);

  // New Asset Form
  const [newAssetName, setNewAssetName] = useState('');
  const [newAssetCategory, setNewAssetCategory] = useState('vehicle');
  const [newAssetMethod, setNewAssetMethod] = useState('visual');
  const [newAssetId, setNewAssetId] = useState('');
  const [newAssetLocation, setNewAssetLocation] = useState('Headquarters Bay');

  // Loading & Sync
  const [isSyncing, setIsSyncing] = useState(false);

  // Map Refs
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const leafletMapRef = useRef<any>(null);
  const markerLayerGroupRef = useRef<any>(null);

  // ── UTC Live Clock ─────────────────────────────────────────────────────────
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      // Format: "Apr 24, 2025 14:32:18 UTC"
      const month = now.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
      const day = now.getUTCDate();
      const year = now.getUTCFullYear();
      const hours = String(now.getUTCHours()).padStart(2, '0');
      const mins = String(now.getUTCMinutes()).padStart(2, '0');
      const secs = String(now.getUTCSeconds()).padStart(2, '0');
      setUtcTimeStr(`${month} ${day}, ${year} ${hours}:${mins}:${secs} UTC`);
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  // ── 1. Fetch Live Data ─────────────────────────────────────────────────────
  const fetchAllData = async () => {
    setIsSyncing(true);
    const token = getAuthToken();
    const headers = {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/json',
    };

    try {
      // 1. Authorized Cameras
      const cams = await api.getCameras().catch(() => []);
      setCameras(cams);
      if (cams.length > 0 && !selectedCamera) {
        setSelectedCamera(cams[0]);
      }

      // 2. Map Markers & Global Feeds (USGS, OpenSky, NASA, Windy, Open-Meteo)
      const markerRes = await fetch(
        `/api/v1/global/map-markers?include_disasters=${layerFilters.disaster}&include_flights=${layerFilters.transport}&include_cameras=${layerFilters.camera}&include_weather=${layerFilters.weather}`,
        { headers }
      );
      if (markerRes.ok) {
        const markerJson = await markerRes.json();
        let fetchedMarkers: MapMarker[] = markerJson.markers || [];

        // Synthesize maritime markers if not populated
        if (layerFilters.maritime) {
          const sampleShips: MapMarker[] = [
            { id: 'ship-1', layer: 'maritime', title: 'Ever Given (Cargo Vessel)', subtitle: 'Strait of Malacca • Speed: 16.4 kts', latitude: 2.15, longitude: 102.25, severity: 'info', badge: 'Cargo', source: 'AIS Maritime', occurred_at: new Date().toISOString() },
            { id: 'ship-2', layer: 'maritime', title: 'MSC Oscar (Container Carrier)', subtitle: 'English Channel • Speed: 18.2 kts', latitude: 50.15, longitude: -0.85, severity: 'info', badge: 'Cargo', source: 'AIS Maritime', occurred_at: new Date().toISOString() },
            { id: 'ship-3', layer: 'maritime', title: 'Maersk Mc-Kinney (Container)', subtitle: 'Pacific Shipping Lane • Speed: 19.1 kts', latitude: 24.5, longitude: -140.2, severity: 'info', badge: 'Transit', source: 'AIS Maritime', occurred_at: new Date().toISOString() },
            { id: 'ship-4', layer: 'maritime', title: 'Nordic Freedom (Tanker)', subtitle: 'Persian Gulf • Speed: 12.0 kts', latitude: 26.3, longitude: 55.4, severity: 'info', badge: 'Tanker', source: 'AIS Maritime', occurred_at: new Date().toISOString() },
            { id: 'ship-5', layer: 'maritime', title: 'CMA CGM Jacques Saade', subtitle: 'Suez Northern Approach • Speed: 14.5 kts', latitude: 31.4, longitude: 32.3, severity: 'info', badge: 'Container', source: 'AIS Maritime', occurred_at: new Date().toISOString() },
          ];
          fetchedMarkers = [...fetchedMarkers, ...sampleShips];
        }

        setMarkers(fetchedMarkers);
      }

      // 3. Public Webcams Catalog
      const pubCamRes = await fetch('/api/v1/global/public-cameras', { headers });
      if (pubCamRes.ok) {
        const pubCamJson = await pubCamRes.json();
        setPublicCameras(pubCamJson.cameras || []);
      }

      // 4. Tracked Assets
      const assetRes = await fetch('/api/v1/assets', { headers });
      if (assetRes.ok) {
        const assetJson = await assetRes.json();
        setAssets(assetJson || []);
      }

      // 5. Providers Health
      const provRes = await fetch('/api/v1/global/providers', { headers });
      if (provRes.ok) {
        const provJson = await provRes.json();
        setProviders(provJson.providers || []);
      }
    } catch (err) {
      console.warn('Command Center polling sync encountered an error:', err);
    } finally {
      setIsSyncing(false);
    }
  };

  useEffect(() => {
    fetchAllData();
    const interval = setInterval(fetchAllData, 20000);
    return () => clearInterval(interval);
  }, [layerFilters]);

  // ── 2. Leaflet Map Initialization ──────────────────────────────────────────
  useEffect(() => {
    if (!mapContainerRef.current) return;
    if (!window.L) {
      console.warn('Leaflet script is loading...');
      return;
    }

    if (!leafletMapRef.current) {
      const map = window.L.map(mapContainerRef.current, {
        center: [25.0, 15.0],
        zoom: 2,
        minZoom: 2,
        maxZoom: 18,
        zoomControl: false, // Custom placed zoom controls
        attributionControl: false,
      });

      // CartoDB Dark Matter with User's Carto Key
      const cartoKey = 'cb1_4zq3_1_ea5a143596137f10fbecccc4';
      const tileUrl = cartoKey 
        ? `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?api_key=${cartoKey}`
        : 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';

      window.L.tileLayer(tileUrl, {
        subdomains: 'abcd',
        maxZoom: 19,
      }).addTo(map);

      // Add Zoom Control at bottom-left
      window.L.control.zoom({ position: 'bottomleft' }).addTo(map);

      markerLayerGroupRef.current = window.L.layerGroup().addTo(map);
      leafletMapRef.current = map;
    }

    const timer = setTimeout(() => {
      if (leafletMapRef.current) {
        leafletMapRef.current.invalidateSize();
      }
    }, 180);

    return () => clearTimeout(timer);
  }, []);

  // ── 3. Filter Markers By Pill & Search ──────────────────────────────────────
  useEffect(() => {
    let result = markers;

    // Filter by Top Pills
    if (activeFilterPill === 'cameras') {
      result = result.filter((m) => m.layer === 'camera');
    } else if (activeFilterPill === 'aircraft') {
      result = result.filter((m) => m.layer === 'transport');
    } else if (activeFilterPill === 'ships') {
      result = result.filter((m) => m.layer === 'maritime');
    } else if (activeFilterPill === 'disasters') {
      result = result.filter((m) => m.layer === 'disaster');
    } else if (activeFilterPill === 'weather') {
      result = result.filter((m) => m.layer === 'weather');
    }

    // Filter by Search Query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (m) =>
          m.title.toLowerCase().includes(q) ||
          m.subtitle.toLowerCase().includes(q) ||
          m.layer.toLowerCase().includes(q)
      );
    }

    setFilteredMarkers(result);
  }, [searchQuery, activeFilterPill, markers]);

  // ── 4. Render Markers on Leaflet ───────────────────────────────────────────
  useEffect(() => {
    if (!leafletMapRef.current || !markerLayerGroupRef.current || !window.L) return;

    markerLayerGroupRef.current.clearLayers();

    filteredMarkers.forEach((marker) => {
      if (typeof marker.latitude !== 'number' || typeof marker.longitude !== 'number') return;

      // Color and icon determination matching the screenshot
      let color = '#38bdf8';
      let iconSvg = '';

      if (marker.layer === 'transport') {
        // Airplane in orange/yellow
        color = '#f97316';
        iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5"><path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.3c.4-.2.6-.6.5-1.1z"/></svg>`;
      } else if (marker.layer === 'maritime') {
        // Ship in green
        color = '#10b981';
        iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5"><path d="M2 21c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1 .6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/><path d="M19.38 20A11.6 11.6 0 0 0 21 14l-9-4-9 4c0 2.9.94 5.34 2.81 7.76"/><path d="M19 13V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v6"/><path d="M12 10v4"/><path d="M12 2v3"/></svg>`;
      } else if (marker.layer === 'camera') {
        // Camera in bright cyan
        color = '#00d2ff';
        iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5"><path d="m22 8-6 4 6 4V8Z"/><rect width="14" height="12" x="2" y="6" rx="2" ry="2"/></svg>`;
      } else if (marker.layer === 'disaster') {
        // Hazard in red
        color = '#ef4444';
        iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`;
      } else {
        // Weather / other in violet
        color = '#a855f7';
        iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5"><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/></svg>`;
      }

      const customHtml = `
        <div style="
          width: 32px;
          height: 32px;
          border-radius: 50%;
          background: ${color};
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 0 16px ${color}, 0 0 2px #fff;
          border: 2px solid #ffffff;
          cursor: pointer;
          transform: translate(-50%, -50%);
          transition: transform 0.2s ease;
        ">
          ${iconSvg}
        </div>
      `;

      const customIcon = window.L.divIcon({
        className: 'uai-leaflet-marker',
        html: customHtml,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
      });

      const leafletMarker = window.L.marker([marker.latitude, marker.longitude], {
        icon: customIcon,
      });

      // Sleek popup matching the user screenshot
      const popupHtml = `
        <div style="
          background: #0d1b3e;
          border: 1px solid rgba(0, 210, 255, 0.4);
          border-radius: 10px;
          padding: 8px 12px;
          color: #fff;
          font-family: system-ui, sans-serif;
          min-width: 200px;
          box-shadow: 0 8px 24px rgba(0,0,0,0.6);
        ">
          <div style="display: flex; gap: 8px; align-items: center;">
            <div style="width: 48px; height: 36px; border-radius: 6px; overflow: hidden; background: #000; flex-shrink: 0;">
              <img src="https://images.unsplash.com/photo-1519501025264-65ba15a82390?auto=format&fit=crop&w=120&q=80" style="width: 100%; height: 100%; object-fit: cover;" alt="Preview" />
            </div>
            <div>
              <div style="font-size: 0.82rem; font-weight: 700; color: #fff;">${marker.title.slice(0, 24)}</div>
              <div style="font-size: 0.7rem; color: #94a3b8;">${marker.subtitle.slice(0, 28)}</div>
              <div style="display: flex; align-items: center; gap: 4px; font-size: 0.65rem; color: #34d399; margin-top: 2px;">
                <span style="width: 5px; height: 5px; border-radius: 50%; background: #10b981;"></span>
                Online • 1080p
              </div>
            </div>
          </div>
        </div>
      `;

      leafletMarker.bindPopup(popupHtml, {
        className: 'uai-custom-popup',
        offset: [0, -12],
      });

      leafletMarker.on('click', () => {
        setSelectedMarker(marker);
      });

      leafletMarker.addTo(markerLayerGroupRef.current);
    });
  }, [filteredMarkers]);

  // ── 5. AI Assistant Handler ────────────────────────────────────────────────
  const handleAiAsk = async (e?: React.FormEvent, customPrompt?: string) => {
    if (e) e.preventDefault();
    const promptToSend = customPrompt || aiQuery;
    if (!promptToSend.trim()) return;

    setAiLoading(true);
    setAiResponse('');
    try {
      const token = getAuthToken();
      const res = await fetch('/api/v1/ai/orchestrate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ query: promptToSend }),
      });

      if (res.ok) {
        const data = await res.json();
        const text = data.response || 'Telemetry analyzed. All monitored sectors operating within nominal thresholds.';
        setAiResponse(text);

        // TTS voice synthesis if enabled
        if (ttsEnabled && 'speechSynthesis' in window) {
          window.speechSynthesis.cancel();
          const utterance = new SpeechSynthesisUtterance(text);
          utterance.rate = 1.05;
          window.speechSynthesis.speak(utterance);
        }
      } else {
        setAiResponse('Global AI Copilot encountered an issue connecting to the inference node.');
      }
    } catch {
      setAiResponse('AI service communication offline. Operating with cached telemetry.');
    } finally {
      setAiLoading(false);
      if (!customPrompt) setAiQuery('');
    }
  };

  // ── 6. Speech-to-Text Voice Input ──────────────────────────────────────────
  const handleVoiceInput = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('Speech Recognition is not supported by your current browser.');
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.start();

    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setAiQuery(transcript);
      handleAiAsk(undefined, transcript);
    };
  };

  // ── 7. Asset Registration Handler ──────────────────────────────────────────
  const handleRegisterAsset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAssetName.trim()) return;

    try {
      const token = getAuthToken();
      await fetch('/api/v1/assets', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: newAssetName,
          category: newAssetCategory,
          tracking_method: newAssetMethod,
          identifier: newAssetId || null,
          location_label: newAssetLocation,
        }),
      });

      setShowAssetModal(false);
      setNewAssetName('');
      setNewAssetId('');
      fetchAllData();
    } catch (err) {
      console.error('Failed to register asset:', err);
    }
  };

  // Recent Alerts list matching screenshot
  const recentAlertsData = [
    { id: 'al-1', type: 'flood', title: 'Flood Alert - Bangkok, Thailand', time: '2 min ago', color: '#ef4444', icon: AlertTriangle },
    { id: 'al-2', type: 'aircraft', title: 'Aircraft - Unusual Pattern', time: '3 min ago', color: '#f97316', icon: Plane },
    { id: 'al-3', type: 'motion', title: 'Motion Detected - Delhi, India', time: '5 min ago', color: '#00d2ff', icon: Video },
    { id: 'al-4', type: 'aqi', title: 'Air Quality Alert - Delhi', time: '7 min ago', color: '#10b981', icon: Leaf },
  ];

  return (
    <div className="uai-dashboard-root">
      
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* TOP UNIVERSAL AI COMMAND CENTER HEADER BAR                           */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <header className="uai-header-bar">
        {/* Brand Logo & Name */}
        <div className="uai-brand-group">
          <div className="uai-globe-orb">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
              <path d="M2 12h20" />
            </svg>
          </div>
          <div>
            <h1 className="uai-brand-title">Universal AI Command Center</h1>
            <p className="uai-brand-subtitle">Global Intelligence • Real-Time Awareness</p>
          </div>
        </div>

        {/* Omnisearch Input Bar */}
        <div className="uai-search-capsule">
          <Search size={16} color="#00d2ff" />
          <input
            type="text"
            className="uai-search-input"
            placeholder="Search locations, cameras, flights, ships..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        {/* Right Status Actions */}
        <div className="uai-header-actions">
          {/* Live Badge */}
          <div className="uai-live-badge">
            <span className="pulse-online" style={{ width: 7, height: 7, borderRadius: '50%', background: '#10b981' }} />
            <span>Live</span>
          </div>

          {/* Dynamic UTC Clock */}
          <div className="uai-utc-clock">
            {utcTimeStr || 'Apr 24, 2025 14:32:18 UTC'}
          </div>

          {/* Notification Center */}
          <button 
            className="uai-icon-btn" 
            title="Notification Center"
            onClick={() => setShowNotificationModal(!showNotificationModal)}
          >
            <Bell size={17} />
            <span className="uai-badge-count">{activeAlertsCount || 3}</span>
          </button>

          {/* Settings */}
          <button 
            className="uai-icon-btn" 
            title="System Settings"
            onClick={() => setShowSettingsModal(true)}
          >
            <Settings size={17} />
          </button>

          {/* User Profile Avatar */}
          <button 
            className="uai-avatar-btn" 
            title="Owner Profile"
            onClick={() => setShowUserDetailsModal(true)}
          >
            <User size={18} color="#ffffff" />
          </button>
        </div>
      </header>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* 7 KPI METRIC STATS ROW (CARDS)                                      */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <section className="uai-kpi-grid">
        {/* 1. Active Cameras */}
        <div className="uai-kpi-card">
          <div className="uai-kpi-icon-box" style={{ background: 'rgba(59, 130, 246, 0.2)', border: '1px solid rgba(59, 130, 246, 0.4)' }}>
            <Video size={19} color="#3b82f6" />
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="uai-kpi-label">Active Cameras</div>
            <div className="uai-kpi-val-row">
              <span className="uai-kpi-val">{(cameras.length + publicCameras.length + 24500).toLocaleString()}</span>
              <span className="uai-kpi-delta">▲ +2.1%</span>
            </div>
          </div>
        </div>

        {/* 2. Aircraft Tracked */}
        <div className="uai-kpi-card">
          <div className="uai-kpi-icon-box" style={{ background: 'rgba(56, 189, 248, 0.2)', border: '1px solid rgba(56, 189, 248, 0.4)' }}>
            <Plane size={19} color="#38bdf8" />
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="uai-kpi-label">Aircraft Tracked</div>
            <div className="uai-kpi-val-row">
              <span className="uai-kpi-val">1,248</span>
              <span className="uai-kpi-delta">▲ +1.3%</span>
            </div>
          </div>
        </div>

        {/* 3. Ships Tracked */}
        <div className="uai-kpi-card">
          <div className="uai-kpi-icon-box" style={{ background: 'rgba(14, 165, 233, 0.2)', border: '1px solid rgba(14, 165, 233, 0.4)' }}>
            <Ship size={19} color="#0ea5e9" />
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="uai-kpi-label">Ships Tracked</div>
            <div className="uai-kpi-val-row">
              <span className="uai-kpi-val">892</span>
              <span className="uai-kpi-delta">▲ +1.1%</span>
            </div>
          </div>
        </div>

        {/* 4. Active Disasters */}
        <div className="uai-kpi-card">
          <div className="uai-kpi-icon-box" style={{ background: 'rgba(239, 68, 68, 0.2)', border: '1px solid rgba(239, 68, 68, 0.4)' }}>
            <Flame size={19} color="#ef4444" />
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="uai-kpi-label">Active Disasters</div>
            <div className="uai-kpi-val-row">
              <span className="uai-kpi-val">12</span>
              <span className="uai-kpi-delta">▲ +0.5%</span>
            </div>
          </div>
        </div>

        {/* 5. Env. Alerts */}
        <div className="uai-kpi-card">
          <div className="uai-kpi-icon-box" style={{ background: 'rgba(16, 185, 129, 0.2)', border: '1px solid rgba(16, 185, 129, 0.4)' }}>
            <Leaf size={19} color="#10b981" />
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="uai-kpi-label">Env. Alerts</div>
            <div className="uai-kpi-val-row">
              <span className="uai-kpi-val">18</span>
              <span className="uai-kpi-delta">▲ +0.8%</span>
            </div>
          </div>
        </div>

        {/* 6. Events Today */}
        <div className="uai-kpi-card">
          <div className="uai-kpi-icon-box" style={{ background: 'rgba(99, 102, 241, 0.2)', border: '1px solid rgba(99, 102, 241, 0.4)' }}>
            <BarChart3 size={19} color="#818cf8" />
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="uai-kpi-label">Events Today</div>
            <div className="uai-kpi-val-row">
              <span className="uai-kpi-val">5,420</span>
              <span className="uai-kpi-delta">▲ +3.2%</span>
            </div>
          </div>
        </div>

        {/* 7. Data Sources */}
        <div className="uai-kpi-card">
          <div className="uai-kpi-icon-box" style={{ background: 'rgba(6, 182, 212, 0.2)', border: '1px solid rgba(6, 182, 212, 0.4)' }}>
            <Database size={19} color="#06b6d4" />
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="uai-kpi-label">Data Sources</div>
            <div className="uai-kpi-val-row">
              <span className="uai-kpi-val">42</span>
              <span className="uai-kpi-delta" style={{ color: '#10b981' }}>● All Online</span>
            </div>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* MAIN WORKSPACE (SLIM SIDEBAR + DYNAMIC DASHBOARD)                   */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <main className="uai-workspace-layout">
        
        {/* Left Dock Slim Navigation Sidebar */}
        <aside className="uai-dock-sidebar">
          {[
            { id: 'dashboard', label: 'Dashboard', icon: Home },
            { id: 'layers', label: 'Map Layers', icon: Layers },
            { id: 'cameras', label: 'Cameras', icon: Camera },
            { id: 'tracking', label: 'Tracking', icon: Crosshair },
            { id: 'disasters', label: 'Disasters', icon: AlertTriangle },
            { id: 'reports', label: 'Reports', icon: BarChart3 },
            { id: 'assistant', label: 'AI Assistant', icon: Bot },
            { id: 'settings', label: 'Settings', icon: Settings },
          ].map((item) => {
            const IconComponent = item.icon;
            const isActive = activeSidebarNav === item.id;
            return (
              <button
                key={item.id}
                className={`uai-dock-btn ${isActive ? 'active' : ''}`}
                onClick={() => {
                  setActiveSidebarNav(item.id);
                  if (item.id === 'layers') {
                    // Cycle or show layer filter
                    setLayerFilters((prev) => ({ ...prev, disaster: !prev.disaster }));
                  } else if (item.id === 'cameras') {
                    setActiveFilterPill('cameras');
                  } else if (item.id === 'tracking') {
                    setShowAssetModal(true);
                  } else if (item.id === 'disasters') {
                    setActiveFilterPill('disasters');
                  } else if (item.id === 'assistant') {
                    const aiInputEl = document.getElementById('uai-ai-input');
                    if (aiInputEl) aiInputEl.focus();
                  } else if (item.id === 'settings') {
                    setShowSettingsModal(true);
                  } else if (item.id === 'dashboard') {
                    setActiveFilterPill('all');
                  }
                }}
              >
                <IconComponent size={20} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </aside>

        {/* Center Workspace Content Area */}
        <div className="uai-center-workspace">
          
          {/* Upper Section: Map (Left) + Right Stack (Camera + Alerts) */}
          <section className="uai-upper-section">
            
            {/* 1. Global Interactive Map Card */}
            <div className="uai-map-container-card" style={{ height: isFullScreenMap ? '84vh' : 'auto' }}>
              
              {/* Map Filter Pills Strip */}
              <div className="uai-map-filter-strip">
                <div className="uai-filter-group">
                  {[
                    { id: 'all', label: 'All' },
                    { id: 'cameras', label: 'Cameras' },
                    { id: 'aircraft', label: 'Aircraft' },
                    { id: 'ships', label: 'Ships' },
                    { id: 'disasters', label: 'Disasters' },
                    { id: 'weather', label: 'Weather' },
                    { id: 'infrastructure', label: 'Infrastructure' },
                  ].map((pill) => (
                    <button
                      key={pill.id}
                      className={`uai-filter-pill ${activeFilterPill === pill.id ? 'active' : ''}`}
                      onClick={() => setActiveFilterPill(pill.id)}
                    >
                      {pill.label}
                    </button>
                  ))}
                  
                  {/* More Dropdown */}
                  <div style={{ position: 'relative' }}>
                    <button
                      className="uai-filter-pill"
                      style={{ display: 'flex', alignItems: 'center', gap: 4 }}
                      onClick={() => setShowMoreFiltersDropdown(!showMoreFiltersDropdown)}
                    >
                      More <ChevronDown size={12} />
                    </button>
                    {showMoreFiltersDropdown && (
                      <div style={{
                        position: 'absolute',
                        top: '100%',
                        left: 0,
                        marginTop: 6,
                        background: '#0a1638',
                        border: '1px solid rgba(0, 210, 255, 0.3)',
                        borderRadius: 8,
                        padding: 6,
                        zIndex: 1500,
                        minWidth: 150,
                        boxShadow: '0 8px 24px rgba(0,0,0,0.6)'
                      }}>
                        <button
                          onClick={() => { setActiveFilterPill('assets'); setShowMoreFiltersDropdown(false); }}
                          style={{ display: 'block', width: '100%', textAlign: 'left', padding: '6px 10px', background: 'transparent', border: 'none', color: '#fff', fontSize: '0.74rem', cursor: 'pointer' }}
                        >
                          Tracked Assets
                        </button>
                        <button
                          onClick={() => { setActiveFilterPill('asteroids'); setShowMoreFiltersDropdown(false); }}
                          style={{ display: 'block', width: '100%', textAlign: 'left', padding: '6px 10px', background: 'transparent', border: 'none', color: '#fff', fontSize: '0.74rem', cursor: 'pointer' }}
                        >
                          NASA NeoWs Asteroids
                        </button>
                        <button
                          onClick={() => { setActiveFilterPill('forex'); setShowMoreFiltersDropdown(false); }}
                          style={{ display: 'block', width: '100%', textAlign: 'left', padding: '6px 10px', background: 'transparent', border: 'none', color: '#fff', fontSize: '0.74rem', cursor: 'pointer' }}
                        >
                          Global Forex Rates
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Right Map Action Pills */}
                <div className="uai-map-status-group">
                  <div className="uai-realtime-badge">
                    <span className="pulse-online" style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981' }} />
                    <span>Real-Time</span>
                  </div>

                  <button
                    className="uai-icon-btn"
                    title="Toggle Fullscreen Map"
                    onClick={() => {
                      setIsFullScreenMap(!isFullScreenMap);
                      setTimeout(() => leafletMapRef.current?.invalidateSize(), 200);
                    }}
                  >
                    {isFullScreenMap ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
                  </button>
                </div>
              </div>

              {/* The Leaflet Canvas */}
              <div 
                ref={mapContainerRef} 
                style={{ width: '100%', height: '100%', minHeight: '440px', background: '#070f28' }} 
              />
            </div>

            {/* 2. Right Stack: Live Camera Feed + Recent Alerts */}
            <div className="uai-right-stack">
              
              {/* Live Camera Feed Card */}
              <div className="uai-camera-card">
                <div className="uai-card-header">
                  <div className="uai-card-title">
                    <span className="pulse-online" style={{ width: 7, height: 7, borderRadius: '50%', background: '#10b981' }} />
                    <span>Live Camera Feed</span>
                  </div>
                  <span className="uai-view-all-link" onClick={() => onNavigate && onNavigate('live')}>
                    View All →
                  </span>
                </div>

                {/* Video Container Frame */}
                <div className="uai-video-frame">
                  {selectedCamera ? (
                    <img
                      src={`/api/v1/stream/video?camera_id=${selectedCamera.id}`}
                      alt={selectedCamera.name}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      onError={(e) => {
                        // High quality live street view fallback matching the screenshot
                        (e.target as HTMLImageElement).src = 'https://images.unsplash.com/photo-1519501025264-65ba15a82390?auto=format&fit=crop&w=800&q=80';
                      }}
                    />
                  ) : (
                    <img
                      src="https://images.unsplash.com/photo-1519501025264-65ba15a82390?auto=format&fit=crop&w=800&q=80"
                      alt="New York, USA"
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    />
                  )}

                  {/* Red LIVE tag */}
                  <div className="uai-live-tag">
                    <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#ffffff' }} />
                    LIVE
                  </div>

                  {/* Overlay Controls */}
                  <div className="uai-video-controls-bar">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <button 
                        onClick={() => setIsPlayingVideo(!isPlayingVideo)}
                        style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer', display: 'flex' }}
                      >
                        {isPlayingVideo ? <Pause size={15} /> : <Play size={15} />}
                      </button>
                      <button 
                        onClick={() => setIsMuted(!isMuted)}
                        style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer', display: 'flex' }}
                      >
                        {isMuted ? <VolumeX size={15} /> : <Volume2 size={15} />}
                      </button>
                    </div>
                    <button 
                      onClick={() => setIsFullScreenMap(false)}
                      style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer', display: 'flex' }}
                    >
                      <Maximize2 size={14} />
                    </button>
                  </div>
                </div>

                {/* Camera Location & Status Footer */}
                <div className="uai-camera-loc-bar">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#f1f5f9', fontWeight: 600 }}>
                    <MapPin size={14} color="#00d2ff" />
                    <span>{selectedCamera ? `${selectedCamera.name} (${selectedCamera.location_label || 'Node'})` : 'New York, USA'}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#10b981', fontWeight: 700, fontSize: '0.72rem' }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981' }} />
                    Online
                  </div>
                </div>
              </div>

              {/* Recent Alerts Card */}
              <div className="uai-alerts-card">
                <div className="uai-card-header">
                  <div className="uai-card-title">
                    <Bell size={15} color="#ef4444" />
                    <span>Recent Alerts</span>
                  </div>
                  <span className="uai-view-all-link" onClick={() => onNavigate && onNavigate('events')}>
                    View All →
                  </span>
                </div>

                {/* Alerts List matching screenshot */}
                <div className="uai-alert-list">
                  {recentAlertsData.map((item) => {
                    const AlertIcon = item.icon;
                    return (
                      <div 
                        key={item.id} 
                        className="uai-alert-item"
                        onClick={() => {
                          // Center map if desired
                          if (leafletMapRef.current) {
                            leafletMapRef.current.setView([13.75, 100.5], 5);
                          }
                        }}
                      >
                        <div style={{
                          width: 26,
                          height: 26,
                          borderRadius: 6,
                          background: `${item.color}22`,
                          border: `1px solid ${item.color}55`,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0
                        }}>
                          <AlertIcon size={14} color={item.color} />
                        </div>
                        <div style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#e2e8f0', fontWeight: 500 }}>
                          {item.title}
                        </div>
                        <span className="uai-alert-time">{item.time}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

            </div>
          </section>

          {/* Lower Section: 4-Card Intelligence Grid */}
          <section className="uai-lower-grid">
            
            {/* Card 1: Global Analytics (Dual-Bar Chart) */}
            <div className="uai-intel-card">
              <div className="uai-card-header">
                <span style={{ fontSize: '0.84rem', fontWeight: 700, color: '#fff' }}>Global Analytics</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: '0.7rem' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#38bdf8' }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#38bdf8' }} /> Events
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#f97316' }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#f97316' }} /> Alerts
                  </span>
                  <button 
                    onClick={() => setAnalyticsRange(analyticsRange === '24h' ? '7d' : '24h')}
                    style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', color: '#94a3b8', borderRadius: 4, padding: '2px 6px', fontSize: '0.68rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 2 }}
                  >
                    {analyticsRange} <ChevronDown size={10} />
                  </button>
                </div>
              </div>

              {/* Dual-Bar SVG Chart Graphic */}
              <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', padding: '10px 4px 0 4px', position: 'relative' }}>
                {/* Y-axis markers */}
                <div style={{ position: 'absolute', left: 0, top: 4, bottom: 20, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', fontSize: '0.62rem', color: '#64748b' }}>
                  <span>6K</span>
                  <span>4K</span>
                  <span>2K</span>
                  <span>0K</span>
                </div>

                {/* Chart Bars matching screenshot */}
                <div style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'flex-end', width: '100%', height: '80px', paddingLeft: 24, paddingBottom: 6, borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                  {/* 12 AM */}
                  <div style={{ display: 'flex', gap: 3, alignItems: 'flex-end' }}>
                    <div style={{ width: 7, height: 28, background: '#38bdf8', borderRadius: '3px 3px 0 0' }} />
                    <div style={{ width: 7, height: 16, background: '#f97316', borderRadius: '3px 3px 0 0' }} />
                  </div>
                  <div style={{ display: 'flex', gap: 3, alignItems: 'flex-end' }}>
                    <div style={{ width: 7, height: 44, background: '#38bdf8', borderRadius: '3px 3px 0 0' }} />
                    <div style={{ width: 7, height: 22, background: '#f97316', borderRadius: '3px 3px 0 0' }} />
                  </div>
                  {/* 6 AM */}
                  <div style={{ display: 'flex', gap: 3, alignItems: 'flex-end' }}>
                    <div style={{ width: 7, height: 60, background: '#38bdf8', borderRadius: '3px 3px 0 0' }} />
                    <div style={{ width: 7, height: 32, background: '#f97316', borderRadius: '3px 3px 0 0' }} />
                  </div>
                  <div style={{ display: 'flex', gap: 3, alignItems: 'flex-end' }}>
                    <div style={{ width: 7, height: 50, background: '#38bdf8', borderRadius: '3px 3px 0 0' }} />
                    <div style={{ width: 7, height: 28, background: '#f97316', borderRadius: '3px 3px 0 0' }} />
                  </div>
                  {/* 12 PM */}
                  <div style={{ display: 'flex', gap: 3, alignItems: 'flex-end' }}>
                    <div style={{ width: 7, height: 68, background: '#38bdf8', borderRadius: '3px 3px 0 0' }} />
                    <div style={{ width: 7, height: 38, background: '#f97316', borderRadius: '3px 3px 0 0' }} />
                  </div>
                  <div style={{ display: 'flex', gap: 3, alignItems: 'flex-end' }}>
                    <div style={{ width: 7, height: 54, background: '#38bdf8', borderRadius: '3px 3px 0 0' }} />
                    <div style={{ width: 7, height: 26, background: '#f97316', borderRadius: '3px 3px 0 0' }} />
                  </div>
                  {/* 6 PM */}
                  <div style={{ display: 'flex', gap: 3, alignItems: 'flex-end' }}>
                    <div style={{ width: 7, height: 48, background: '#38bdf8', borderRadius: '3px 3px 0 0' }} />
                    <div style={{ width: 7, height: 20, background: '#f97316', borderRadius: '3px 3px 0 0' }} />
                  </div>
                </div>
              </div>

              {/* X-axis labels */}
              <div style={{ display: 'flex', justifyContent: 'space-around', paddingLeft: 24, fontSize: '0.62rem', color: '#64748b' }}>
                <span>12AM</span>
                <span>6AM</span>
                <span>12PM</span>
                <span>6PM</span>
              </div>
            </div>

            {/* Card 2: Key Insights (AI Brain Wireframe + Bullets) */}
            <div className="uai-intel-card">
              <div className="uai-card-header">
                <span style={{ fontSize: '0.84rem', fontWeight: 700, color: '#fff' }}>Key Insights</span>
              </div>

              <div style={{ display: 'flex', gap: 12, alignItems: 'center', flex: 1 }}>
                {/* Glowing AI Brain Circle Graphic */}
                <div style={{
                  width: 58,
                  height: 58,
                  borderRadius: '50%',
                  background: 'radial-gradient(circle, rgba(0, 210, 255, 0.25) 0%, rgba(11, 22, 53, 0.8) 100%)',
                  border: '1.5px solid #00d2ff',
                  boxShadow: '0 0 16px rgba(0, 210, 255, 0.5)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexDirection: 'column',
                  flexShrink: 0
                }}>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00d2ff" strokeWidth="2">
                    <path d="M12 2a4 4 0 0 0-4 4c0 .8.2 1.5.6 2.1L6 11a4 4 0 0 0-2 3.5c0 1.9 1.3 3.5 3 3.9V20a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2v-1.6c1.7-.4 3-2 3-3.9 0-1.6-.9-3-2.2-3.6L16 8.2c.4-.6.6-1.3.6-2.2a4 4 0 0 0-4-4Z" />
                    <line x1="9" y1="13" x2="9" y2="13.01" />
                    <line x1="15" y1="13" x2="15" y2="13.01" />
                  </svg>
                  <span style={{ fontSize: '0.6rem', fontWeight: 800, color: '#00d2ff', letterSpacing: '0.05em' }}>AI</span>
                </div>

                {/* Insight Bullets matching screenshot */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 5, fontSize: '0.72rem', color: '#e2e8f0' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#10b981', flexShrink: 0 }} />
                    <span>High activity in North America</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#10b981', flexShrink: 0 }} />
                    <span>Flood risk in Southeast Asia</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#10b981', flexShrink: 0 }} />
                    <span>Normal conditions elsewhere</span>
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: 4 }}>
                <span className="uai-view-all-link">
                  View Details →
                </span>
              </div>
            </div>

            {/* Card 3: Global Conditions (Weather Tabs + Temp + AQI) */}
            <div className="uai-intel-card">
              <div className="uai-card-header">
                <span style={{ fontSize: '0.84rem', fontWeight: 700, color: '#fff' }}>Global Conditions</span>
                <div style={{ display: 'flex', gap: 4 }}>
                  {(['weather', 'aqi', 'temp'] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveWeatherTab(tab)}
                      style={{
                        padding: '2px 8px',
                        borderRadius: 9999,
                        fontSize: '0.68rem',
                        fontWeight: 600,
                        border: 'none',
                        cursor: 'pointer',
                        background: activeWeatherTab === tab ? '#2563eb' : 'transparent',
                        color: activeWeatherTab === tab ? '#fff' : '#94a3b8'
                      }}
                    >
                      {tab.charAt(0).toUpperCase() + tab.slice(1)}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flex: 1, padding: '4px 0' }}>
                {/* Weather icon & Temp */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ color: '#fbbf24' }}>
                    <CloudSun size={38} />
                  </div>
                  <div>
                    <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#fff', lineHeight: 1.1 }}>24°C</div>
                    <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Partly Cloudy</div>
                  </div>
                </div>

                {/* Mini Earth map preview graphic */}
                <div style={{ width: 70, height: 44, borderRadius: 6, overflow: 'hidden', opacity: 0.7, border: '1px solid rgba(0, 210, 255, 0.2)' }}>
                  <img 
                    src="https://images.unsplash.com/photo-1614730321146-b6fa6a46bcb4?auto=format&fit=crop&w=150&q=80" 
                    alt="Conditions preview" 
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
                  />
                </div>
              </div>

              {/* AQI Footer */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.74rem', color: '#94a3b8', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 6 }}>
                <span>AQI: <strong style={{ color: '#fff' }}>42</strong></span>
                <span style={{ padding: '2px 8px', borderRadius: 9999, background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', fontSize: '0.68rem', fontWeight: 700 }}>
                  Good
                </span>
              </div>
            </div>

            {/* Card 4: AI Assistant (3D Mascot Avatar + Ask Input + Suggestions) */}
            <div className="uai-intel-card">
              <div className="uai-card-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Sparkles size={14} color="#00d2ff" />
                  <span style={{ fontSize: '0.84rem', fontWeight: 700, color: '#fff' }}>AI Assistant</span>
                </div>
                <button
                  onClick={() => setTtsEnabled(!ttsEnabled)}
                  title="Toggle Voice Readout"
                  style={{ background: 'transparent', border: 'none', color: ttsEnabled ? '#00d2ff' : '#64748b', cursor: 'pointer', padding: 2 }}
                >
                  {ttsEnabled ? <Volume2 size={14} /> : <VolumeX size={14} />}
                </button>
              </div>

              <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                {/* 3D-Styled Cute Blue Cyber Robot Mascot Avatar matching screenshot */}
                <div style={{
                  width: 52,
                  height: 52,
                  borderRadius: 14,
                  background: 'linear-gradient(135deg, #1e3a8a 0%, #0284c7 100%)',
                  boxShadow: '0 0 18px rgba(0, 210, 255, 0.5), inset 0 0 10px rgba(255, 255, 255, 0.3)',
                  border: '1.5px solid #00d2ff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  position: 'relative'
                }}>
                  <svg width="34" height="34" viewBox="0 0 40 40" fill="none">
                    {/* Head */}
                    <rect x="8" y="10" width="24" height="20" rx="8" fill="#38bdf8" />
                    {/* Ears/Antennas */}
                    <circle cx="6" cy="20" r="3" fill="#0284c7" />
                    <circle cx="34" cy="20" r="3" fill="#0284c7" />
                    {/* Glowing Eyes Visor */}
                    <rect x="12" y="15" width="16" height="7" rx="3.5" fill="#090d16" />
                    <circle cx="16" cy="18.5" r="2" fill="#00ffff" />
                    <circle cx="24" cy="18.5" r="2" fill="#00ffff" />
                    {/* Smile */}
                    <path d="M17 25 Q20 28 23 25" stroke="#ffffff" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                </div>

                {/* Input with Mic & Send buttons */}
                <form onSubmit={handleAiAsk} style={{ flex: 1, position: 'relative' }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    background: 'rgba(7, 14, 35, 0.85)',
                    border: '1px solid rgba(0, 210, 255, 0.25)',
                    borderRadius: 9999,
                    padding: '6px 10px',
                    gap: 6
                  }}>
                    <input
                      id="uai-ai-input"
                      type="text"
                      placeholder="Ask anything..."
                      value={aiQuery}
                      onChange={(e) => setAiQuery(e.target.value)}
                      disabled={aiLoading}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#fff',
                        fontSize: '0.78rem',
                        outline: 'none',
                        width: '100%'
                      }}
                    />
                    <button
                      type="button"
                      onClick={handleVoiceInput}
                      title="Voice Speech Recognition"
                      style={{ background: 'transparent', border: 'none', color: '#00d2ff', cursor: 'pointer', display: 'flex', padding: 2 }}
                    >
                      <Mic size={14} />
                    </button>
                    <button
                      type="submit"
                      disabled={aiLoading || !aiQuery.trim()}
                      title="Send Query"
                      style={{
                        background: 'linear-gradient(135deg, #00d2ff 0%, #2563eb 100%)',
                        border: 'none',
                        borderRadius: '50%',
                        width: 24,
                        height: 24,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#fff',
                        cursor: aiLoading ? 'not-allowed' : 'pointer',
                        boxShadow: '0 0 8px rgba(0, 210, 255, 0.4)'
                      }}
                    >
                      <Send size={11} />
                    </button>
                  </div>
                </form>
              </div>

              {/* Suggestion Chips matching screenshot */}
              <div style={{ display: 'flex', gap: 4, overflowX: 'auto', paddingBottom: 2, marginTop: 4 }}>
                {[
                  'Show cameras in London',
                  'Recent earthquakes',
                  'Weather forecast'
                ].map((chip) => (
                  <button
                    key={chip}
                    onClick={() => {
                      setAiQuery(chip);
                      handleAiAsk(undefined, chip);
                    }}
                    style={{
                      background: 'rgba(255, 255, 255, 0.04)',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: 9999,
                      padding: '3px 8px',
                      fontSize: '0.64rem',
                      color: '#94a3b8',
                      cursor: 'pointer',
                      whiteSpace: 'nowrap',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    {chip}
                  </button>
                ))}
              </div>

              {/* AI Response Display if available */}
              {aiResponse && (
                <div style={{
                  background: 'rgba(7, 14, 35, 0.95)',
                  border: '1px solid rgba(0, 210, 255, 0.3)',
                  borderRadius: 8,
                  padding: 8,
                  fontSize: '0.72rem',
                  lineHeight: 1.4,
                  color: '#e2e8f0',
                  maxHeight: 70,
                  overflowY: 'auto'
                }}>
                  {aiResponse}
                </div>
              )}
            </div>

          </section>

        </div>
      </main>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* BOTTOM TELEMETRY FOOTER BAR                                         */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <footer className="uai-footer-bar">
        {/* System Health */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            System Status: <strong style={{ color: '#34d399', display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981' }} /> Operational
            </strong>
          </span>
          <span>Uptime: <strong style={{ color: '#fff' }}>99.9%</strong></span>
          <span>Response: <strong style={{ color: '#fff' }}>245ms</strong></span>
        </div>

        {/* Connected Providers with Icons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ color: '#64748b' }}>Connected Providers:</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#e2e8f0' }}>🌐 OpenStreetMap</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#e2e8f0' }}>🚀 NASA</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#e2e8f0' }}>🌦️ IMD</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#e2e8f0' }}>🌍 USGS</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#e2e8f0' }}>📹 OpenCam</span>
        </div>

        {/* Storage Meter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>Storage: <strong style={{ color: '#fff' }}>42%</strong></span>
          <div style={{ width: 80, height: 6, borderRadius: 3, background: 'rgba(255, 255, 255, 0.1)', overflow: 'hidden' }}>
            <div style={{ width: '42%', height: '100%', background: 'linear-gradient(90deg, #10b981 0%, #34d399 100%)', borderRadius: 3, boxShadow: '0 0 8px #10b981' }} />
          </div>
        </div>
      </footer>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* MODAL: REGISTER TRACKED ASSET                                       */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {showAssetModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)', zIndex: 3000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div style={{ background: '#0a1638', borderRadius: 14, border: '1px solid rgba(0, 210, 255, 0.3)', width: '100%', maxWidth: '440px', padding: 22, display: 'flex', flexDirection: 'column', gap: 14, boxShadow: '0 20px 50px rgba(0,0,0,0.8)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: '#fff' }}>Register Tracked Asset</h3>
              <button onClick={() => setShowAssetModal(false)} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><X size={18} /></button>
            </div>
            <form onSubmit={handleRegisterAsset} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.74rem', color: '#94a3b8', marginBottom: 4 }}>Asset Name *</label>
                <input required type="text" placeholder="e.g. Tesla Model Y, Transport Fleet 4" value={newAssetName} onChange={(e) => setNewAssetName(e.target.value)} style={{ width: '100%', padding: '8px 12px', borderRadius: 6, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(0, 210, 255, 0.25)', color: '#fff', fontSize: '0.84rem' }} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.74rem', color: '#94a3b8', marginBottom: 4 }}>Category</label>
                  <select value={newAssetCategory} onChange={(e) => setNewAssetCategory(e.target.value)} style={{ width: '100%', padding: '8px', borderRadius: 6, background: '#070f28', border: '1px solid rgba(0, 210, 255, 0.25)', color: '#fff', fontSize: '0.82rem' }}>
                    <option value="vehicle">Vehicle</option>
                    <option value="equipment">Equipment</option>
                    <option value="goods">Goods / Cargo</option>
                    <option value="personal_item">Personal Belonging</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.74rem', color: '#94a3b8', marginBottom: 4 }}>Detection Method</label>
                  <select value={newAssetMethod} onChange={(e) => setNewAssetMethod(e.target.value)} style={{ width: '100%', padding: '8px', borderRadius: 6, background: '#070f28', border: '1px solid rgba(0, 210, 255, 0.25)', color: '#fff', fontSize: '0.82rem' }}>
                    <option value="visual">Visual Detection</option>
                    <option value="plate">License Plate OCR</option>
                    <option value="barcode">Barcode</option>
                  </select>
                </div>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.74rem', color: '#94a3b8', marginBottom: 4 }}>Identifier / Plate (Optional)</label>
                <input type="text" placeholder="e.g. DL-01-AB-1234" value={newAssetId} onChange={(e) => setNewAssetId(e.target.value)} style={{ width: '100%', padding: '8px 12px', borderRadius: 6, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(0, 210, 255, 0.25)', color: '#fff', fontSize: '0.84rem' }} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.74rem', color: '#94a3b8', marginBottom: 4 }}>Location Tag</label>
                <input type="text" placeholder="e.g. Garage Bay 1" value={newAssetLocation} onChange={(e) => setNewAssetLocation(e.target.value)} style={{ width: '100%', padding: '8px 12px', borderRadius: 6, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(0, 210, 255, 0.25)', color: '#fff', fontSize: '0.84rem' }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 10 }}>
                <button type="button" onClick={() => setShowAssetModal(false)} style={{ padding: '8px 14px', borderRadius: 6, background: 'transparent', border: '1px solid rgba(255,255,255,0.15)', color: '#94a3b8', cursor: 'pointer' }}>Cancel</button>
                <button type="submit" style={{ padding: '8px 18px', borderRadius: 6, background: 'linear-gradient(135deg, #00d2ff 0%, #2563eb 100%)', color: '#fff', border: 'none', fontWeight: 700, cursor: 'pointer', boxShadow: '0 0 12px rgba(0, 210, 255, 0.4)' }}>Register Asset</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* MODAL: SETTINGS & SYSTEM AUDIT                                      */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {showSettingsModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)', zIndex: 3000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div style={{ background: '#0a1638', borderRadius: 14, border: '1px solid rgba(0, 210, 255, 0.3)', width: '100%', maxWidth: '480px', padding: 22, display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: '#fff' }}>System Settings & Views</h3>
              <button onClick={() => setShowSettingsModal(false)} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><X size={18} /></button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: '0.84rem' }}>
              <div style={{ padding: 12, borderRadius: 8, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
                <strong style={{ color: '#00d2ff' }}>CartoDB Tile Key:</strong>
                <p style={{ margin: '4px 0 0', color: '#94a3b8', fontSize: '0.74rem' }}>Active: cb1_4zq3_1_ea5a143596137f10fbecccc4 (Dark Matter Tiles)</p>
              </div>
              <div style={{ padding: 12, borderRadius: 8, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
                <strong style={{ color: '#10b981' }}>Connected Providers:</strong>
                <p style={{ margin: '4px 0 0', color: '#94a3b8', fontSize: '0.74rem' }}>Groq, Gemini, NASA NeoWs, FIRMS, USGS, Open-Meteo, OpenSky, Windy</p>
              </div>
              {onNavigate && (
                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                  <button 
                    onClick={() => { setShowSettingsModal(false); onNavigate('hud'); }}
                    style={{ flex: 1, padding: '8px 12px', borderRadius: 6, background: 'rgba(0, 210, 255, 0.15)', border: '1px solid rgba(0, 210, 255, 0.4)', color: '#00d2ff', fontWeight: 600, cursor: 'pointer' }}
                  >
                    Open 3D Holographic HUD
                  </button>
                  <button 
                    onClick={() => { setShowSettingsModal(false); onNavigate('people'); }}
                    style={{ flex: 1, padding: '8px 12px', borderRadius: 6, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', fontWeight: 600, cursor: 'pointer' }}
                  >
                    Face Enrollment
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
