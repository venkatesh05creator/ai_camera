import React, { useEffect, useRef, useState } from 'react';
import { 
  Globe, 
  Video, 
  Plane, 
  Flame, 
  PackageSearch, 
  Sparkles, 
  Search, 
  Layers, 
  RefreshCw, 
  Maximize2, 
  Minimize2, 
  MapPin, 
  ExternalLink, 
  Activity, 
  ShieldCheck, 
  AlertTriangle, 
  TrendingUp, 
  Tag, 
  Clock, 
  Plus, 
  Trash2, 
  Mic, 
  Send, 
  Volume2, 
  VolumeX, 
  CheckCircle, 
  Compass, 
  Server,
  X
} from 'lucide-react';
import { api, getAuthToken } from '../services/api';
import { Camera, Alert } from '../types';

declare global {
  interface Window {
    L: any;
  }
}

interface MapMarker {
  id: string;
  layer: 'disaster' | 'camera' | 'transport' | 'weather' | 'asset';
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

export const UnifiedCommandCenter: React.FC = () => {
  // --- Core State ---
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [selectedCamera, setSelectedCamera] = useState<Camera | null>(null);
  const [publicCameras, setPublicCameras] = useState<any[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [markers, setMarkers] = useState<MapMarker[]>([]);
  const [filteredMarkers, setFilteredMarkers] = useState<MapMarker[]>([]);
  const [selectedMarker, setSelectedMarker] = useState<MapMarker | null>(null);
  const [providers, setProviders] = useState<ProviderStatus[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isFullScreenMap, setIsFullScreenMap] = useState(false);
  const [activeTabSection, setActiveTabSection] = useState<'all' | 'cameras' | 'events' | 'assets' | 'analytics'>('all');
  
  // Layer Filters
  const [layerFilters, setLayerFilters] = useState({
    disaster: true,
    transport: true,
    camera: true,
    weather: true,
    asset: true,
  });

  // AI Voice & Chat State
  const [aiQuery, setAiQuery] = useState('');
  const [aiResponse, setAiResponse] = useState<string>('');
  const [aiSpeech, setAiSpeech] = useState<string>('');
  const [aiLoading, setAiLoading] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);

  // Asset Registration Modal
  const [showAssetModal, setShowAssetModal] = useState(false);
  const [newAssetName, setNewAssetName] = useState('');
  const [newAssetCategory, setNewAssetCategory] = useState('vehicle');
  const [newAssetMethod, setNewAssetMethod] = useState('visual');
  const [newAssetId, setNewAssetId] = useState('');
  const [newAssetLocation, setNewAssetLocation] = useState('Garage Bay');

  // Loading & Timestamps
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string>('');

  // Map Reference & Leaflet Instance
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const leafletMapRef = useRef<any>(null);
  const markerLayerGroupRef = useRef<any>(null);

  // ─────────────────────────────────────────────────────────────────────────────
  // 1. Fetch System Data
  // ─────────────────────────────────────────────────────────────────────────────
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

      // 2. Map Markers & Global Feeds
      const markerRes = await fetch(
        `/api/v1/global/map-markers?include_disasters=${layerFilters.disaster}&include_flights=${layerFilters.transport}&include_cameras=${layerFilters.camera}&include_weather=${layerFilters.weather}`,
        { headers }
      );
      if (markerRes.ok) {
        const markerJson = await markerRes.json();
        setMarkers(markerJson.markers || []);
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

      setLastUpdated(new Date().toLocaleTimeString());
    } catch (err) {
      console.warn('Command Center polling sync encountered an error:', err);
    } finally {
      setIsSyncing(false);
    }
  };

  useEffect(() => {
    fetchAllData();
    const interval = setInterval(fetchAllData, 20000); // 20s live sync
    return () => clearInterval(interval);
  }, [layerFilters]);

  // ─────────────────────────────────────────────────────────────────────────────
  // 2. Leaflet Map Initialization & Rendering
  // ─────────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!mapContainerRef.current) return;
    if (!window.L) {
      console.warn('Leaflet script is still loading from CDN...');
      return;
    }

    // Initialize Map if not already created
    if (!leafletMapRef.current) {
      const map = window.L.map(mapContainerRef.current, {
        center: [20.0, 10.0],
        zoom: 2,
        minZoom: 2,
        maxZoom: 18,
        zoomControl: true,
        attributionControl: true,
      });

      // CARTO Dark Matter Tiles with User's Carto API Key
      const cartoKey = 'cb1_4zq3_1_ea5a143596137f10fbecccc4';
      const tileUrl = cartoKey 
        ? `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?api_key=${cartoKey}`
        : 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';

      window.L.tileLayer(tileUrl, {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 19,
      }).addTo(map);

      markerLayerGroupRef.current = window.L.layerGroup().addTo(map);
      leafletMapRef.current = map;
    }

    // Resize map when window or container size changes
    const timer = setTimeout(() => {
      if (leafletMapRef.current) {
        leafletMapRef.current.invalidateSize();
      }
    }, 150);

    return () => clearTimeout(timer);
  }, []);

  // Filter markers by search query
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

  // Update Leaflet Markers whenever filtered markers change
  useEffect(() => {
    if (!leafletMapRef.current || !markerLayerGroupRef.current || !window.L) return;

    markerLayerGroupRef.current.clearLayers();

    filteredMarkers.forEach((m) => {
      if (m.latitude == null || m.longitude == null) return;

      let color = '#6366f1';
      if (m.layer === 'disaster') {
        color = m.severity === 'critical' ? '#ef4444' : m.severity === 'high' ? '#f97316' : '#eab308';
      } else if (m.layer === 'transport') {
        color = '#38bdf8';
      } else if (m.layer === 'camera') {
        color = '#10b981';
      } else if (m.layer === 'weather') {
        color = '#a855f7';
      } else if (m.layer === 'asset') {
        color = '#ec4899';
      }

      // Styled SVG Circle Marker
      const marker = window.L.circleMarker([m.latitude, m.longitude], {
        radius: m.severity === 'critical' ? 9 : 7,
        fillColor: color,
        color: '#ffffff',
        weight: 1.5,
        opacity: 0.9,
        fillOpacity: 0.85,
      });

      marker.bindPopup(`
        <div style="font-family: sans-serif; color: #0f172a; min-width: 180px;">
          <div style="font-weight: 700; font-size: 0.85rem; margin-bottom: 2px;">${m.title}</div>
          <div style="font-size: 0.75rem; color: #475569; margin-bottom: 4px;">${m.subtitle}</div>
          <div style="font-size: 0.7rem; color: #64748b;">Source: ${m.source}</div>
        </div>
      `);

      marker.on('click', () => {
        setSelectedMarker(m);
      });

      marker.addTo(markerLayerGroupRef.current);
    });
  }, [filteredMarkers]);

  // ─────────────────────────────────────────────────────────────────────────────
  // 3. AI Copilot Interaction
  // ─────────────────────────────────────────────────────────────────────────────
  const handleAiAsk = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!aiQuery.trim() || aiLoading) return;

    setAiLoading(true);
    const token = getAuthToken();
    try {
      const res = await fetch('/api/v1/ai/query', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: aiQuery.trim(),
          camera_id: selectedCamera?.id || '0',
          include_frame: true,
        }),
      });

      if (res.ok) {
        const json = await res.json();
        setAiResponse(json.answer || 'Analysis complete.');
        const speech = json.speech_text || json.answer || '';
        setAiSpeech(speech);

        if (ttsEnabled && speech && 'speechSynthesis' in window) {
          window.speechSynthesis.cancel();
          const utterance = new SpeechSynthesisUtterance(speech);
          utterance.rate = 1.05;
          window.speechSynthesis.speak(utterance);
        }
      }
    } catch (err) {
      setAiResponse('Unable to reach the AI engine right now.');
    } finally {
      setAiLoading(false);
      setAiQuery('');
    }
  };

  // ─────────────────────────────────────────────────────────────────────────────
  // 4. Asset Registration
  // ─────────────────────────────────────────────────────────────────────────────
  const handleRegisterAsset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAssetName.trim()) return;

    const token = getAuthToken();
    try {
      const res = await fetch('/api/v1/assets', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: newAssetName.trim(),
          category: newAssetCategory,
          tracking_method: newAssetMethod,
          identifier: newAssetId.trim() || undefined,
          location_label: newAssetLocation.trim() || 'Monitored Perimeter',
        }),
      });

      if (res.ok) {
        setShowAssetModal(false);
        setNewAssetName('');
        setNewAssetId('');
        fetchAllData();
      }
    } catch (err) {
      console.error('Failed to register asset:', err);
    }
  };

  const handleDeleteAsset = async (assetId: string) => {
    if (!confirm('Remove this asset from situational tracking?')) return;
    const token = getAuthToken();
    try {
      await fetch(`/api/v1/assets/${assetId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      fetchAllData();
    } catch (err) {
      console.error('Failed to delete asset:', err);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto', background: 'var(--bg-main)', color: 'var(--text-main)', padding: '16px', gap: '16px' }}>
      
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* A. TOP OMNI-HEADER & GLOBAL TELEMETRY BAR                           */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', background: 'var(--bg-card)', padding: '14px 18px', borderRadius: '14px', border: '1px solid var(--border-subtle)', boxShadow: '0 4px 20px rgba(0,0,0,0.2)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: 'linear-gradient(135deg, #6366f1 0%, #3b82f6 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 16px rgba(99, 102, 241, 0.4)' }}>
            <Globe size={22} color="#ffffff" />
          </div>
          <div>
            <h1 style={{ fontSize: '1.15rem', fontWeight: 800, margin: 0, letterSpacing: '-0.02em', color: 'var(--text-main)' }}>
              Universal AI Command Center
            </h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.74rem', color: 'var(--text-muted)' }}>
              <span style={{ display: 'inline-block', width: '7px', height: '7px', borderRadius: '50%', background: '#10b981', boxShadow: '0 0 8px #10b981' }} />
              Live Operational Grid • Zero-Budget Windows 11 Architecture
            </div>
          </div>
        </div>

        {/* Omnisearch across all telemetry */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '6px 14px', width: '320px' }}>
          <Search size={15} color="#94a3b8" />
          <input
            type="text"
            placeholder="Search cameras, flights, quakes, assets..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ background: 'transparent', border: 'none', color: '#fff', fontSize: '0.84rem', outline: 'none', width: '100%' }}
          />
        </div>

        {/* Sync Status and Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {lastUpdated && (
            <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
              Updated {lastUpdated}
            </span>
          )}
          <button
            onClick={fetchAllData}
            disabled={isSyncing}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '7px 12px', borderRadius: '8px', background: 'rgba(99, 102, 241, 0.15)', border: '1px solid rgba(99, 102, 241, 0.3)', color: '#818cf8', fontWeight: 600, fontSize: '0.78rem', cursor: isSyncing ? 'not-allowed' : 'pointer' }}
          >
            <RefreshCw size={13} className={isSyncing ? 'animate-spin' : ''} />
            {isSyncing ? 'Syncing...' : 'Live Sync'}
          </button>
        </div>
      </header>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* B. OVERVIEW KPI STATISTICS COUNTERS (REAL-TIME METRICS)              */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '10px' }}>
        <div style={{ background: 'var(--bg-card)', padding: '12px 14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#10b981', fontSize: '0.75rem', fontWeight: 600 }}>
            <Video size={14} /> Active Cameras
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-main)', marginTop: '4px' }}>
            {cameras.length + publicCameras.length}
          </div>
        </div>
        <div style={{ background: 'var(--bg-card)', padding: '12px 14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#38bdf8', fontSize: '0.75rem', fontWeight: 600 }}>
            <Plane size={14} /> Aircraft Detected
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#38bdf8', marginTop: '4px' }}>
            {markers.filter((m) => m.layer === 'transport').length}
          </div>
        </div>
        <div style={{ background: 'var(--bg-card)', padding: '12px 14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#ef4444', fontSize: '0.75rem', fontWeight: 600 }}>
            <Flame size={14} /> Active Disasters (USGS)
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#ef4444', marginTop: '4px' }}>
            {markers.filter((m) => m.layer === 'disaster').length}
          </div>
        </div>
        <div style={{ background: 'var(--bg-card)', padding: '12px 14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#ec4899', fontSize: '0.75rem', fontWeight: 600 }}>
            <PackageSearch size={14} /> Tracked Assets
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#ec4899', marginTop: '4px' }}>
            {assets.length}
          </div>
        </div>
        <div style={{ background: 'var(--bg-card)', padding: '12px 14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#a855f7', fontSize: '0.75rem', fontWeight: 600 }}>
            <Server size={14} /> Connected Providers
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#a855f7', marginTop: '4px' }}>
            {providers.length || 6} Online
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* C. MAIN GLOBAL INTERACTIVE MAP (PROMINENT CENTERPIECE)              */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <section style={{ display: 'flex', flexDirection: 'column', gap: '8px', position: 'relative' }}>
        {/* Layer Controls & Map Tools Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Compass size={18} color="#6366f1" />
            <span style={{ fontSize: '0.9rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Real-Time Global Geospatial Radar
            </span>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
              ({filteredMarkers.length} Active Geo-Telemetry Points)
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {/* Layer Toggles */}
            {[
              { key: 'disaster', label: 'Hazards', color: '#ef4444' },
              { key: 'transport', label: 'Aviation', color: '#38bdf8' },
              { key: 'camera', label: 'Cameras', color: '#10b981' },
              { key: 'weather', label: 'Weather', color: '#a855f7' },
              { key: 'asset', label: 'Assets', color: '#ec4899' },
            ].map((layer) => (
              <button
                key={layer.key}
                onClick={() => setLayerFilters((prev: any) => ({ ...prev, [layer.key]: !prev[layer.key] }))}
                style={{
                  background: (layerFilters as any)[layer.key] ? `${layer.color}22` : 'transparent',
                  border: `1px solid ${(layerFilters as any)[layer.key] ? layer.color : 'rgba(255,255,255,0.1)'}`,
                  color: (layerFilters as any)[layer.key] ? layer.color : '#64748b',
                  borderRadius: '6px',
                  padding: '3px 8px',
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                ● {layer.label}
              </button>
            ))}

            {/* Fullscreen Toggle */}
            <button
              onClick={() => {
                setIsFullScreenMap(!isFullScreenMap);
                setTimeout(() => leafletMapRef.current?.invalidateSize(), 200);
              }}
              title="Toggle Fullscreen Radar"
              style={{ padding: '4px 8px', borderRadius: '6px', background: 'rgba(255,255,255,0.06)', border: '1px solid var(--border-subtle)', color: 'var(--text-main)', cursor: 'pointer' }}
            >
              {isFullScreenMap ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            </button>
          </div>
        </div>

        {/* The Leaflet Slippy Map DOM Container */}
        <div
          style={{
            position: 'relative',
            width: '100%',
            height: isFullScreenMap ? '82vh' : '440px',
            borderRadius: '12px',
            overflow: 'hidden',
            border: '1px solid var(--border-subtle)',
            boxShadow: '0 6px 24px rgba(0,0,0,0.3)',
            transition: 'height 0.3s ease',
          }}
        >
          <div ref={mapContainerRef} style={{ width: '100%', height: '100%', background: '#0a0d18' }} />

          {/* Marker Detail Slide-Out Card */}
          {selectedMarker && (
            <div
              style={{
                position: 'absolute',
                top: 12,
                right: 12,
                zIndex: 1000,
                width: '300px',
                background: 'rgba(15, 23, 42, 0.94)',
                backdropFilter: 'blur(10px)',
                borderRadius: '10px',
                border: '1px solid var(--border-subtle)',
                padding: '14px',
                boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '2px 6px', borderRadius: '4px', background: 'rgba(99, 102, 241, 0.2)', color: '#818cf8', textTransform: 'uppercase' }}>
                  {selectedMarker.layer} • {selectedMarker.badge}
                </span>
                <button onClick={() => setSelectedMarker(null)} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
                  <X size={14} />
                </button>
              </div>
              <h4 style={{ margin: '8px 0 4px', fontSize: '0.92rem', color: '#fff' }}>{selectedMarker.title}</h4>
              <p style={{ margin: 0, fontSize: '0.78rem', color: '#94a3b8' }}>{selectedMarker.subtitle}</p>
              <div style={{ marginTop: '8px', fontSize: '0.72rem', color: '#64748b' }}>
                Coords: {selectedMarker.latitude}°N, {selectedMarker.longitude}°E • Source: {selectedMarker.source}
              </div>
              {selectedMarker.url && (
                <a
                  href={selectedMarker.url}
                  target="_blank"
                  rel="noreferrer"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', marginTop: '8px', fontSize: '0.74rem', color: '#818cf8', textDecoration: 'none' }}
                >
                  <ExternalLink size={12} /> Open Official Feed
                </a>
              )}
            </div>
          )}
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* D. MULTI-PANEL SPLIT COMMAND WORKSPACE                               */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 1.2fr) minmax(300px, 1fr)', gap: '16px' }}>
        
        {/* PANEL 1: LIVE SURVEILLANCE & PUBLIC CAMERA MATRIX */}
        <div style={{ background: 'var(--bg-card)', borderRadius: '12px', border: '1px solid var(--border-subtle)', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.92rem', fontWeight: 700 }}>
              <Video size={16} color="#10b981" /> Authorized & Public Camera Feeds
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              {cameras.length} Local • {publicCameras.length} Public
            </span>
          </div>

          {/* Primary Camera Video Player */}
          {selectedCamera ? (
            <div style={{ position: 'relative', width: '100%', height: '260px', background: '#000', borderRadius: '10px', overflow: 'hidden', border: '1px solid var(--border-subtle)' }}>
              <img
                src={`/api/v1/stream/video?camera_id=${selectedCamera.id}`}
                alt={selectedCamera.name}
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                onError={(e) => {
                  (e.target as HTMLImageElement).src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 400 240"><rect width="400" height="240" fill="%230f172a"/><text x="50%" y="50%" fill="%2364748b" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="14">Connecting Live Camera Stream...</text></svg>';
                }}
              />
              <div style={{ position: 'absolute', top: 10, left: 10, background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(4px)', padding: '3px 8px', borderRadius: '6px', fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#ef4444', boxShadow: '0 0 6px #ef4444' }} />
                LIVE • {selectedCamera.name} ({selectedCamera.location_label || 'Default Node'})
              </div>
            </div>
          ) : (
            <div style={{ height: '200px', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.3)', borderRadius: '10px', color: 'var(--text-muted)', fontSize: '0.84rem' }}>
              No primary camera selected
            </div>
          )}

          {/* Camera Selection Switcher Strip */}
          <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '4px' }}>
            {cameras.map((c) => (
              <button
                key={c.id}
                onClick={() => setSelectedCamera(c)}
                style={{
                  flexShrink: 0,
                  padding: '6px 12px',
                  borderRadius: '8px',
                  background: selectedCamera?.id === c.id ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255,255,255,0.04)',
                  border: `1px solid ${selectedCamera?.id === c.id ? '#10b981' : 'transparent'}`,
                  color: selectedCamera?.id === c.id ? '#10b981' : 'var(--text-muted)',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                📹 {c.name}
              </button>
            ))}
            {publicCameras.slice(0, 4).map((pub) => (
              <a
                key={pub.id}
                href={pub.stream_url}
                target="_blank"
                rel="noreferrer"
                style={{
                  flexShrink: 0,
                  padding: '6px 12px',
                  borderRadius: '8px',
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-muted)',
                  fontSize: '0.75rem',
                  textDecoration: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                🌐 {pub.name.slice(0, 16)}...
              </a>
            ))}
          </div>
        </div>

        {/* PANEL 2: LIVE DISASTER & FLIGHT EVENT STREAM */}
        <div style={{ background: 'var(--bg-card)', borderRadius: '12px', border: '1px solid var(--border-subtle)', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.92rem', fontWeight: 700 }}>
              <Activity size={16} color="#ef4444" /> Live Hazards & Multi-Source Events
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              Real-time USGS & ADS-B
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '310px', overflowY: 'auto' }}>
            {markers.slice(0, 8).map((evt) => (
              <div
                key={evt.id}
                onClick={() => {
                  setSelectedMarker(evt);
                  if (evt.latitude && evt.longitude && leafletMapRef.current) {
                    leafletMapRef.current.setView([evt.latitude, evt.longitude], 6);
                  }
                }}
                style={{
                  padding: '10px 12px',
                  borderRadius: '8px',
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid var(--border-subtle)',
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-main)' }}>
                    {evt.title}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    {evt.subtitle} • {evt.source}
                  </div>
                </div>
                <span
                  style={{
                    padding: '2px 6px',
                    borderRadius: '4px',
                    fontSize: '0.68rem',
                    fontWeight: 700,
                    background: evt.layer === 'disaster' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(56, 189, 248, 0.2)',
                    color: evt.layer === 'disaster' ? '#ef4444' : '#38bdf8',
                  }}
                >
                  {evt.badge}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* E. UNIVERSAL ASSET TRACKING STRIP                                    */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div style={{ background: 'var(--bg-card)', borderRadius: '12px', border: '1px solid var(--border-subtle)', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.92rem', fontWeight: 700 }}>
            <PackageSearch size={16} color="#ec4899" /> Registered Assets & Situational Presence
          </div>
          <button
            onClick={() => setShowAssetModal(true)}
            style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '5px 10px', borderRadius: '6px', background: 'rgba(236, 72, 153, 0.15)', border: '1px solid rgba(236, 72, 153, 0.3)', color: '#ec4899', fontSize: '0.74rem', fontWeight: 600, cursor: 'pointer' }}
          >
            <Plus size={13} /> Add Tracked Asset
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '10px' }}>
          {assets.map((ast) => (
            <div
              key={ast.id}
              style={{
                padding: '10px 12px',
                borderRadius: '8px',
                background: 'rgba(255,255,255,0.02)',
                border: '1px solid var(--border-subtle)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <div style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--text-main)' }}>{ast.name}</div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  {ast.category} • Tag: {ast.identifier || 'Visual'} • {ast.location_label}
                </div>
              </div>
              <button
                onClick={() => handleDeleteAsset(ast.id)}
                title="Remove asset"
                style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', padding: '4px' }}
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
          {assets.length === 0 && (
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', gridColumn: '1 / -1' }}>
              No tracked assets registered yet. Click "+ Add Tracked Asset" to monitor vehicles or equipment.
            </div>
          )}
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* F. UNIFIED DOCKED AI COPILOT & VOICE ASSISTANT                       */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div style={{ background: 'linear-gradient(180deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%)', borderRadius: '14px', border: '1px solid rgba(99, 102, 241, 0.3)', padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles size={16} color="#818cf8" />
            <span style={{ fontSize: '0.88rem', fontWeight: 700, color: '#fff' }}>Unified Intelligence Copilot</span>
            <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Map, Camera & OSINT Cross-Engine Reasoning</span>
          </div>

          <button
            onClick={() => setTtsEnabled(!ttsEnabled)}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'transparent', border: 'none', color: ttsEnabled ? '#818cf8' : '#64748b', cursor: 'pointer', fontSize: '0.76rem' }}
          >
            {ttsEnabled ? <Volume2 size={14} /> : <VolumeX size={14} />}
            Spoken Audio {ttsEnabled ? 'ON' : 'OFF'}
          </button>
        </div>

        {/* AI Answer Card */}
        {aiResponse && (
          <div style={{ background: 'rgba(15, 23, 42, 0.8)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '10px', padding: '12px', fontSize: '0.84rem', lineHeight: 1.5, color: '#e2e8f0', whiteSpace: 'pre-wrap' }}>
            {aiResponse}
          </div>
        )}

        {/* AI Input Form */}
        <form onSubmit={handleAiAsk} style={{ display: 'flex', gap: '8px' }}>
          <input
            type="text"
            placeholder="Ask about visible cameras, recent quakes, flights overhead, or locate an asset..."
            value={aiQuery}
            onChange={(e) => setAiQuery(e.target.value)}
            disabled={aiLoading}
            style={{ flex: 1, padding: '10px 14px', borderRadius: '10px', background: 'rgba(255,255,255,0.06)', border: '1px solid var(--border-subtle)', color: '#fff', fontSize: '0.85rem', outline: 'none' }}
          />
          <button
            type="submit"
            disabled={aiLoading || !aiQuery.trim()}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '10px 18px', borderRadius: '10px', background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)', color: '#fff', border: 'none', fontWeight: 600, fontSize: '0.84rem', cursor: aiLoading ? 'not-allowed' : 'pointer' }}
          >
            <Send size={14} /> {aiLoading ? 'Thinking...' : 'Analyze'}
          </button>
        </form>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* G. BOTTOM DATA-SOURCE HEALTH & SYSTEM TELEMETRY STRIP                */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <footer style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px', padding: '10px 14px', background: 'var(--bg-card)', borderRadius: '10px', border: '1px solid var(--border-subtle)', fontSize: '0.74rem', color: 'var(--text-muted)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span>Connected Sources:</span>
          {providers.map((p) => (
            <span key={p.name} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981' }} />
              {p.name}
            </span>
          ))}
        </div>
        <div>
          Universal AI Single-Page Command Center • Strict ₹0 Budget Standard
        </div>
      </footer>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* MODAL: REGISTER TRACKED ASSET                                       */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {showAssetModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(6px)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div style={{ background: 'var(--bg-card)', borderRadius: '14px', border: '1px solid var(--border-subtle)', width: '100%', maxWidth: '420px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700 }}>Register Tracked Asset</h3>
              <button onClick={() => setShowAssetModal(false)} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>✕</button>
            </div>
            <form onSubmit={handleRegisterAsset} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.76rem', color: '#94a3b8', marginBottom: '4px' }}>Asset Name *</label>
                <input required type="text" placeholder="e.g. Tesla Model Y, Dell Workstation" value={newAssetName} onChange={(e) => setNewAssetName(e.target.value)} style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-subtle)', color: '#fff', fontSize: '0.84rem' }} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.76rem', color: '#94a3b8', marginBottom: '4px' }}>Category</label>
                  <select value={newAssetCategory} onChange={(e) => setNewAssetCategory(e.target.value)} style={{ width: '100%', padding: '8px', borderRadius: '6px', background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', color: '#fff', fontSize: '0.82rem' }}>
                    <option value="vehicle">Vehicle</option>
                    <option value="equipment">Equipment</option>
                    <option value="goods">Goods / Package</option>
                    <option value="personal_item">Personal Belonging</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.76rem', color: '#94a3b8', marginBottom: '4px' }}>Method</label>
                  <select value={newAssetMethod} onChange={(e) => setNewAssetMethod(e.target.value)} style={{ width: '100%', padding: '8px', borderRadius: '6px', background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', color: '#fff', fontSize: '0.82rem' }}>
                    <option value="visual">Visual Detection</option>
                    <option value="plate">Plate OCR</option>
                    <option value="barcode">Barcode</option>
                  </select>
                </div>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.76rem', color: '#94a3b8', marginBottom: '4px' }}>Tag / Identifier (Optional)</label>
                <input type="text" placeholder="e.g. License plate or serial" value={newAssetId} onChange={(e) => setNewAssetId(e.target.value)} style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-subtle)', color: '#fff', fontSize: '0.84rem' }} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.76rem', color: '#94a3b8', marginBottom: '4px' }}>Location Tag</label>
                <input type="text" placeholder="e.g. Garage Bay 1" value={newAssetLocation} onChange={(e) => setNewAssetLocation(e.target.value)} style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-subtle)', color: '#fff', fontSize: '0.84rem' }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '8px' }}>
                <button type="button" onClick={() => setShowAssetModal(false)} style={{ padding: '8px 12px', borderRadius: '6px', background: 'transparent', border: '1px solid var(--border-subtle)', color: '#94a3b8', cursor: 'pointer' }}>Cancel</button>
                <button type="submit" style={{ padding: '8px 16px', borderRadius: '6px', background: '#6366f1', color: '#fff', border: 'none', fontWeight: 600, cursor: 'pointer' }}>Register Asset</button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};

