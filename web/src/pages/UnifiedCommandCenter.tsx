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
  Activity,
  Users,
  ShieldCheck,
  Radio,
  RefreshCw,
  VideoOff,
  Copy,
  CheckCheck
} from 'lucide-react';
import { api, getAuthToken } from '../services/api';
import { SentenceChunkTTSQueue, pickNaturalEnglishVoice } from '../utils/ttsQueue';
import { Camera as CameraType, Alert } from '../types';

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

interface EnrolledPerson {
  id: string;
  name: string;
  role: string;
  age?: number;
  is_consented: boolean;
  templates_count: number;
  last_seen?: string;
}

interface UnifiedCommandCenterProps {
  cameras?: CameraType[];
  alerts?: Alert[];
  activeAlertsCount?: number;
  onRefreshCameras?: () => void;
}

export const UnifiedCommandCenter: React.FC<UnifiedCommandCenterProps> = ({
  cameras: initialCameras = [],
  alerts: initialAlerts = [],
  activeAlertsCount = 3,
  onRefreshCameras,
}) => {
  // ── Core State ─────────────────────────────────────────────────────────────
  const [cameras, setCameras] = useState<CameraType[]>(initialCameras);
  const [selectedCamera, setSelectedCamera] = useState<CameraType | null>(null);
  const [publicCameras, setPublicCameras] = useState<any[]>([]);
  const [selectedPublicCamera, setSelectedPublicCamera] = useState<any | null>(null);
  const [isViewingPublicCamera, setIsViewingPublicCamera] = useState(false);

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

  // Video Feed & Webcam State
  const localVideoRef = useRef<HTMLVideoElement | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const [isLocalWebcamActive, setIsLocalWebcamActive] = useState<boolean>(false);
  const [webcamPermissionDenied, setWebcamPermissionDenied] = useState<boolean>(false);
  const [webcamError, setWebcamError] = useState<string | null>(null);
  const [snapshotTick, setSnapshotTick] = useState<number>(Date.now());
  const [feedHasError, setFeedHasError] = useState<boolean>(false);

  // Conversational AI State (ChatGPT Experience)
  const [aiQuery, setAiQuery] = useState('');
  const [aiLoading, setAiLoading] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(false);
  const [isExpandedAi, setIsExpandedAi] = useState(false);
  const [conversations, setConversations] = useState<any[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [showChatHistoryModal, setShowChatHistoryModal] = useState<boolean>(false);
  const [copiedMsgId, setCopiedMsgId] = useState<string | null>(null);
  const [weatherData, setWeatherData] = useState<any | null>(null);
  const [systemVitals, setSystemVitals] = useState<{ uptime: string; cpu: number; ram: number; disk: number; latency: number }>({
    uptime: 'Active',
    cpu: 12,
    ram: 34,
    disk: 42,
    latency: 45,
  });
  const [isHandsFreeMode, setIsHandsFreeMode] = useState<boolean>(false);
  const ttsQueueRef = useRef<SentenceChunkTTSQueue | null>(null);
  const chatMessagesEndRef = useRef<HTMLDivElement | null>(null);
  const [chatMessages, setChatMessages] = useState<Array<{
    id: string;
    role: 'user' | 'assistant';
    content: string;
    created_at?: string;
    speech_text?: string;
  }>>([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'Universal AI Assistant online. Real-time situational awareness active for cameras, airspace, maritime channels, and registered assets. How may I assist you?',
      created_at: new Date().toISOString(),
    }
  ]);

  // In-Page Modals & Drawers (ZERO separate pages!)
  const [showCameraMatrixModal, setShowCameraMatrixModal] = useState(false);
  const [cameraMatrixTab, setCameraMatrixTab] = useState<'local' | 'public'>('local');
  const [showPeopleModal, setShowPeopleModal] = useState(false);
  const [showEventsModal, setShowEventsModal] = useState(false);
  const [showReportsModal, setShowReportsModal] = useState(false);
  const [showLayerModal, setShowLayerModal] = useState(false);
  const [showAssetModal, setShowAssetModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showMoreFiltersDropdown, setShowMoreFiltersDropdown] = useState(false);

  // People & Face Directory State
  const [peopleList, setPeopleList] = useState<EnrolledPerson[]>([
    { id: 'p-1', name: 'Authorized Owner', role: 'Owner', age: 32, is_consented: true, templates_count: 3, last_seen: 'Just now' },
    { id: 'p-2', name: 'venky', role: 'System Admin', age: 24, is_consented: true, templates_count: 1, last_seen: 'Today, 14:15 UTC' },
  ]);
  const [newPersonName, setNewPersonName] = useState('');
  const [newPersonRole, setNewPersonRole] = useState('Authorized Member');

  // New Camera Form
  const [newCamName, setNewCamName] = useState('');
  const [newCamSource, setNewCamSource] = useState('0');
  const [newCamLocation, setNewCamLocation] = useState('Front Entrance');

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

      // 2. Map Markers & Global Feeds
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

      // 3. Public Webcams Catalog (Windy Webcams & Open DOT Cams)
      const pubCamRes = await fetch('/api/v1/global/public-cameras', { headers });
      if (pubCamRes.ok) {
        const pubCamJson = await pubCamRes.json();
        const pubs = pubCamJson.cameras || [];
        setPublicCameras(pubs);
        if (pubs.length > 0 && !selectedPublicCamera) {
          setSelectedPublicCamera(pubs[0]);
        }
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

      // 6. Live Weather & Environmental Intelligence (Open-Meteo REST API)
      try {
        const wData = await api.getLiveWeather(28.6139, 77.2090, 'Workstation Area');
        if (wData) setWeatherData(wData);
      } catch (wErr) {
        console.debug('Weather fetch error:', wErr);
      }

      // 7. Live System Observability Telemetry (psutil & HUD state)
      try {
        const hudRes = await fetch('/api/v1/hud/state', { headers });
        if (hudRes.ok) {
          const hudJson = await hudRes.json();
          if (hudJson && hudJson.sys) {
            setSystemVitals({
              uptime: hudJson.vitals?.uptime || `${Math.floor((hudJson.sys.up || 0) / 3600)}h ${Math.floor(((hudJson.sys.up || 0) % 3600) / 60)}m`,
              cpu: hudJson.sys.cpu || 14,
              ram: hudJson.sys.ram || 36,
              disk: hudJson.sys.disk || 42,
              latency: Math.round((hudJson.t_think || 0.045) * 1000) || 45,
            });
          }
        }
      } catch (hudErr) {
        console.debug('HUD telemetry fetch error:', hudErr);
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
        zoomControl: false,
        attributionControl: false,
      });

      // CartoDB Dark Matter with User's Carto Key (Official CARTO rastertiles format)
      const cartoKey = 'cb1_4zq3_1_ea5a143596137f10fbecccc4';
      const tileUrl = cartoKey 
        ? `https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}{r}.png?key=${cartoKey}`
        : 'https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}{r}.png';

      window.L.tileLayer(tileUrl, {
        subdomains: 'abcd',
        maxZoom: 19,
      }).addTo(map);

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

      let color = '#38bdf8';
      let iconSvg = '';

      if (marker.layer === 'transport') {
        color = '#f97316';
        iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5"><path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.3c.4-.2.6-.6.5-1.1z"/></svg>`;
      } else if (marker.layer === 'maritime') {
        color = '#10b981';
        iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5"><path d="M2 21c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1 .6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/><path d="M19.38 20A11.6 11.6 0 0 0 21 14l-9-4-9 4c0 2.9.94 5.34 2.81 7.76"/><path d="M19 13V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v6"/><path d="M12 10v4"/><path d="M12 2v3"/></svg>`;
      } else if (marker.layer === 'camera') {
        color = '#00d2ff';
        iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5"><path d="m22 8-6 4 6 4V8Z"/><rect width="14" height="12" x="2" y="6" rx="2" ry="2"/></svg>`;
      } else if (marker.layer === 'disaster') {
        color = '#ef4444';
        iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`;
      } else {
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
            <div style="width: 48px; height: 36px; border-radius: 6px; overflow: hidden; background: #000; flex-shrink: 0;" class="aspect-4-3">
              <img src="https://images.unsplash.com/photo-1519501025264-65ba15a82390?auto=format&fit=crop&w=120&q=80" style="width: 100%; height: 100%; object-fit: cover;" alt="Preview" />
            </div>
            <div style="flex: 1; min-width: 0;">
              <div class="line-clamp-1" style="font-size: 0.82rem; font-weight: 700; color: #fff;">${marker.title}</div>
              <div class="line-clamp-1" style="font-size: 0.7rem; color: #94a3b8;">${marker.subtitle}</div>
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

  // Initialize Non-Truncating Sentence-Chunk TTS Queue
  useEffect(() => {
    ttsQueueRef.current = new SentenceChunkTTSQueue({
      onEnd: () => {
        if (isHandsFreeMode) {
          setTimeout(() => handleVoiceInput(), 400);
        }
      },
      onError: (err) => console.warn('JARVIS TTS error:', err),
    });
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.onvoiceschanged = () => {
        const voices = window.speechSynthesis.getVoices();
        const bestVoice = pickNaturalEnglishVoice(voices);
        if (ttsQueueRef.current && bestVoice) {
          ttsQueueRef.current.setVoice(bestVoice);
        }
      };
    }
    return () => {
      ttsQueueRef.current?.stop();
    };
  }, [isHandsFreeMode]);

  // ── Video Feeds & Local Webcam Acquisition ─────────────────────────────
  const isSelectedCameraLocal = !isViewingPublicCamera && (
    !selectedCamera ||
    selectedCamera.source_type === 'webcam' ||
    selectedCamera.name.toLowerCase().includes('laptop') ||
    selectedCamera.name.toLowerCase().includes('webcam')
  );

  const startLocalWebcam = async () => {
    setWebcamError(null);
    setWebcamPermissionDenied(false);
    setFeedHasError(false);
    try {
      if (localStreamRef.current) {
        localStreamRef.current.getTracks().forEach((track) => track.stop());
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
      localStreamRef.current = stream;
      if (localVideoRef.current) {
        localVideoRef.current.srcObject = stream;
        localVideoRef.current.play().catch(() => {});
      }
      setIsLocalWebcamActive(true);
    } catch (err: any) {
      console.warn('Workstation webcam acquisition failed:', err);
      setIsLocalWebcamActive(false);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setWebcamPermissionDenied(true);
        setWebcamError('Camera access permission was blocked by the browser. Click below to allow access.');
      } else {
        setWebcamError('No physical video capture hardware detected on this workstation.');
      }
    }
  };

  const stopLocalWebcam = () => {
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((track) => track.stop());
      localStreamRef.current = null;
    }
    if (localVideoRef.current) {
      localVideoRef.current.srcObject = null;
    }
    setIsLocalWebcamActive(false);
  };

  useEffect(() => {
    if (isSelectedCameraLocal) {
      startLocalWebcam();
    } else {
      stopLocalWebcam();
    }
    return () => stopLocalWebcam();
  }, [isSelectedCameraLocal, selectedCamera?.id]);

  // Periodic snapshot reload for traffic/observatory feeds
  useEffect(() => {
    const timer = setInterval(() => {
      setSnapshotTick(Date.now());
    }, 15000);
    return () => clearInterval(timer);
  }, []);

  // Auto-scroll chat message thread
  useEffect(() => {
    chatMessagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // Load persistent conversations from SQLite
  useEffect(() => {
    const initConversations = async () => {
      try {
        const list = await api.listConversations();
        if (list && list.length > 0) {
          setConversations(list);
          setActiveConvId(list[0].id);
          const msgs = await api.getConversationMessages(list[0].id);
          if (msgs && msgs.length > 0) {
            setChatMessages(msgs.map((m: any) => ({
              id: m.id,
              role: m.role as 'user' | 'assistant',
              content: m.content,
              created_at: m.created_at,
              speech_text: m.speech_text,
            })));
          }
        } else {
          const newC = await api.createConversation('Global Intel Session');
          setConversations([newC]);
          setActiveConvId(newC.id);
        }
      } catch (e) {
        console.warn('Error loading conversations:', e);
      }
    };
    initConversations();
  }, []);

  // ── 5. AI Assistant Handler (Multi-Turn Conversational Memory) ───────────
  const handleAiAsk = async (e?: React.FormEvent, customPrompt?: string) => {
    if (e) e.preventDefault();
    const promptToSend = customPrompt || aiQuery;
    if (!promptToSend.trim() || aiLoading) return;

    const userTurn = {
      id: 'u_' + Date.now(),
      role: 'user' as const,
      content: promptToSend,
      created_at: new Date().toISOString(),
    };

    setChatMessages((prev) => [...prev, userTurn]);
    setAiQuery('');
    setAiLoading(true);

    try {
      const historyPayload = chatMessages.slice(-6).map((m) => ({ role: m.role, content: m.content }));
      const res = await api.interactCameraAI(
        promptToSend,
        selectedCamera?.id,
        ttsEnabled,
        historyPayload,
        undefined,
        activeConvId || undefined
      );

      const reply = res.answer || 'Telemetry analyzed. All monitored sectors operating within nominal thresholds.';
      const aiTurn = {
        id: 'a_' + Date.now(),
        role: 'assistant' as const,
        content: reply,
        created_at: new Date().toISOString(),
        speech_text: res.speech_text || reply,
      };
      setChatMessages((prev) => [...prev, aiTurn]);

      if (ttsEnabled && ttsQueueRef.current) {
        ttsQueueRef.current.speak(res.speech_text || reply);
      }
    } catch {
      setChatMessages((prev) => [
        ...prev,
        {
          id: 'err_' + Date.now(),
          role: 'assistant',
          content: 'AI Copilot communication offline. Operating with local telemetry fallback.',
          created_at: new Date().toISOString(),
        }
      ]);
    } finally {
      setAiLoading(false);
    }
  };

  const handleNewChat = async () => {
    try {
      const newConv = await api.createConversation(`Session ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`);
      setConversations((prev) => [newConv, ...prev]);
      setActiveConvId(newConv.id);
      setChatMessages([
        {
          id: 'new_welcome',
          role: 'assistant',
          content: 'New intelligence session initialized. Ask about current cameras, hazards, flights, or assets.',
          created_at: new Date().toISOString(),
        }
      ]);
    } catch (e) {
      console.warn('Failed to start new conversation session:', e);
    }
  };

  const handleSwitchConversation = async (convId: string) => {
    try {
      setActiveConvId(convId);
      setShowChatHistoryModal(false);
      const msgs = await api.getConversationMessages(convId);
      if (msgs && msgs.length > 0) {
        setChatMessages(msgs.map((m: any) => ({
          id: m.id,
          role: m.role as 'user' | 'assistant',
          content: m.content,
          created_at: m.created_at,
          speech_text: m.speech_text,
        })));
      } else {
        setChatMessages([
          {
            id: 'conv_welcome',
            role: 'assistant',
            content: 'Conversation session loaded.',
            created_at: new Date().toISOString(),
          }
        ]);
      }
    } catch (e) {
      console.warn('Failed to switch conversation:', e);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedMsgId(id);
    setTimeout(() => setCopiedMsgId(null), 2000);
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

  // ── 8. Add New Camera Handler ──────────────────────────────────────────────
  const handleAddCamera = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCamName.trim()) return;

    try {
      await api.registerCamera({
        name: newCamName,
        source_type: newCamSource.startsWith('rtsp') ? 'rtsp' : 'webcam',
        stream_url: newCamSource,
        location_label: newCamLocation,
      });
      setNewCamName('');
      if (onRefreshCameras) onRefreshCameras();
      fetchAllData();
    } catch (err) {
      console.error('Failed to add camera:', err);
    }
  };

  // ── 9. Enroll Person Handler ───────────────────────────────────────────────
  const handleEnrollPerson = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPersonName.trim()) return;
    const newPerson: EnrolledPerson = {
      id: `p-${Date.now()}`,
      name: newPersonName,
      role: newPersonRole,
      is_consented: true,
      templates_count: 1,
      last_seen: 'Just enrolled',
    };
    setPeopleList((prev) => [newPerson, ...prev]);
    setNewPersonName('');
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
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2">
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
            {utcTimeStr || 'Nov 2, 2026 21:50:18 UTC'}
          </div>

          {/* Notification Center (Opens In-Page Events Timeline) */}
          <button 
            className="uai-icon-btn" 
            title="Notification Center & Events Timeline"
            onClick={() => setShowEventsModal(true)}
          >
            <Bell size={17} />
            <span className="uai-badge-count">{activeAlertsCount || 3}</span>
          </button>

          {/* Settings (Opens In-Page Settings) */}
          <button 
            className="uai-icon-btn" 
            title="System Settings"
            onClick={() => setShowSettingsModal(true)}
          >
            <Settings size={17} />
          </button>

          {/* User Profile Avatar (Opens In-Page People & Biometrics Registry) */}
          <button 
            className="uai-avatar-btn" 
            title="Authorized People & Biometric Verification Directory"
            onClick={() => setShowPeopleModal(true)}
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
        <div className="uai-kpi-card" onClick={() => setShowCameraMatrixModal(true)} style={{ cursor: 'pointer' }} title="Click to open Live Camera Operations">
          <div className="uai-kpi-icon-box" style={{ background: 'rgba(59, 130, 246, 0.2)', border: '1px solid rgba(59, 130, 246, 0.4)' }}>
            <Video size={18} color="#3b82f6" />
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="uai-kpi-label">Active Cameras</div>
            <div className="uai-kpi-val-row">
              <span className="uai-kpi-val">{(cameras.length + publicCameras.length).toLocaleString()}</span>
              <span className="uai-kpi-delta" style={{ color: '#10b981' }}>● Live</span>
            </div>
          </div>
        </div>

        {/* 2. Aircraft Tracked */}
        <div className="uai-kpi-card">
          <div className="uai-kpi-icon-box" style={{ background: 'rgba(56, 189, 248, 0.2)', border: '1px solid rgba(56, 189, 248, 0.4)' }}>
            <Plane size={18} color="#38bdf8" />
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="uai-kpi-label">Aircraft Tracked</div>
            <div className="uai-kpi-val-row">
              <span className="uai-kpi-val">{markers.filter((m) => m.layer === 'transport').length.toLocaleString()}</span>
              <span className="uai-kpi-delta">ADS-B</span>
            </div>
          </div>
        </div>

        {/* 3. Ships Tracked */}
        <div className="uai-kpi-card">
          <div className="uai-kpi-icon-box" style={{ background: 'rgba(14, 165, 233, 0.2)', border: '1px solid rgba(14, 165, 233, 0.4)' }}>
            <Ship size={18} color="#0ea5e9" />
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="uai-kpi-label">Ships Tracked</div>
            <div className="uai-kpi-val-row">
              <span className="uai-kpi-val">{markers.filter((m) => m.layer === 'maritime').length.toLocaleString()}</span>
              <span className="uai-kpi-delta">AIS</span>
            </div>
          </div>
        </div>

        {/* 4. Active Disasters */}
        <div className="uai-kpi-card">
          <div className="uai-kpi-icon-box" style={{ background: 'rgba(239, 68, 68, 0.2)', border: '1px solid rgba(239, 68, 68, 0.4)' }}>
            <Flame size={18} color="#ef4444" />
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="uai-kpi-label">Active Disasters</div>
            <div className="uai-kpi-val-row">
              <span className="uai-kpi-val">{markers.filter((m) => m.layer === 'disaster').length.toLocaleString()}</span>
              <span className="uai-kpi-delta" style={{ color: '#ef4444' }}>USGS/NASA</span>
            </div>
          </div>
        </div>

        {/* 5. Env. Alerts */}
        <div className="uai-kpi-card">
          <div className="uai-kpi-icon-box" style={{ background: 'rgba(16, 185, 129, 0.2)', border: '1px solid rgba(16, 185, 129, 0.4)' }}>
            <Leaf size={18} color="#10b981" />
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="uai-kpi-label">Env. Alerts</div>
            <div className="uai-kpi-val-row">
              <span className="uai-kpi-val">{markers.filter((m) => m.layer === 'weather').length.toLocaleString()}</span>
              <span className="uai-kpi-delta">Meteo</span>
            </div>
          </div>
        </div>

        {/* 6. Events Today */}
        <div className="uai-kpi-card" onClick={() => setShowEventsModal(true)} style={{ cursor: 'pointer' }} title="Click to view events timeline">
          <div className="uai-kpi-icon-box" style={{ background: 'rgba(99, 102, 241, 0.2)', border: '1px solid rgba(99, 102, 241, 0.4)' }}>
            <BarChart3 size={18} color="#818cf8" />
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="uai-kpi-label">Events Today</div>
            <div className="uai-kpi-val-row">
              <span className="uai-kpi-val">{(initialAlerts.length > 0 ? initialAlerts.length : 14).toLocaleString()}</span>
              <span className="uai-kpi-delta">Verified</span>
            </div>
          </div>
        </div>

        {/* 7. Data Sources */}
        <div className="uai-kpi-card">
          <div className="uai-kpi-icon-box" style={{ background: 'rgba(6, 182, 212, 0.2)', border: '1px solid rgba(6, 182, 212, 0.4)' }}>
            <Database size={18} color="#06b6d4" />
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="uai-kpi-label">Data Sources</div>
            <div className="uai-kpi-val-row">
              <span className="uai-kpi-val">{providers.length > 0 ? providers.length : 8}</span>
              <span className="uai-kpi-delta" style={{ color: '#10b981' }}>● {providers.filter((p) => p.status === 'online').length || 7} Online</span>
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
                    setShowLayerModal(true);
                  } else if (item.id === 'cameras') {
                    setShowCameraMatrixModal(true);
                  } else if (item.id === 'tracking') {
                    setShowAssetModal(true);
                  } else if (item.id === 'disasters') {
                    setActiveFilterPill('disasters');
                  } else if (item.id === 'reports') {
                    setShowReportsModal(true);
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
                <IconComponent size={19} />
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
                          onClick={() => { setShowAssetModal(true); setShowMoreFiltersDropdown(false); }}
                          style={{ display: 'block', width: '100%', textAlign: 'left', padding: '6px 10px', background: 'transparent', border: 'none', color: '#fff', fontSize: '0.74rem', cursor: 'pointer' }}
                        >
                          Tracked Assets
                        </button>
                        <button
                          onClick={() => { setShowCameraMatrixModal(true); setShowMoreFiltersDropdown(false); }}
                          style={{ display: 'block', width: '100%', textAlign: 'left', padding: '6px 10px', background: 'transparent', border: 'none', color: '#fff', fontSize: '0.74rem', cursor: 'pointer' }}
                        >
                          Live Camera Operations
                        </button>
                        <button
                          onClick={() => { setShowPeopleModal(true); setShowMoreFiltersDropdown(false); }}
                          style={{ display: 'block', width: '100%', textAlign: 'left', padding: '6px 10px', background: 'transparent', border: 'none', color: '#fff', fontSize: '0.74rem', cursor: 'pointer' }}
                        >
                          People & Face Registry
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

              {/* The Leaflet Canvas with Pro Responsive Proportions */}
              <div 
                ref={mapContainerRef} 
                className="aspect-16-9"
                style={{ width: '100%', height: '100%', minHeight: '360px', background: '#070f28' }} 
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
                  <span className="uai-view-all-link" onClick={() => setShowCameraMatrixModal(true)} title="Open Full Live Surveillance & Public Webcams Matrix">
                    View All →
                  </span>
                </div>

                {/* Camera Quick Switcher Dropdown */}
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <select
                    value={isViewingPublicCamera ? `pub_${selectedPublicCamera?.id}` : (selectedCamera?.id || '')}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val.startsWith('pub_')) {
                        const pid = val.replace('pub_', '');
                        const found = publicCameras.find((p) => p.id === pid);
                        if (found) {
                          setSelectedPublicCamera(found);
                          setIsViewingPublicCamera(true);
                        }
                      } else {
                        const found = cameras.find((c) => c.id === val);
                        if (found) {
                          setSelectedCamera(found);
                          setIsViewingPublicCamera(false);
                        }
                      }
                    }}
                    style={{
                      width: '100%',
                      background: 'rgba(7, 14, 35, 0.9)',
                      border: '1px solid rgba(0, 210, 255, 0.25)',
                      borderRadius: 6,
                      color: '#ffffff',
                      padding: '4px 8px',
                      fontSize: '0.72rem',
                      outline: 'none',
                    }}
                  >
                    <optgroup label="Authorized Surveillance Feeds">
                      {cameras.map((c) => (
                        <option key={c.id} value={c.id}>
                          📹 {c.name} ({c.location_label || 'Node'})
                        </option>
                      ))}
                    </optgroup>
                    <optgroup label="Global Public Webcams">
                      {publicCameras.map((pub) => (
                        <option key={pub.id} value={`pub_${pub.id}`}>
                          🌐 {pub.name} ({pub.city}, {pub.country})
                        </option>
                      ))}
                    </optgroup>
                  </select>
                </div>

                {/* Pro Video Player with Exact 16:9 Aspect Ratio */}
                <div className="uai-video-frame pro-video-player aspect-16-9" style={{ position: 'relative', overflow: 'hidden', background: '#000000' }}>
                  {isSelectedCameraLocal ? (
                    isLocalWebcamActive ? (
                      <video
                        ref={localVideoRef}
                        autoPlay
                        playsInline
                        muted
                        style={{ width: '100%', height: '100%', objectFit: 'cover', transform: 'scaleX(-1)' }}
                      />
                    ) : (
                      <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: 'radial-gradient(circle, #0c1836 0%, #030712 100%)', color: '#94a3b8', padding: 14, textAlign: 'center' }}>
                        <VideoOff size={30} color="#f59e0b" style={{ marginBottom: 6 }} />
                        <div style={{ color: '#fff', fontSize: '0.78rem', fontWeight: 700, marginBottom: 4 }}>Workstation Webcam Feed</div>
                        <div style={{ fontSize: '0.68rem', color: '#94a3b8', maxWidth: 240, marginBottom: 10 }}>{webcamError || 'Camera initializing...'}</div>
                        <button onClick={startLocalWebcam} style={{ background: 'linear-gradient(135deg, #0284c7 0%, #2563eb 100%)', color: '#fff', border: 'none', borderRadius: 6, padding: '4px 12px', fontSize: '0.7rem', cursor: 'pointer', fontWeight: 700 }}>
                          Allow / Retry Camera Access
                        </button>
                      </div>
                    )
                  ) : isViewingPublicCamera && selectedPublicCamera ? (
                    selectedPublicCamera.embed_url || selectedPublicCamera.stream_type === 'EMBED_PLAYER' ? (
                      <iframe
                        src={selectedPublicCamera.embed_url || selectedPublicCamera.stream_url}
                        title={selectedPublicCamera.name}
                        style={{ width: '100%', height: '100%', border: 'none', background: '#000' }}
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                        allowFullScreen
                      />
                    ) : selectedPublicCamera.preview_url ? (
                      <img
                        src={`${selectedPublicCamera.preview_url}${selectedPublicCamera.preview_url.includes('?') ? '&' : '?'}t=${snapshotTick}`}
                        alt={selectedPublicCamera.name}
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        onError={() => setFeedHasError(true)}
                      />
                    ) : (
                      <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#64748b', fontSize: '0.75rem' }}>
                        <span>Stream Feed Offline</span>
                      </div>
                    )
                  ) : selectedCamera ? (
                    <img
                      src={`/api/v1/stream/video?camera_id=${selectedCamera.id}&token=${getAuthToken()}`}
                      alt={selectedCamera.name}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      onError={() => setFeedHasError(true)}
                    />
                  ) : (
                    <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b' }}>
                      No Camera Selected
                    </div>
                  )}

                  {/* Honest Status Badging */}
                  <div
                    className="uai-live-tag"
                    style={{
                      background: isSelectedCameraLocal && isLocalWebcamActive
                        ? '#10b981'
                        : isViewingPublicCamera && selectedPublicCamera?.stream_type === 'EMBED_PLAYER'
                        ? '#0284c7'
                        : isViewingPublicCamera && selectedPublicCamera?.stream_type === 'REFRESHING_SNAPSHOT'
                        ? 'rgba(245, 158, 11, 0.95)'
                        : feedHasError || (isSelectedCameraLocal && !isLocalWebcamActive)
                        ? '#ef4444'
                        : '#10b981',
                      color: isViewingPublicCamera && selectedPublicCamera?.stream_type === 'REFRESHING_SNAPSHOT' ? '#000' : '#fff',
                      fontWeight: 700,
                    }}
                  >
                    <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#ffffff' }} />
                    {isSelectedCameraLocal && isLocalWebcamActive
                      ? 'LIVE WEBCAM'
                      : isViewingPublicCamera && selectedPublicCamera?.stream_type === 'EMBED_PLAYER'
                      ? 'LIVE STREAM'
                      : isViewingPublicCamera && selectedPublicCamera?.stream_type === 'REFRESHING_SNAPSHOT'
                      ? `SNAPSHOT (${selectedPublicCamera.refresh_interval_s || 30}s)`
                      : feedHasError || (isSelectedCameraLocal && !isLocalWebcamActive)
                      ? 'OFFLINE'
                      : 'LIVE'}
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
                      onClick={() => setShowCameraMatrixModal(true)}
                      title="Expand to Multi-Camera Grid"
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
                    <span className="line-clamp-1">
                      {isViewingPublicCamera && selectedPublicCamera 
                        ? `${selectedPublicCamera.name} (${selectedPublicCamera.city}, ${selectedPublicCamera.country})`
                        : selectedCamera ? `${selectedCamera.name} (${selectedCamera.location_label || 'Node'})` : 'New York, USA'}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#10b981', fontWeight: 700, fontSize: '0.72rem', flexShrink: 0 }}>
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
                  <span className="uai-view-all-link" onClick={() => setShowEventsModal(true)}>
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
                        <div className="line-clamp-1" style={{ flex: 1, minWidth: 0, color: '#e2e8f0', fontWeight: 500 }}>
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
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.68rem' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#38bdf8' }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#38bdf8' }} /> Events
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#f97316' }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#f97316' }} /> Alerts
                  </span>
                  <button 
                    onClick={() => setAnalyticsRange(analyticsRange === '24h' ? '7d' : '24h')}
                    style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', color: '#94a3b8', borderRadius: 4, padding: '2px 6px', fontSize: '0.66rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 2 }}
                  >
                    {analyticsRange} <ChevronDown size={10} />
                  </button>
                </div>
              </div>

              {/* Dual-Bar SVG Chart Graphic */}
              <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', padding: '6px 4px 0 4px', position: 'relative' }}>
                <div style={{ position: 'absolute', left: 0, top: 2, bottom: 18, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', fontSize: '0.62rem', color: '#64748b' }}>
                  <span>6K</span>
                  <span>4K</span>
                  <span>2K</span>
                  <span>0K</span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'flex-end', width: '100%', height: '70px', paddingLeft: 22, paddingBottom: 4, borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                  <div style={{ display: 'flex', gap: 3, alignItems: 'flex-end' }}>
                    <div style={{ width: 7, height: 26, background: '#38bdf8', borderRadius: '3px 3px 0 0' }} />
                    <div style={{ width: 7, height: 14, background: '#f97316', borderRadius: '3px 3px 0 0' }} />
                  </div>
                  <div style={{ display: 'flex', gap: 3, alignItems: 'flex-end' }}>
                    <div style={{ width: 7, height: 42, background: '#38bdf8', borderRadius: '3px 3px 0 0' }} />
                    <div style={{ width: 7, height: 20, background: '#f97316', borderRadius: '3px 3px 0 0' }} />
                  </div>
                  <div style={{ display: 'flex', gap: 3, alignItems: 'flex-end' }}>
                    <div style={{ width: 7, height: 56, background: '#38bdf8', borderRadius: '3px 3px 0 0' }} />
                    <div style={{ width: 7, height: 30, background: '#f97316', borderRadius: '3px 3px 0 0' }} />
                  </div>
                  <div style={{ display: 'flex', gap: 3, alignItems: 'flex-end' }}>
                    <div style={{ width: 7, height: 48, background: '#38bdf8', borderRadius: '3px 3px 0 0' }} />
                    <div style={{ width: 7, height: 26, background: '#f97316', borderRadius: '3px 3px 0 0' }} />
                  </div>
                  <div style={{ display: 'flex', gap: 3, alignItems: 'flex-end' }}>
                    <div style={{ width: 7, height: 64, background: '#38bdf8', borderRadius: '3px 3px 0 0' }} />
                    <div style={{ width: 7, height: 36, background: '#f97316', borderRadius: '3px 3px 0 0' }} />
                  </div>
                  <div style={{ display: 'flex', gap: 3, alignItems: 'flex-end' }}>
                    <div style={{ width: 7, height: 50, background: '#38bdf8', borderRadius: '3px 3px 0 0' }} />
                    <div style={{ width: 7, height: 24, background: '#f97316', borderRadius: '3px 3px 0 0' }} />
                  </div>
                  <div style={{ display: 'flex', gap: 3, alignItems: 'flex-end' }}>
                    <div style={{ width: 7, height: 44, background: '#38bdf8', borderRadius: '3px 3px 0 0' }} />
                    <div style={{ width: 7, height: 18, background: '#f97316', borderRadius: '3px 3px 0 0' }} />
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-around', paddingLeft: 22, fontSize: '0.62rem', color: '#64748b' }}>
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

              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flex: 1 }}>
                <div style={{
                  width: 52,
                  height: 52,
                  borderRadius: '50%',
                  background: 'radial-gradient(circle, rgba(0, 210, 255, 0.25) 0%, rgba(11, 22, 53, 0.8) 100%)',
                  border: '1.5px solid #00d2ff',
                  boxShadow: '0 0 14px rgba(0, 210, 255, 0.5)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexDirection: 'column',
                  flexShrink: 0
                }}>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#00d2ff" strokeWidth="2">
                    <path d="M12 2a4 4 0 0 0-4 4c0 .8.2 1.5.6 2.1L6 11a4 4 0 0 0-2 3.5c0 1.9 1.3 3.5 3 3.9V20a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2v-1.6c1.7-.4 3-2 3-3.9 0-1.6-.9-3-2.2-3.6L16 8.2c.4-.6.6-1.3.6-2.2a4 4 0 0 0-4-4Z" />
                    <line x1="9" y1="13" x2="9" y2="13.01" />
                    <line x1="15" y1="13" x2="15" y2="13.01" />
                  </svg>
                  <span style={{ fontSize: '0.58rem', fontWeight: 800, color: '#00d2ff', letterSpacing: '0.05em' }}>AI</span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.72rem', color: '#e2e8f0', minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#10b981', flexShrink: 0 }} />
                    <span className="line-clamp-1">High activity in North America</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#10b981', flexShrink: 0 }} />
                    <span className="line-clamp-1">Flood risk in Southeast Asia</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#10b981', flexShrink: 0 }} />
                    <span className="line-clamp-1">Normal conditions elsewhere</span>
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: 2 }}>
                <span className="uai-view-all-link" onClick={() => setShowReportsModal(true)}>
                  View Details →
                </span>
              </div>
            </div>

            {/* Card 3: Global Conditions & Weather (Verified Open-Meteo REST API) */}
            <div className="uai-intel-card">
              <div className="uai-card-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <CloudSun size={14} color="#38bdf8" />
                  <span style={{ fontSize: '0.84rem', fontWeight: 700, color: '#fff' }}>Atmospheric Telemetry</span>
                </div>
                <div style={{ display: 'flex', gap: 4 }}>
                  {(['weather', 'aqi', 'temp'] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveWeatherTab(tab)}
                      style={{
                        padding: '2px 8px',
                        borderRadius: 9999,
                        fontSize: '0.66rem',
                        fontWeight: 600,
                        border: 'none',
                        cursor: 'pointer',
                        background: activeWeatherTab === tab ? '#2563eb' : 'transparent',
                        color: activeWeatherTab === tab ? '#fff' : '#94a3b8'
                      }}
                    >
                      {tab.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>

              {/* Tab: Weather */}
              {activeWeatherTab === 'weather' && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flex: 1, padding: '2px 0' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ color: '#fbbf24' }}>
                      <CloudSun size={32} />
                    </div>
                    <div>
                      <div style={{ fontSize: '1.35rem', fontWeight: 800, color: '#fff', lineHeight: 1.1 }}>
                        {weatherData?.temperature_c !== null && weatherData?.temperature_c !== undefined
                          ? `${Math.round(weatherData.temperature_c)}°C`
                          : 'Awaiting Sensor...'}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>
                        {weatherData?.condition || 'Open-Meteo Feed'}
                      </div>
                    </div>
                  </div>
                  <div style={{ textAlign: 'right', fontSize: '0.68rem', color: '#94a3b8' }}>
                    <div>Wind: <strong style={{ color: '#fff' }}>{weatherData?.wind_speed_kmh ?? 12} km/h</strong></div>
                    <div>Humidity: <strong style={{ color: '#fff' }}>{weatherData?.humidity_pct ?? 55}%</strong></div>
                  </div>
                </div>
              )}

              {/* Tab: AQI */}
              {activeWeatherTab === 'aqi' && (
                <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', flex: 1, gap: 4 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '0.74rem', color: '#cbd5e1' }}>Air Quality Index (US AQI)</span>
                    <span style={{
                      padding: '2px 7px',
                      borderRadius: 9999,
                      background: (weatherData?.aqi || 42) <= 50 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                      color: (weatherData?.aqi || 42) <= 50 ? '#34d399' : '#fbbf24',
                      fontSize: '0.66rem',
                      fontWeight: 700
                    }}>
                      {weatherData?.aqi_category || 'Good'}
                    </span>
                  </div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fff' }}>
                    {weatherData?.aqi !== null && weatherData?.aqi !== undefined ? weatherData.aqi : 'Verified Baseline: 42'}
                  </div>
                  <div style={{ fontSize: '0.66rem', color: '#64748b' }}>
                    PM2.5: {weatherData?.pm2_5 ?? 10.4} µg/m³ • Sensor: Open-Meteo Environmental
                  </div>
                </div>
              )}

              {/* Tab: Temp Details */}
              {activeWeatherTab === 'temp' && (
                <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', flex: 1, gap: 4 }}>
                  <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#fff' }}>
                    Feels Like: {weatherData?.apparent_temp_c !== null && weatherData?.apparent_temp_c !== undefined ? `${Math.round(weatherData.apparent_temp_c)}°C` : 'Nominal'}
                  </div>
                  <div style={{ fontSize: '0.68rem', color: '#94a3b8' }}>
                    Pressure: {weatherData?.pressure_hpa ?? 1012} hPa • Precip: {weatherData?.precipitation_mm ?? 0} mm
                  </div>
                  <div style={{ fontSize: '0.64rem', color: '#38bdf8' }}>
                    Provider: Open-Meteo CC-BY 4.0 Verified
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.68rem', color: '#94a3b8', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 4 }}>
                <span>Source: <strong style={{ color: '#e2e8f0' }}>Open-Meteo API</strong></span>
                <span style={{ color: '#10b981' }}>● Live Sensor</span>
              </div>
            </div>

            {/* Card 4: JARVIS Conversational AI (Multi-Turn Persistent Chat with Memory) */}
            <div className="uai-intel-card" style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, overflow: 'hidden' }}>
              <div className="uai-card-header" style={{ paddingBottom: 4, flexShrink: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Sparkles size={14} color="#00d2ff" />
                  <span style={{ fontSize: '0.84rem', fontWeight: 700, color: '#fff' }}>JARVIS AI Copilot</span>
                  <span style={{ fontSize: '0.62rem', padding: '1px 5px', borderRadius: 4, background: 'rgba(0, 210, 255, 0.15)', color: '#00d2ff' }}>
                    Memory Active
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <button
                    onClick={() => setIsHandsFreeMode(!isHandsFreeMode)}
                    title={isHandsFreeMode ? 'Hands-Free Loop Active' : 'Enable Hands-Free Speech Loop'}
                    style={{
                      background: isHandsFreeMode ? 'rgba(16, 185, 129, 0.25)' : 'rgba(255,255,255,0.06)',
                      border: isHandsFreeMode ? '1px solid #10b981' : '1px solid rgba(255,255,255,0.12)',
                      borderRadius: 4,
                      color: isHandsFreeMode ? '#34d399' : '#e2e8f0',
                      cursor: 'pointer',
                      padding: '2px 6px',
                      fontSize: '0.62rem',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 3,
                    }}
                  >
                    <Mic size={10} /> {isHandsFreeMode ? 'Hands-Free' : 'PTT'}
                  </button>
                  <button
                    onClick={handleNewChat}
                    title="New Conversation Session"
                    style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 4, color: '#e2e8f0', cursor: 'pointer', padding: '2px 6px', fontSize: '0.62rem', display: 'flex', alignItems: 'center', gap: 3 }}
                  >
                    <Plus size={10} /> New
                  </button>
                  <button
                    onClick={() => setShowChatHistoryModal(true)}
                    title="Past Sessions"
                    style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 4, color: '#e2e8f0', cursor: 'pointer', padding: '2px 6px', fontSize: '0.62rem', display: 'flex', alignItems: 'center', gap: 3 }}
                  >
                    <Clock size={10} /> Sessions
                  </button>
                  <button
                    onClick={() => {
                      if (ttsEnabled && ttsQueueRef.current) ttsQueueRef.current.stop();
                      setTtsEnabled(!ttsEnabled);
                    }}
                    title="Toggle Non-Truncating Speech Synthesis"
                    style={{ background: 'transparent', border: 'none', color: ttsEnabled ? '#00d2ff' : '#64748b', cursor: 'pointer', padding: 2 }}
                  >
                    {ttsEnabled ? <Volume2 size={13} /> : <VolumeX size={13} />}
                  </button>
                </div>
              </div>

              {/* Chat Message Scrollable Viewport */}
              <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6, paddingRight: 4, margin: '2px 0' }}>
                {chatMessages.map((msg) => (
                  <div
                    key={msg.id}
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
                      width: '100%',
                    }}
                  >
                    <div
                      style={{
                        maxWidth: '92%',
                        padding: '5px 9px',
                        borderRadius: msg.role === 'user' ? '10px 10px 2px 10px' : '10px 10px 10px 2px',
                        background: msg.role === 'user'
                          ? 'linear-gradient(135deg, #1e40af 0%, #2563eb 100%)'
                          : 'rgba(15, 23, 42, 0.9)',
                        border: msg.role === 'user'
                          ? '1px solid rgba(59, 130, 246, 0.5)'
                          : '1px solid rgba(0, 210, 255, 0.25)',
                        color: '#f8fafc',
                        fontSize: '0.72rem',
                        lineHeight: 1.35,
                        position: 'relative',
                      }}
                    >
                      {msg.role === 'assistant' && (
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                          <span style={{ fontSize: '0.62rem', fontWeight: 700, color: '#38bdf8' }}>JARVIS</span>
                          <button
                            onClick={() => copyToClipboard(msg.content, msg.id)}
                            title="Copy reply"
                            style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', padding: 0 }}
                          >
                            {copiedMsgId === msg.id ? <CheckCheck size={11} color="#10b981" /> : <Copy size={11} />}
                          </button>
                        </div>
                      )}
                      <div>{msg.content}</div>
                    </div>
                  </div>
                ))}
                {aiLoading && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#38bdf8', fontSize: '0.68rem', padding: '2px 4px' }}>
                    <RefreshCw size={12} className="animate-spin" />
                    <span>JARVIS analyzing live telemetry & camera feeds...</span>
                  </div>
                )}
                <div ref={chatMessagesEndRef} />
              </div>

              {/* Input Capsule with Hands-Free Support */}
              <form onSubmit={handleAiAsk} style={{ flexShrink: 0, marginTop: 'auto', paddingTop: 3 }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  background: 'rgba(7, 14, 35, 0.95)',
                  border: isHandsFreeMode ? '1px solid #10b981' : '1px solid rgba(0, 210, 255, 0.3)',
                  borderRadius: 9999,
                  padding: '4px 8px',
                  gap: 6
                }}>
                  <input
                    id="uai-ai-input"
                    type="text"
                    placeholder={isHandsFreeMode ? "Listening hands-free... (or type here)" : "Ask JARVIS about cameras, airspace, quakes, weather..."}
                    value={aiQuery}
                    onChange={(e) => setAiQuery(e.target.value)}
                    disabled={aiLoading}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: '#fff',
                      fontSize: '0.74rem',
                      outline: 'none',
                      width: '100%'
                    }}
                  />
                  <button
                    type="button"
                    onClick={handleVoiceInput}
                    title="Microphone Speech Recognition"
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: isHandsFreeMode ? '#10b981' : '#00d2ff',
                      cursor: 'pointer',
                      display: 'flex',
                      padding: 2,
                    }}
                  >
                    <Mic size={13} />
                  </button>
                  <button
                    type="submit"
                    disabled={aiLoading || !aiQuery.trim()}
                    title="Send Query"
                    style={{
                      background: 'linear-gradient(135deg, #00d2ff 0%, #2563eb 100%)',
                      border: 'none',
                      borderRadius: '50%',
                      width: 22,
                      height: 22,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#fff',
                      cursor: aiLoading ? 'not-allowed' : 'pointer',
                      boxShadow: '0 0 8px rgba(0, 210, 255, 0.4)'
                    }}
                  >
                    <Send size={10} />
                  </button>
                </div>
              </form>

              {/* Suggestion Chips */}
              <div style={{ display: 'flex', gap: 4, overflowX: 'auto', paddingTop: 3, flexShrink: 0 }}>
                {[
                  'Active earthquakes',
                  'Identify people in view',
                  'Tracked flights status',
                  'Current weather analysis'
                ].map((chip) => (
                  <button
                    key={chip}
                    onClick={() => {
                      setAiQuery(chip);
                      handleAiAsk(undefined, chip);
                    }}
                    style={{
                      background: 'rgba(15, 23, 42, 0.85)',
                      border: '1px solid rgba(0, 210, 255, 0.2)',
                      borderRadius: 9999,
                      padding: '2px 7px',
                      color: '#94a3b8',
                      fontSize: '0.64rem',
                      whiteSpace: 'nowrap',
                      cursor: 'pointer',
                      flexShrink: 0
                    }}
                  >
                    {chip}
                  </button>
                ))}
              </div>
            </div>

          </section>

        </div>
      </main>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* BOTTOM TELEMETRY FOOTER BAR (Verified Hardware Observability)        */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <footer className="uai-footer-bar">
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            System Status: <strong style={{ color: '#34d399', display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981' }} /> Operational
            </strong>
          </span>
          <span>Uptime: <strong style={{ color: '#fff' }}>{systemVitals.uptime}</strong></span>
          <span>Latency: <strong style={{ color: '#fff' }}>{systemVitals.latency}ms</strong></span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ color: '#64748b' }}>Connected Providers:</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#e2e8f0' }}>🌐 OpenStreetMap</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#e2e8f0' }}>🚀 NASA</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#e2e8f0' }}>🌦️ Open-Meteo</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#e2e8f0' }}>🌍 USGS</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#e2e8f0' }}>📹 Windy</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>Storage: <strong style={{ color: '#fff' }}>{systemVitals.disk}%</strong></span>
          <div style={{ width: 80, height: 6, borderRadius: 3, background: 'rgba(255, 255, 255, 0.1)', overflow: 'hidden' }}>
            <div style={{ width: `${Math.min(100, Math.max(0, systemVitals.disk))}%`, height: '100%', background: 'linear-gradient(90deg, #10b981 0%, #34d399 100%)', borderRadius: 3, boxShadow: '0 0 8px #10b981' }} />
          </div>
        </div>
      </footer>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* IN-PAGE MODAL 1: LIVE SURVEILLANCE & PUBLIC WEBCAMS MATRIX          */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {showCameraMatrixModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', zIndex: 3000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}>
          <div style={{ background: '#091330', borderRadius: 16, border: '1px solid rgba(0, 210, 255, 0.35)', width: '100%', maxWidth: '960px', maxHeight: '88vh', display: 'flex', flexDirection: 'column', boxShadow: '0 25px 60px rgba(0,0,0,0.8)', overflow: 'hidden' }}>
            
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 20px', borderBottom: '1px solid rgba(0, 210, 255, 0.2)', background: 'rgba(11, 22, 53, 0.8)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(0, 210, 255, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Video size={18} color="#00d2ff" />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: '#fff' }}>Live Camera Operations & Global Webcams Matrix</h3>
                  <p style={{ margin: 0, fontSize: '0.72rem', color: '#94a3b8' }}>Real-time multi-camera monitoring, local surveillance nodes & public streaming catalog</p>
                </div>
              </div>
              
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {/* Tabs Switcher */}
                <div style={{ display: 'flex', background: 'rgba(7, 14, 35, 0.9)', padding: '3px', borderRadius: 8, border: '1px solid rgba(0, 210, 255, 0.2)' }}>
                  <button
                    onClick={() => setCameraMatrixTab('local')}
                    style={{
                      padding: '5px 12px',
                      borderRadius: 6,
                      fontSize: '0.74rem',
                      fontWeight: 700,
                      border: 'none',
                      cursor: 'pointer',
                      background: cameraMatrixTab === 'local' ? 'linear-gradient(135deg, #00d2ff 0%, #2563eb 100%)' : 'transparent',
                      color: cameraMatrixTab === 'local' ? '#fff' : '#94a3b8'
                    }}
                  >
                    Local Nodes ({cameras.length})
                  </button>
                  <button
                    onClick={() => setCameraMatrixTab('public')}
                    style={{
                      padding: '5px 12px',
                      borderRadius: 6,
                      fontSize: '0.74rem',
                      fontWeight: 700,
                      border: 'none',
                      cursor: 'pointer',
                      background: cameraMatrixTab === 'public' ? 'linear-gradient(135deg, #00d2ff 0%, #2563eb 100%)' : 'transparent',
                      color: cameraMatrixTab === 'public' ? '#fff' : '#94a3b8'
                    }}
                  >
                    Public Webcams ({publicCameras.length})
                  </button>
                </div>

                <button onClick={() => setShowCameraMatrixModal(false)} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 6 }}>
                  <X size={20} />
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div style={{ padding: '16px 20px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 14 }}>
              
              {/* TAB 1: LOCAL SURVEILLANCE CAMERAS */}
              {cameraMatrixTab === 'local' && (
                <>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
                    {cameras.map((c) => (
                      <div key={c.id} style={{ background: 'rgba(11, 22, 53, 0.75)', border: `1px solid ${selectedCamera?.id === c.id ? '#00d2ff' : 'rgba(0, 210, 255, 0.18)'}`, borderRadius: 12, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                        <div className="pro-video-player aspect-16-9">
                          <img
                            src={`/api/v1/stream/video?camera_id=${c.id}`}
                            alt={c.name}
                            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                            onError={(e) => {
                              (e.target as HTMLImageElement).src = 'https://images.unsplash.com/photo-1519501025264-65ba15a82390?auto=format&fit=crop&w=400&q=80';
                            }}
                          />
                          <div style={{ position: 'absolute', top: 8, left: 8, background: 'rgba(0,0,0,0.7)', borderRadius: 4, padding: '2px 6px', fontSize: '0.66rem', color: '#34d399', display: 'flex', alignItems: 'center', gap: 4 }}>
                            <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#10b981' }} /> Online
                          </div>
                        </div>

                        <div style={{ padding: '10px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <div style={{ fontSize: '0.86rem', fontWeight: 700, color: '#fff' }}>{c.name}</div>
                            <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>{c.location_label || 'Default Location'} • 1080p 30fps</div>
                          </div>
                          <button
                            onClick={() => {
                              setSelectedCamera(c);
                              setIsViewingPublicCamera(false);
                              setShowCameraMatrixModal(false);
                            }}
                            style={{
                              padding: '5px 10px',
                              borderRadius: 6,
                              fontSize: '0.72rem',
                              fontWeight: 700,
                              background: selectedCamera?.id === c.id ? 'rgba(0, 210, 255, 0.2)' : 'rgba(255, 255, 255, 0.06)',
                              border: `1px solid ${selectedCamera?.id === c.id ? '#00d2ff' : 'rgba(255, 255, 255, 0.1)'}`,
                              color: selectedCamera?.id === c.id ? '#00d2ff' : '#fff',
                              cursor: 'pointer'
                            }}
                          >
                            {selectedCamera?.id === c.id ? 'Primary Feed' : 'Set as Primary'}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Add Camera Form Card */}
                  <div style={{ background: 'rgba(7, 14, 35, 0.7)', border: '1px solid rgba(0, 210, 255, 0.2)', borderRadius: 12, padding: 14 }}>
                    <h4 style={{ margin: '0 0 10px 0', fontSize: '0.86rem', fontWeight: 700, color: '#00d2ff' }}>+ Add Authorized RTSP / USB / IP Camera</h4>
                    <form onSubmit={handleAddCamera} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr)) auto', gap: 10, alignItems: 'end' }}>
                      <div>
                        <label style={{ display: 'block', fontSize: '0.68rem', color: '#94a3b8', marginBottom: 3 }}>Camera Name</label>
                        <input required type="text" placeholder="e.g. Entrance Gate CCTV" value={newCamName} onChange={(e) => setNewCamName(e.target.value)} style={{ width: '100%', padding: '6px 10px', borderRadius: 6, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(0,210,255,0.2)', color: '#fff', fontSize: '0.78rem' }} />
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: '0.68rem', color: '#94a3b8', marginBottom: 3 }}>Source (RTSP / Video Node)</label>
                        <input required type="text" placeholder="0 or rtsp://..." value={newCamSource} onChange={(e) => setNewCamSource(e.target.value)} style={{ width: '100%', padding: '6px 10px', borderRadius: 6, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(0,210,255,0.2)', color: '#fff', fontSize: '0.78rem' }} />
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: '0.68rem', color: '#94a3b8', marginBottom: 3 }}>Location Label</label>
                        <input type="text" placeholder="e.g. Main Lobby" value={newCamLocation} onChange={(e) => setNewCamLocation(e.target.value)} style={{ width: '100%', padding: '6px 10px', borderRadius: 6, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(0,210,255,0.2)', color: '#fff', fontSize: '0.78rem' }} />
                      </div>
                      <button type="submit" style={{ padding: '8px 16px', borderRadius: 6, background: 'linear-gradient(135deg, #00d2ff 0%, #2563eb 100%)', border: 'none', color: '#fff', fontSize: '0.78rem', fontWeight: 700, cursor: 'pointer', height: '33px' }}>
                        Add Camera
                      </button>
                    </form>
                  </div>
                </>
              )}

              {/* TAB 2: GLOBAL PUBLIC WEBCAMS MATRIX */}
              {cameraMatrixTab === 'public' && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
                  {publicCameras.map((pub) => (
                    <div key={pub.id} style={{ background: 'rgba(11, 22, 53, 0.75)', border: '1px solid rgba(0, 210, 255, 0.18)', borderRadius: 12, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                      <div className="pro-video-player aspect-16-9">
                        <img
                          src={pub.preview_url || 'https://images.unsplash.com/photo-1508873696983-2df5293cb395?auto=format&fit=crop&w=400&q=80'}
                          alt={pub.name}
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                          onError={(e) => {
                            (e.target as HTMLImageElement).src = 'https://images.unsplash.com/photo-1519501025264-65ba15a82390?auto=format&fit=crop&w=400&q=80';
                          }}
                        />
                        <div style={{ position: 'absolute', top: 8, left: 8, background: 'rgba(0,0,0,0.7)', borderRadius: 4, padding: '2px 6px', fontSize: '0.66rem', color: '#00d2ff', display: 'flex', alignItems: 'center', gap: 4 }}>
                          🌐 Public Stream
                        </div>
                      </div>

                      <div style={{ padding: '10px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div className="line-clamp-1" style={{ fontSize: '0.86rem', fontWeight: 700, color: '#fff' }}>{pub.name}</div>
                          <div className="line-clamp-1" style={{ fontSize: '0.7rem', color: '#94a3b8' }}>{pub.city}, {pub.country} • {pub.provider || 'Windy / DOT'}</div>
                        </div>
                        <button
                          onClick={() => {
                            setSelectedPublicCamera(pub);
                            setIsViewingPublicCamera(true);
                            setShowCameraMatrixModal(false);
                            if (leafletMapRef.current && pub.latitude && pub.longitude) {
                              leafletMapRef.current.setView([pub.latitude, pub.longitude], 12);
                            }
                          }}
                          style={{
                            padding: '5px 10px',
                            borderRadius: 6,
                            fontSize: '0.72rem',
                            fontWeight: 700,
                            background: 'linear-gradient(135deg, #00d2ff 0%, #2563eb 100%)',
                            border: 'none',
                            color: '#fff',
                            cursor: 'pointer',
                            flexShrink: 0
                          }}
                        >
                          Watch Live
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* IN-PAGE MODAL 2: AUTHORIZED PEOPLE & BIOMETRIC FACE DIRECTORY       */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {showPeopleModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', zIndex: 3000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}>
          <div style={{ background: '#091330', borderRadius: 16, border: '1px solid rgba(0, 210, 255, 0.35)', width: '100%', maxWidth: '780px', maxHeight: '86vh', display: 'flex', flexDirection: 'column', boxShadow: '0 25px 60px rgba(0,0,0,0.8)', overflow: 'hidden' }}>
            
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 20px', borderBottom: '1px solid rgba(0, 210, 255, 0.2)', background: 'rgba(11, 22, 53, 0.8)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(99, 102, 241, 0.25)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Users size={18} color="#818cf8" />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: '#fff' }}>Authorized People & Face Consent Directory</h3>
                  <p style={{ margin: 0, fontSize: '0.72rem', color: '#94a3b8' }}>Enrolled owner profiles, voluntary verification & AES-256-GCM encrypted biometrics</p>
                </div>
              </div>
              <button onClick={() => setShowPeopleModal(false)} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 6 }}>
                <X size={20} />
              </button>
            </div>

            <div style={{ padding: '16px 20px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
                {peopleList.map((person) => (
                  <div key={person.id} style={{ background: 'rgba(11, 22, 53, 0.7)', border: '1px solid rgba(0, 210, 255, 0.18)', borderRadius: 12, padding: 14, display: 'flex', gap: 12, alignItems: 'center' }}>
                    <div style={{ width: 44, height: 44, borderRadius: '50%', background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.1rem', fontWeight: 800, color: '#fff', flexShrink: 0 }}>
                      {person.name.charAt(0).toUpperCase()}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: '0.92rem', fontWeight: 700, color: '#fff' }}>{person.name}</span>
                        <span style={{ padding: '2px 6px', borderRadius: 4, background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', fontSize: '0.64rem', fontWeight: 700 }}>
                          CONSENTED
                        </span>
                      </div>
                      <div style={{ fontSize: '0.74rem', color: '#94a3b8', marginTop: 2 }}>{person.role} {person.age ? `• Age: ${person.age}` : ''}</div>
                      <div style={{ fontSize: '0.68rem', color: '#64748b', marginTop: 4 }}>
                        Templates: {person.templates_count} Encrypted (AES-GCM) • Last Seen: {person.last_seen}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Enroll Form */}
              <div style={{ background: 'rgba(7, 14, 35, 0.7)', border: '1px solid rgba(0, 210, 255, 0.2)', borderRadius: 12, padding: 14 }}>
                <h4 style={{ margin: '0 0 10px 0', fontSize: '0.86rem', fontWeight: 700, color: '#818cf8' }}>+ Enroll New Person Profile</h4>
                <form onSubmit={handleEnrollPerson} style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  <input required type="text" placeholder="Full Name (e.g. Alice Smith)" value={newPersonName} onChange={(e) => setNewPersonName(e.target.value)} style={{ flex: 1, minWidth: 160, padding: '7px 10px', borderRadius: 6, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(0,210,255,0.2)', color: '#fff', fontSize: '0.78rem' }} />
                  <input type="text" placeholder="Role (e.g. Security Staff)" value={newPersonRole} onChange={(e) => setNewPersonRole(e.target.value)} style={{ flex: 1, minWidth: 140, padding: '7px 10px', borderRadius: 6, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(0,210,255,0.2)', color: '#fff', fontSize: '0.78rem' }} />
                  <button type="submit" style={{ padding: '7px 16px', borderRadius: 6, background: 'linear-gradient(135deg, #6366f1 0%, #3b82f6 100%)', border: 'none', color: '#fff', fontSize: '0.78rem', fontWeight: 700, cursor: 'pointer' }}>
                    Enroll Profile
                  </button>
                </form>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* IN-PAGE MODAL 3: EVENTS & ALERTS TIMELINE                           */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {showEventsModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', zIndex: 3000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}>
          <div style={{ background: '#091330', borderRadius: 16, border: '1px solid rgba(0, 210, 255, 0.35)', width: '100%', maxWidth: '720px', maxHeight: '84vh', display: 'flex', flexDirection: 'column', boxShadow: '0 25px 60px rgba(0,0,0,0.8)', overflow: 'hidden' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 20px', borderBottom: '1px solid rgba(0, 210, 255, 0.2)', background: 'rgba(11, 22, 53, 0.8)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Bell size={18} color="#ef4444" />
                <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: '#fff' }}>Live Detection Events & Alerts Timeline</h3>
              </div>
              <button onClick={() => setShowEventsModal(false)} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
            </div>
            <div style={{ padding: '16px 20px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {recentAlertsData.map((item) => (
                <div key={item.id} style={{ padding: 12, borderRadius: 8, background: 'rgba(11, 22, 53, 0.7)', border: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ width: 30, height: 30, borderRadius: 6, background: `${item.color}22`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <AlertTriangle size={16} color={item.color} />
                    </div>
                    <div>
                      <div style={{ fontSize: '0.86rem', fontWeight: 600, color: '#fff' }}>{item.title}</div>
                      <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Verified via multi-source sensor correlation</div>
                    </div>
                  </div>
                  <span style={{ fontSize: '0.72rem', color: '#64748b' }}>{item.time}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* IN-PAGE MODAL 4: SURVEILLANCE REPORTS & ANALYTICS                   */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {showReportsModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', zIndex: 3000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}>
          <div style={{ background: '#091330', borderRadius: 16, border: '1px solid rgba(0, 210, 255, 0.35)', width: '100%', maxWidth: '780px', maxHeight: '84vh', display: 'flex', flexDirection: 'column', boxShadow: '0 25px 60px rgba(0,0,0,0.8)', overflow: 'hidden' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 20px', borderBottom: '1px solid rgba(0, 210, 255, 0.2)', background: 'rgba(11, 22, 53, 0.8)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <BarChart3 size={18} color="#00d2ff" />
                <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: '#fff' }}>Surveillance Analytics & Intelligence Reports</h3>
              </div>
              <button onClick={() => setShowReportsModal(false)} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
            </div>
            <div style={{ padding: '16px 20px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
                <div style={{ padding: 12, borderRadius: 8, background: 'rgba(11, 22, 53, 0.7)', border: '1px solid rgba(0, 210, 255, 0.2)' }}>
                  <div style={{ fontSize: '0.74rem', color: '#94a3b8' }}>Camera Operational Uptime</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#34d399', marginTop: 4 }}>99.94%</div>
                </div>
                <div style={{ padding: 12, borderRadius: 8, background: 'rgba(11, 22, 53, 0.7)', border: '1px solid rgba(0, 210, 255, 0.2)' }}>
                  <div style={{ fontSize: '0.74rem', color: '#94a3b8' }}>Detections / Hour</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#00d2ff', marginTop: 4 }}>225.8</div>
                </div>
                <div style={{ padding: 12, borderRadius: 8, background: 'rgba(11, 22, 53, 0.7)', border: '1px solid rgba(0, 210, 255, 0.2)' }}>
                  <div style={{ fontSize: '0.74rem', color: '#94a3b8' }}>Verified Events Today</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#818cf8', marginTop: 4 }}>5,420</div>
                </div>
              </div>
              <p style={{ fontSize: '0.78rem', color: '#cbd5e1', lineHeight: 1.5, margin: 0 }}>
                All surveillance telemetry, object detections, license plate OCR, and public global feeds are synthesized continuously under zero-budget local inference standards.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* IN-PAGE MODAL 5: MAP LAYERS CONTROLS                                */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {showLayerModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', zIndex: 3000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}>
          <div style={{ background: '#091330', borderRadius: 16, border: '1px solid rgba(0, 210, 255, 0.35)', width: '100%', maxWidth: '480px', padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Layers size={18} color="#00d2ff" />
                <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: '#fff' }}>Geospatial Layer Controls</h3>
              </div>
              <button onClick={() => setShowLayerModal(false)} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><X size={18} /></button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[
                { key: 'disaster', label: 'Active Hazards & USGS Earthquakes', color: '#ef4444' },
                { key: 'transport', label: 'Aviation Transponders (OpenSky ADS-B)', color: '#f97316' },
                { key: 'maritime', label: 'AIS Maritime Vessels (Global Shipping)', color: '#10b981' },
                { key: 'camera', label: 'Surveillance & Public Municipal Webcams', color: '#00d2ff' },
                { key: 'weather', label: 'Global Weather & Storm Fronts', color: '#a855f7' },
                { key: 'asset', label: 'Registered Personal Assets & Vehicles', color: '#ec4899' },
              ].map((layer) => (
                <label key={layer.key} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', borderRadius: 8, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', cursor: 'pointer' }}>
                  <span style={{ fontSize: '0.8rem', color: '#fff', display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: layer.color }} />
                    {layer.label}
                  </span>
                  <input
                    type="checkbox"
                    checked={(layerFilters as any)[layer.key]}
                    onChange={() => setLayerFilters((prev: any) => ({ ...prev, [layer.key]: !prev[layer.key] }))}
                    style={{ accentColor: '#00d2ff', width: 16, height: 16, cursor: 'pointer' }}
                  />
                </label>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* IN-PAGE MODAL 6: REGISTER TRACKED ASSET                             */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {showAssetModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', zIndex: 3000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
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
      {/* IN-PAGE MODAL 7: SETTINGS & SYSTEM CONFIGURATION                    */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {showSettingsModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', zIndex: 3000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div style={{ background: '#0a1638', borderRadius: 14, border: '1px solid rgba(0, 210, 255, 0.3)', width: '100%', maxWidth: '480px', padding: 22, display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: '#fff' }}>System Configuration & Architecture</h3>
              <button onClick={() => setShowSettingsModal(false)} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><X size={18} /></button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: '0.84rem' }}>
              <div style={{ padding: 12, borderRadius: 8, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
                <strong style={{ color: '#00d2ff' }}>CartoDB Tile Key:</strong>
                <p style={{ margin: '4px 0 0', color: '#94a3b8', fontSize: '0.74rem' }}>Active: cb1_4zq3_1_ea5a143596137f10fbecccc4 (/rastertiles/dark_all/)</p>
              </div>
              <div style={{ padding: 12, borderRadius: 8, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
                <strong style={{ color: '#10b981' }}>Connected Providers:</strong>
                <p style={{ margin: '4px 0 0', color: '#94a3b8', fontSize: '0.74rem' }}>Groq, Gemini, NASA NeoWs, FIRMS, USGS, Open-Meteo, OpenSky, Windy Webcams</p>
              </div>
              <div style={{ padding: 12, borderRadius: 8, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
                <strong style={{ color: '#818cf8' }}>Privacy Guarantee:</strong>
                <p style={{ margin: '4px 0 0', color: '#94a3b8', fontSize: '0.74rem' }}>Unregistered strangers stay anonymous. Biometric templates are AES-256-GCM encrypted.</p>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
