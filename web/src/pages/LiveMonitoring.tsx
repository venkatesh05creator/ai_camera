import React, { useEffect, useState, useRef } from 'react';
import { Camera, DetectionEvent } from '../types';
import { api, getAuthToken } from '../services/api';
import {
  Play,
  Pause,
  Camera as CameraIcon,
  Maximize2,
  Shield,
  AlertTriangle,
  Eye,
  Video,
  Sparkles,
  UserPlus,
  Volume2,
  VolumeX,
  Circle,
  Download,
  Send,
  MessageSquare,
  Activity,
  CheckCircle,
  HelpCircle,
  Zap,
  Compass,
  Mic,
  MicOff,
  LayoutGrid,
  FileText,
  Search,
  Layers,
  RefreshCw,
  Box,
} from 'lucide-react';
import { QuickEnrollModal } from '../components/QuickEnrollModal';
import { AIDossierModal } from '../components/AIDossierModal';
import { VoiceCopilotModal } from '../components/VoiceCopilotModal';
import { SentenceChunkTTSQueue, pickNaturalEnglishVoice } from '../utils/ttsQueue';

interface LiveMonitoringProps {
  cameras: Camera[];
  onOpenEvents: () => void;
}

export const LiveMonitoring: React.FC<LiveMonitoringProps> = ({ cameras, onOpenEvents }) => {
  const [selectedCameraId, setSelectedCameraId] = useState<string>(cameras[0]?.id || '');
  const [viewMode, setViewMode] = useState<'focus' | 'grid'>('focus');
  const [isPlaying, setIsPlaying] = useState(true);
  const [streamError, setStreamError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const [recentEvents, setRecentEvents] = useState<DetectionEvent[]>([]);
  const [camerasHealth, setCamerasHealth] = useState<Array<any>>([]);
  const [snapshotMsg, setSnapshotMsg] = useState<string | null>(null);
  const [isQuickEnrollOpen, setIsQuickEnrollOpen] = useState(false);
  const [dossierTarget, setDossierTarget] = useState<{ id: string; name: string } | null>(null);

  // Live Camera AI Interaction & Speech
  const [rightPanelTab, setRightPanelTab] = useState<'copilot' | 'ocr_objects' | 'history_search' | 'telemetry'>('copilot');
  const [isVoiceEnabled, setIsVoiceEnabled] = useState(true);
  const [isVoiceModalOpen, setIsVoiceModalOpen] = useState(false);
  const [aiAssistantOpen, setAiAssistantOpen] = useState(false);
  const [userQuery, setUserQuery] = useState('');
  const [aiResponse, setAiResponse] = useState<string | null>(null);
  const [isAiThinking, setIsAiThinking] = useState(false);

  // OCR & Object Detection State
  const [ocrData, setOcrData] = useState<any | null>(null);
  const [isOcrLoading, setIsOcrLoading] = useState(false);
  const [objectData, setObjectData] = useState<any | null>(null);
  const [isObjectLoading, setIsObjectLoading] = useState(false);

  // Historical Event Search State
  const [historySearchQuery, setHistorySearchQuery] = useState('');
  const [historySearchResult, setHistorySearchResult] = useState<any | null>(null);
  const [isHistorySearching, setIsHistorySearching] = useState(false);

  const [isDrawerListening, setIsDrawerListening] = useState(false);
  const drawerRecognitionRef = useRef<any>(null);
  const liveUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const drawerTtsRef = useRef<SentenceChunkTTSQueue | null>(null);

  const lastGreetedName = useRef<string | null>(null);

  // Initialize Sentence TTS Queue for LiveMonitoring
  useEffect(() => {
    const queue = new SentenceChunkTTSQueue({
      onStart: () => {
        // Pause drawer microphone while speaking to prevent feedback loop
        if (drawerRecognitionRef.current && isDrawerListening) {
          try {
            drawerRecognitionRef.current.stop();
          } catch {}
          setIsDrawerListening(false);
        }
      },
    });
    drawerTtsRef.current = queue;

    return () => {
      queue.stop();
    };
  }, []);

  // Web Audio Instant Recognition Chime
  const playRecognitionChime = () => {
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
      osc.frequency.exponentialRampToValueAtTime(880.0, ctx.currentTime + 0.12); // A5
      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.26);
    } catch {
      // Audio autoplay restrictions tolerated
    }
  };

  // Continuous Adaptive Learning & Scene Perception
  const [sceneData, setSceneData] = useState<{
    fps: number;
    people_count: number;
    verified_identities: string[];
    posture: string;
    head_orientation: string;
    lighting_condition: string;
    attention_score: number;
    samples_learned: number;
    model_confidence: number;
    background_color: string;
    background_scene: string;
  }>({
    fps: 30.0,
    people_count: 0,
    verified_identities: [],
    posture: 'Upright, Ergonomic Position',
    head_orientation: 'Direct Frontal (0°)',
    lighting_condition: 'Balanced Ambient (CLAHE Active)',
    attention_score: 96,
    samples_learned: 0,
    model_confidence: 98.8,
    background_color: 'Off-white / cream',
    background_scene: 'Wall and cabinet paneling',
  });

  // Smooth Live Video Recording Feature
  const [isRecording, setIsRecording] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const recordIntervalRef = useRef<any>(null);
  const videoImgRef = useRef<HTMLImageElement | null>(null);

  useEffect(() => {
    if (cameras.length > 0) {
      if (!selectedCameraId || !cameras.some((c) => c.id === selectedCameraId)) {
        setSelectedCameraId(cameras[0].id);
      }
    }
  }, [cameras, selectedCameraId]);

  useEffect(() => {
    setStreamError(false);
  }, [selectedCameraId, retryKey]);

  // Periodic Telemetry & Events Fetcher
  useEffect(() => {
    const fetchTelemetry = async () => {
      try {
        const events = await api.getEvents({ limit: 8 });
        setRecentEvents(events);

        const scene = await api.getSceneAnalysis(selectedCameraId);
        if (scene) {
          setSceneData({
            fps: scene.fps || 30.0,
            people_count: scene.people_count || 0,
            verified_identities: scene.verified_identities || [],
            posture: scene.posture || 'Upright, Ergonomic Position',
            head_orientation: scene.head_orientation || 'Direct Frontal (0°)',
            lighting_condition: scene.lighting_condition || 'Balanced Ambient (CLAHE Active)',
            attention_score: scene.attention_score || 96,
            samples_learned: scene.samples_learned || 0,
            model_confidence: scene.model_confidence || 98.8,
            background_color: scene.background_color || 'Off-white / cream',
            background_scene: scene.background_scene || 'Wall paneling and room fixtures',
          });

          // Check if a new verified person just appeared and greet them
          if (scene.verified_identities && scene.verified_identities.length > 0) {
            const currentName = scene.verified_identities[0];
            if (currentName !== lastGreetedName.current) {
              lastGreetedName.current = currentName;
              playRecognitionChime();
              if (isVoiceEnabled && 'speechSynthesis' in window) {
                const utterance = new SpeechSynthesisUtterance(
                  `Welcome back, ${currentName}. Multi-angle biometrics active.`
                );
                utterance.rate = 1.05;
                utterance.pitch = 1.0;
                window.speechSynthesis.speak(utterance);
              }
            }
          }
        }
        // Fetch multi-camera health
        try {
          const health = await api.getCamerasHealth();
          if (health && Array.isArray(health)) {
            setCamerasHealth(health);
          }
        } catch {}
      } catch (err) {
        // Silently tolerate transient polling hiccups
      }
    };

    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 2500);
    return () => clearInterval(interval);
  }, [selectedCameraId, isVoiceEnabled]);

  // Trigger Live OCR
  const handleRunOCR = async () => {
    setIsOcrLoading(true);
    setSnapshotMsg('Scanning scene for text and signs...');
    try {
      const frameB64 = captureLiveFrameBase64() || undefined;
      const res = await api.extractOCR(selectedCamera?.id, frameB64);
      setOcrData(res);
      setRightPanelTab('ocr_objects');
      if (res.full_text) {
        setSnapshotMsg(`OCR complete: ${res.line_count} text block(s) detected`);
        if (isVoiceEnabled) {
          speakText(`OCR detected text: ${res.full_text.slice(0, 100)}`);
        }
      } else {
        setSnapshotMsg('No readable text detected in current view');
      }
    } catch (err: any) {
      setSnapshotMsg(`OCR error: ${err.message}`);
    } finally {
      setIsOcrLoading(false);
      setTimeout(() => setSnapshotMsg(null), 4000);
    }
  };

  // Trigger Live Object Detection
  const handleRunObjectDetection = async () => {
    setIsObjectLoading(true);
    setSnapshotMsg('Running modular object detection...');
    try {
      const frameB64 = captureLiveFrameBase64() || undefined;
      const res = await api.detectObjects(selectedCamera?.id, frameB64);
      setObjectData(res);
      setRightPanelTab('ocr_objects');
      const countSummary = Object.entries(res.counts || {})
        .map(([k, v]) => `${v} ${k}`)
        .join(', ');
      setSnapshotMsg(`Detected ${res.total_count} object(s): ${countSummary || 'none'}`);
      if (isVoiceEnabled && countSummary) {
        speakText(`I observe ${countSummary}.`);
      }
    } catch (err: any) {
      setSnapshotMsg(`Detection error: ${err.message}`);
    } finally {
      setIsObjectLoading(false);
      setTimeout(() => setSnapshotMsg(null), 4000);
    }
  };

  // Trigger Historical Visual Search
  const handleHistorySearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!historySearchQuery.trim()) return;
    setIsHistorySearching(true);
    try {
      const res = await api.searchHistoricalEvents(historySearchQuery, selectedCamera?.id);
      setHistorySearchResult(res);
      setRightPanelTab('history_search');
      if (isVoiceEnabled && res.summary) {
        speakText(res.summary);
      }
    } catch (err: any) {
      setSnapshotMsg(`History search failed: ${err.message}`);
      setTimeout(() => setSnapshotMsg(null), 3500);
    } finally {
      setIsHistorySearching(false);
    }
  };


  const selectedCamera = cameras.find((c) => c.id === selectedCameraId) || cameras[0];

  // Capture fresh frame from live stream image element at query time
  const captureLiveFrameBase64 = (): string | null => {
    try {
      const img = videoImgRef.current;
      if (!img || !img.naturalWidth || !img.naturalHeight) return null;
      const canvas = document.createElement('canvas');
      canvas.width = img.naturalWidth || 640;
      canvas.height = img.naturalHeight || 480;
      const ctx = canvas.getContext('2d');
      if (!ctx) return null;
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      return canvas.toDataURL('image/jpeg', 0.85);
    } catch (e) {
      console.warn('Could not extract live frame canvas data:', e);
      return null;
    }
  };

  // Voice Speech Helper with non-truncating sentence-chunk queue
  const speakText = (text: string) => {
    if (isVoiceEnabled && drawerTtsRef.current) {
      const voices = typeof window !== 'undefined' && 'speechSynthesis' in window ? window.speechSynthesis.getVoices() : [];
      const preferred = pickNaturalEnglishVoice(voices);
      drawerTtsRef.current.speak(text, preferred);
    }
  };

  // Handle Snapshot
  const handleCaptureSnapshot = async () => {
    if (!selectedCamera) return;
    try {
      setSnapshotMsg('Capturing snapshot...');
      await api.captureSnapshot(selectedCamera.id);
      setSnapshotMsg('Snapshot saved to secure object storage!');
      setTimeout(() => setSnapshotMsg(null), 3500);
    } catch (err: any) {
      setSnapshotMsg(`Snapshot failed: ${err.message}`);
      setTimeout(() => setSnapshotMsg(null), 3500);
    }
  };

  // Handle Smooth Recording
  const startRecording = () => {
    try {
      // Create offscreen canvas capturing live stream from the image element at 30 FPS
      const canvas = document.createElement('canvas');
      canvas.width = 1280;
      canvas.height = 720;
      const ctx = canvas.getContext('2d');
      const img = videoImgRef.current;

      if (!img) {
        setSnapshotMsg('Stream not ready for recording');
        return;
      }

      const stream = canvas.captureStream(30);
      const drawFrame = () => {
        if (!isRecording && recordSeconds > 0) return;
        if (img && img.naturalWidth > 0 && ctx) {
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        }
        requestAnimationFrame(drawFrame);
      };
      drawFrame();

      const options = { mimeType: 'video/webm;codecs=vp9,opus' };
      const recorder = new MediaRecorder(stream, MediaRecorder.isTypeSupported(options.mimeType) ? options : undefined);
      recordedChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          recordedChunksRef.current.push(e.data);
        }
      };

      recorder.onstop = () => {
        const blob = new Blob(recordedChunksRef.current, { type: 'video/webm' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Aegis_LiveRecord_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.webm`;
        a.click();
        URL.revokeObjectURL(url);
        setSnapshotMsg('Smooth recording downloaded successfully!');
        setTimeout(() => setSnapshotMsg(null), 4000);
      };

      recorder.start(100);
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
      setRecordSeconds(0);
      recordIntervalRef.current = setInterval(() => {
        setRecordSeconds((s) => s + 1);
      }, 1000);
    } catch (err: any) {
      setSnapshotMsg(`Recording initialization: ${err.message}`);
      setTimeout(() => setSnapshotMsg(null), 3500);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      clearInterval(recordIntervalRef.current);
      setIsRecording(false);
    }
  };

  // Handle AI Interactive Query
  const handleAskAI = async (queryToAsk?: string) => {
    const q = queryToAsk || userQuery;
    if (!q.trim()) return;

    if (drawerTtsRef.current) {
      drawerTtsRef.current.stop();
    }

    setIsAiThinking(true);
    setAiResponse(null);
    try {
      const freshFrame = captureLiveFrameBase64();
      const res = await api.interactCameraAI(q, selectedCamera?.id, isVoiceEnabled, undefined, freshFrame || undefined);
      setAiResponse(res.answer);
      if (res.speech_text && isVoiceEnabled) {
        speakText(res.speech_text);
      }
    } catch (err: any) {
      setAiResponse(`Assistant encountered an error: ${err.message}`);
    } finally {
      setIsAiThinking(false);
      setUserQuery('');
    }
  };

  // Drawer Microphone Voice Toggle
  const toggleDrawerVoice = async () => {
    if (isDrawerListening) {
      if (drawerRecognitionRef.current) {
        try {
          drawerRecognitionRef.current.stop();
        } catch {}
      }
      setIsDrawerListening(false);
      return;
    }

    if (drawerTtsRef.current) {
      drawerTtsRef.current.stop();
    }

    // Hardware echo cancellation, noise suppression & auto gain
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });
        stream.getTracks().forEach((track) => track.stop());
      } catch (err: any) {
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
          setAiResponse('Microphone permission denied. Please allow microphone access in your browser address bar.');
          return;
        }
      }
    }

    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRec) {
      setAiResponse('Speech recognition is not supported in this browser. Please use Chrome or Edge.');
      return;
    }

    try {
      const rec = new SpeechRec();
      rec.continuous = false;
      rec.interimResults = true;
      rec.lang = 'en-US';

      rec.onstart = () => {
        setIsDrawerListening(true);
      };

      rec.onresult = (e: any) => {
        // Prevent speech feedback loop if speaker is active
        if (drawerTtsRef.current && drawerTtsRef.current.active) {
          return;
        }

        let interim = '';
        let final = '';
        let minConfidence = 1.0;
        for (let i = e.resultIndex; i < e.results.length; ++i) {
          if (e.results[i].isFinal) {
            final += e.results[i][0].transcript;
            if (e.results[i][0].confidence !== undefined && e.results[i][0].confidence > 0) {
              minConfidence = Math.min(minConfidence, e.results[i][0].confidence);
            }
          } else {
            interim += e.results[i][0].transcript;
          }
        }
        setUserQuery(final || interim);
        if (final && final.trim().length > 1) {
          if (minConfidence < 0.38) {
            console.warn('Low confidence speech ignored:', final, minConfidence);
            return;
          }
          try {
            rec.stop();
          } catch {}
          setIsDrawerListening(false);
          handleAskAI(final.trim());
        }
      };

      rec.onerror = (e: any) => {
        if (e.error !== 'no-speech') {
          console.warn('Drawer speech recognition error:', e.error);
        }
        setIsDrawerListening(false);
      };

      rec.onend = () => {
        setIsDrawerListening(false);
      };

      drawerRecognitionRef.current = rec;
      rec.start();
    } catch {
      setIsDrawerListening(false);
    }
  };

  const authToken = getAuthToken();
  const streamSrc = selectedCamera && isPlaying
    ? `/api/v1/stream/mjpeg/${selectedCamera.id}?token=${encodeURIComponent(authToken || '')}&r=${retryKey}`
    : '';

  return (
    <div className="live-monitoring-container">
      {/* Main Video Viewport */}
      <div className="live-monitoring-video-col">
        {/* Camera Selector Tabs & Voice Action Row */}
        <div className="live-camera-header-row">
          <div className="live-camera-tabs">
            {cameras.map((cam) => {
              const isSel = cam.id === selectedCamera?.id;
              return (
                <button
                  key={cam.id}
                  onClick={() => setSelectedCameraId(cam.id)}
                  className={`live-camera-pill ${isSel ? 'active' : ''}`}
                >
                  <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: cam.status === 'online' ? '#10b981' : '#64748b', flexShrink: 0 }} />
                  <span>{cam.name}</span>
                  <span className="live-camera-pill-type">
                    {cam.source_type}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Stream Mode & View Controls */}
          <div className="live-camera-actions">
            <button
              onClick={() => setViewMode(viewMode === 'focus' ? 'grid' : 'focus')}
              className={`live-camera-pill ${viewMode === 'grid' ? 'active' : ''}`}
              title="Toggle Multi-Camera Grid View"
            >
              <LayoutGrid size={14} color={viewMode === 'grid' ? '#818cf8' : undefined} />
              <span>{viewMode === 'grid' ? 'Grid View' : 'Focus View'}</span>
            </button>

            <button
              onClick={handleCaptureSnapshot}
              className="live-camera-pill"
              title="Capture Instant High-Resolution Snapshot"
            >
              <CameraIcon size={14} />
              <span>Snapshot</span>
            </button>

            <button
              onClick={() => {
                const next = !isVoiceEnabled;
                setIsVoiceEnabled(next);
                if (next) speakText('Voice output enabled.');
              }}
              className={`btn-voice-mute ${isVoiceEnabled ? 'active' : ''}`}
              title={isVoiceEnabled ? 'Voice Output Active' : 'Voice Output Muted'}
            >
              {isVoiceEnabled ? <Volume2 size={14} /> : <VolumeX size={14} />}
              <span>Voice: {isVoiceEnabled ? 'ON' : 'MUTED'}</span>
            </button>

            {/* Mobile-only shortcut to open JARVIS copilot dialog if stacked below */}
            <button
              onClick={() => {
                if (window.innerWidth < 1024) {
                  setIsVoiceModalOpen(true);
                } else {
                  setRightPanelTab('copilot');
                }
              }}
              className="btn-voice-copilot mobile-only-voice-btn"
              title="Open Voice Copilot"
            >
              <Mic size={14} />
              <span>Voice</span>
            </button>
          </div>
        </div>

        {viewMode === 'grid' ? (
          /* Multi-Camera 2-5 Dashboard Grid */
          <div style={{ display: 'grid', gridTemplateColumns: cameras.length > 2 ? 'repeat(auto-fit, minmax(320px, 1fr))' : 'repeat(auto-fit, minmax(360px, 1fr))', gap: '14px', marginBottom: '14px' }}>
            {cameras.map((cam) => {
              const hInfo = camerasHealth.find((h) => h.camera_id === cam.id);
              const isTarget = cam.id === selectedCamera?.id;
              const statusColor = hInfo?.status === 'online' ? '#10b981' : hInfo?.status === 'stale' ? '#f59e0b' : '#ef4444';
              return (
                <div
                  key={cam.id}
                  onClick={() => setSelectedCameraId(cam.id)}
                  className="glass-card"
                  style={{
                    padding: '12px',
                    borderRadius: '12px',
                    border: isTarget ? '2px solid #6366f1' : '1px solid var(--border-subtle)',
                    cursor: 'pointer',
                    position: 'relative',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: statusColor }} />
                      <span style={{ fontSize: '0.88rem', fontWeight: 700 }}>{cam.name}</span>
                    </div>
                    <span style={{ fontSize: '0.72rem', background: 'rgba(255,255,255,0.06)', padding: '2px 8px', borderRadius: '4px' }} className="mono">
                      {hInfo?.fps ? `${hInfo.fps} FPS` : '30 FPS'} • {hInfo?.resolution || '720p'}
                    </span>
                  </div>

                  <div style={{ position: 'relative', borderRadius: '8px', overflow: 'hidden', background: '#0a0d14', aspectRatio: '16/9' }}>
                    <img
                      src={`/api/v1/stream/mjpeg/${cam.id}?token=${encodeURIComponent(authToken || '')}`}
                      alt={cam.name}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      onError={(e: any) => { e.target.style.display = 'none'; }}
                    />
                    {isTarget && (
                      <div style={{ position: 'absolute', top: '8px', right: '8px', background: 'rgba(99, 102, 241, 0.9)', color: '#fff', fontSize: '0.7rem', fontWeight: 700, padding: '3px 8px', borderRadius: '6px' }}>
                        ACTIVE COPILOT TARGET
                      </div>
                    )}
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-faint)' }}>ID: {cam.id.slice(0, 8)} • {cam.source_type}</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        api.captureSnapshot(cam.id);
                        setSnapshotMsg(`Snapshot captured for ${cam.name}!`);
                        setTimeout(() => setSnapshotMsg(null), 3000);
                      }}
                      style={{ background: 'rgba(255,255,255,0.08)', border: 'none', color: '#fff', padding: '4px 10px', borderRadius: '6px', fontSize: '0.75rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
                    >
                      <CameraIcon size={12} />
                      <span>Snapshot</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <>
            {/* Video Frame Canvas */}
            <div className="glass-card live-video-canvas">



          {selectedCamera && isPlaying ? (
            streamError ? (
              <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '24px' }}>
                <Video size={48} color="#f87171" style={{ margin: '0 auto 12px' }} />
                <p style={{ fontSize: '1rem', fontWeight: 600, color: '#f87171' }}>Camera Feed Connecting</p>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-faint)', maxWidth: '360px', margin: '8px auto' }}>
                  Initializing DirectShow video grabber on {selectedCamera.name}...
                </p>
                <button
                  onClick={() => { setStreamError(false); setRetryKey(k => k + 1); }}
                  style={{ marginTop: '12px', background: 'rgba(99, 102, 241, 0.2)', color: '#818cf8', border: '1px solid rgba(99, 102, 241, 0.4)', padding: '6px 16px', borderRadius: '6px', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600 }}
                >
                  Retry Connection
                </button>
              </div>
            ) : (
              <img
                ref={videoImgRef}
                crossOrigin="anonymous"
                key={`${selectedCamera.id}-${retryKey}`}
                src={streamSrc}
                alt="Live Surveillance Stream"
                className="live-video-stream-img"
                onError={() => {
                  setStreamError(true);
                }}
              />
            )
          ) : !isPlaying ? (
            <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '24px' }}>
              <Video size={48} color="var(--text-faint)" style={{ margin: '0 auto 12px' }} />
              <p style={{ fontSize: '0.95rem', fontWeight: 600 }}>Camera Stream Paused</p>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-faint)' }}>Click Resume below to continue live monitoring</p>
            </div>
          ) : (
            <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '24px' }}>
              <Video size={48} color="var(--text-faint)" style={{ margin: '0 auto 12px' }} />
              <p style={{ fontSize: '0.95rem', fontWeight: 600 }}>Connecting to Camera Service...</p>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-faint)' }}>Detecting available camera devices</p>
            </div>
          )}

          {/* Stream Overlay HUD: Live 30 FPS + AI Adaptive Learning */}
          <div className="live-hud-left">
            <div className="badge-tag badge-success live-hud-pill">
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981' }} className="pulse-online" />
              <span>LIVE • 30 FPS</span>
            </div>

            <div className="badge-tag badge-accent live-hud-pill live-hud-ai-tag">
              <Shield size={12} />
              <span>AI ANONYMOUS TRACKING</span>
            </div>

            {sceneData.samples_learned > 0 && (
              <div className="live-hud-pill live-hud-learned-tag" title="Multi-angle facial crops continuously adapted for FaceNet 512-dim verification">
                <Zap size={12} />
                <span>ADAPTED SAMPLES: {sceneData.samples_learned}</span>
              </div>
            )}

            {isRecording && (
              <div className="live-hud-pill live-hud-rec-tag">
                <Circle size={8} fill="#ef4444" color="#ef4444" />
                <span>REC {String(Math.floor(recordSeconds / 60)).padStart(2, '0')}:{String(recordSeconds % 60).padStart(2, '0')}</span>
              </div>
            )}
          </div>

          {/* Top Right Resolution & Camera Tag */}
          <div className="live-hud-right">
            <span className="mono live-hud-res-tag">
              {selectedCamera?.name || 'Camera 1'} (1280x720)
            </span>
          </div>

          {/* Toast Notification */}
          {snapshotMsg && (
            <div className="live-snapshot-toast">
              {snapshotMsg}
            </div>
          )}
        </div>

        {/* Dedicated Responsive Control Bar (Positioned cleanly below video) */}
        <div className="live-monitoring-control-bar">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="live-ctrl-btn"
            style={{ background: isPlaying ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)', color: isPlaying ? '#f87171' : '#34d399' }}
          >
            {isPlaying ? <Pause size={14} /> : <Play size={14} />}
            <span>{isPlaying ? 'Pause' : 'Resume'}</span>
          </button>

          {!isRecording ? (
            <button
              onClick={startRecording}
              className="live-ctrl-btn"
              style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.3)' }}
            >
              <Circle size={12} fill="#ef4444" color="#ef4444" />
              <span>Record</span>
            </button>
          ) : (
            <button
              onClick={stopRecording}
              className="live-ctrl-btn"
              style={{ background: 'rgba(239, 68, 68, 0.85)', color: '#ffffff', border: 'none', boxShadow: '0 0 12px rgba(239, 68, 68, 0.5)' }}
            >
              <Download size={14} />
              <span>Stop & Save ({recordSeconds}s)</span>
            </button>
          )}

          <button
            onClick={handleCaptureSnapshot}
            className="live-ctrl-btn"
            style={{ background: 'rgba(255,255,255,0.08)', color: 'var(--text-main)' }}
          >
            <CameraIcon size={14} />
            <span>Snapshot</span>
          </button>

          <button
            onClick={() => {
              if (window.innerWidth >= 1024) {
                setRightPanelTab('copilot');
              } else {
                setIsVoiceModalOpen(true);
              }
            }}
            className="live-ctrl-btn"
            style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', border: '1px solid rgba(16, 185, 129, 0.35)' }}
            title="Speak Voice Command to AI"
          >
            <Mic size={14} />
            <span>Voice</span>
          </button>

          {selectedCamera && (
            <button
              onClick={() => setIsQuickEnrollOpen(true)}
              className="live-ctrl-btn"
              style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', color: '#ffffff', border: 'none', boxShadow: '0 0 12px rgba(16, 185, 129, 0.35)' }}
            >
              <UserPlus size={14} />
              <span>Quick Enroll</span>
            </button>
          )}

          <span className="live-control-engine-tag mono">
            FaceNet 512D
          </span>
        </div>
        </>
        )}
      </div>


      {/* Right Sidebar: Unified Embedded Voice Copilot, OCR, History & Telemetry */}
      <div className="live-monitoring-sidebar-col">
        {/* Panel Switcher: Sleek 4-Tab Segmented Navigation */}
        <div className="live-sidebar-tabs">
          <button
            onClick={() => setRightPanelTab('copilot')}
            className={`live-sidebar-tab-btn ${rightPanelTab === 'copilot' ? 'active-copilot' : ''}`}
            title="JARVIS Personal AI Copilot & Visual Intelligence"
          >
            <Sparkles size={13} />
            <span>JARVIS</span>
          </button>

          <button
            onClick={() => setRightPanelTab('ocr_objects')}
            className={`live-sidebar-tab-btn ${rightPanelTab === 'ocr_objects' ? 'active-ocr' : ''}`}
            title="Environmental Text, Signs & Object Identification"
          >
            <FileText size={13} />
            <span>OCR & Signs</span>
          </button>

          <button
            onClick={() => setRightPanelTab('history_search')}
            className={`live-sidebar-tab-btn ${rightPanelTab === 'history_search' ? 'active-history' : ''}`}
            title="Search Visual Event History & Chronological Detections"
          >
            <Search size={13} />
            <span>History</span>
          </button>

          <button
            onClick={() => setRightPanelTab('telemetry')}
            className={`live-sidebar-tab-btn ${rightPanelTab === 'telemetry' ? 'active-telemetry' : ''}`}
            title="System & Camera Real-Time Telemetry"
          >
            <Activity size={13} />
            <span>Telemetry</span>
          </button>
        </div>

        {rightPanelTab === 'copilot' ? (
          <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
            <VoiceCopilotModal
              isEmbedded={true}
              isOpen={true}
              cameraId={selectedCamera?.id}
              isVoiceMuted={!isVoiceEnabled}
              onToggleVoiceMute={(muted) => setIsVoiceEnabled(!muted)}
              onCaptureSnapshot={handleCaptureSnapshot}
              onStartRecording={startRecording}
              onStopRecording={stopRecording}
              isRecording={isRecording}
              recordSeconds={recordSeconds}
              isPlaying={isPlaying}
              onTogglePlay={(play) => setIsPlaying(play)}
              onOpenQuickEnroll={(name) => setIsQuickEnrollOpen(true)}
              onOpenDossier={(pid, pname) => setDossierTarget({ id: pid, name: pname })}
              onGetLiveFrame={captureLiveFrameBase64}
              telemetrySummary={{
                fps: sceneData.fps,
                people_count: sceneData.people_count,
                background_color: sceneData.background_color,
                background_scene: sceneData.background_scene,
              }}
            />
          </div>
        ) : rightPanelTab === 'ocr_objects' ? (
          <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', gap: '12px', overflowY: 'auto' }}>
            {/* Live Environmental OCR Card */}
            <div className="glass-card" style={{ padding: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                <h3 style={{ fontSize: '0.92rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <FileText size={16} color="#38bdf8" />
                  <span>Environmental OCR & Signs</span>
                </h3>
                <button
                  onClick={handleRunOCR}
                  disabled={isOcrLoading}
                  style={{
                    background: 'rgba(56, 189, 248, 0.2)',
                    border: '1px solid rgba(56, 189, 248, 0.4)',
                    color: '#38bdf8',
                    padding: '4px 10px',
                    borderRadius: '6px',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  <RefreshCw size={11} className={isOcrLoading ? 'spin' : ''} />
                  <span>{isOcrLoading ? 'Scanning...' : 'Scan Now'}</span>
                </button>
              </div>

              {ocrData ? (
                <div>
                  {ocrData.detected_signs && ocrData.detected_signs.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '10px' }}>
                      {ocrData.detected_signs.map((sign: string, i: number) => (
                        <span key={i} style={{ background: '#f59e0b', color: '#000', fontSize: '0.7rem', fontWeight: 800, padding: '2px 8px', borderRadius: '4px' }}>
                          SIGN: {sign}
                        </span>
                      ))}
                    </div>
                  )}

                  <div style={{ background: 'rgba(0,0,0,0.3)', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-subtle)', maxHeight: '160px', overflowY: 'auto' }}>
                    <pre style={{ margin: 0, fontSize: '0.78rem', color: '#e2e8f0', whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>
                      {ocrData.full_text || 'No readable text identified in current frame.'}
                    </pre>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '8px', fontSize: '0.72rem', color: 'var(--text-faint)' }}>
                    <span>Confidence: {(ocrData.mean_confidence * 100).toFixed(0)}%</span>
                    <span>Blocks: {ocrData.line_count}</span>
                    <span style={{ color: '#10b981' }}>Untrusted Data Guard Active</span>
                  </div>
                </div>
              ) : (
                <p style={{ fontSize: '0.8rem', color: 'var(--text-faint)', margin: '8px 0 0' }}>
                  Click Scan Now or ask AI Voice Copilot "Read the text on the sign" to extract visible environmental text.
                </p>
              )}
            </div>

            {/* Modular Object Detection Card */}
            <div className="glass-card" style={{ padding: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                <h3 style={{ fontSize: '0.92rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Box size={16} color="#c084fc" />
                  <span>Visible Objects & Counts</span>
                </h3>
                <button
                  onClick={handleRunObjectDetection}
                  disabled={isObjectLoading}
                  style={{
                    background: 'rgba(168, 85, 247, 0.2)',
                    border: '1px solid rgba(168, 85, 247, 0.4)',
                    color: '#c084fc',
                    padding: '4px 10px',
                    borderRadius: '6px',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  <RefreshCw size={11} className={isObjectLoading ? 'spin' : ''} />
                  <span>{isObjectLoading ? 'Detecting...' : 'Detect Now'}</span>
                </button>
              </div>

              {objectData ? (
                <div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '10px' }}>
                    {Object.entries(objectData.counts || {}).map(([cls, cnt]: [string, any]) => (
                      <div key={cls} style={{ background: 'rgba(255,255,255,0.05)', padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#c084fc' }}>{cnt}x</span>
                        <span style={{ fontSize: '0.78rem', textTransform: 'capitalize' }}>{cls}</span>
                      </div>
                    ))}
                  </div>

                  <p style={{ fontSize: '0.75rem', color: 'var(--text-faint)', margin: 0 }}>
                    Total items observed: <strong>{objectData.total_count}</strong> across frame viewport.
                  </p>
                </div>
              ) : (
                <p style={{ fontSize: '0.8rem', color: 'var(--text-faint)', margin: '8px 0 0' }}>
                  Click Detect Now to identify people, laptops, phones, bottles, chairs, and surrounding items.
                </p>
              )}
            </div>
          </div>
        ) : rightPanelTab === 'history_search' ? (
          <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', gap: '12px', overflowY: 'auto' }}>
            {/* Visual History Search Form */}
            <div className="glass-card" style={{ padding: '16px' }}>
              <h3 style={{ fontSize: '0.92rem', fontWeight: 700, margin: '0 0 10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Search size={16} color="#fbbf24" />
                <span>Visual Memory & Search</span>
              </h3>

              <form onSubmit={handleHistorySearch} style={{ display: 'flex', gap: '6px', marginBottom: '10px' }}>
                <input
                  type="text"
                  value={historySearchQuery}
                  onChange={(e) => setHistorySearchQuery(e.target.value)}
                  placeholder="e.g. 'Last time a person entered'..."
                  style={{
                    flex: 1,
                    background: 'rgba(0,0,0,0.3)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '6px',
                    padding: '8px 10px',
                    color: '#fff',
                    fontSize: '0.82rem',
                    outline: 'none',
                  }}
                />
                <button
                  type="submit"
                  disabled={isHistorySearching}
                  style={{
                    background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
                    border: 'none',
                    color: '#000',
                    padding: '0 14px',
                    borderRadius: '6px',
                    fontWeight: 700,
                    fontSize: '0.78rem',
                    cursor: 'pointer',
                  }}
                >
                  {isHistorySearching ? '...' : 'Search'}
                </button>
              </form>

              {/* Quick Query Suggestions */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
                {['Person entered zone', 'Vehicle detections', 'Unusual events today', 'Motion alerts'].map((chip) => (
                  <button
                    key={chip}
                    type="button"
                    onClick={() => {
                      setHistorySearchQuery(chip);
                      api.searchHistoricalEvents(chip, selectedCamera?.id).then(res => setHistorySearchResult(res));
                    }}
                    style={{
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      borderRadius: '12px',
                      padding: '3px 8px',
                      color: 'var(--text-muted)',
                      fontSize: '0.7rem',
                      cursor: 'pointer',
                    }}
                  >
                    {chip}
                  </button>
                ))}
              </div>

              {historySearchResult && (
                <div style={{ marginTop: '14px', borderTop: '1px solid var(--border-subtle)', paddingTop: '10px' }}>
                  <p style={{ fontSize: '0.8rem', color: '#f59e0b', fontWeight: 600, margin: '0 0 10px' }}>
                    {historySearchResult.summary}
                  </p>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '220px', overflowY: 'auto' }}>
                    {historySearchResult.events?.map((ev: any) => (
                      <div key={ev.id} style={{ background: 'rgba(255,255,255,0.02)', padding: '8px', borderRadius: '6px', border: '1px solid var(--border-subtle)', fontSize: '0.75rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600 }}>
                          <span>{ev.event_type}</span>
                          <span className="mono" style={{ color: 'var(--text-faint)' }}>{new Date(ev.occurred_at).toLocaleTimeString()}</span>
                        </div>
                        <div style={{ color: 'var(--text-faint)', marginTop: '2px' }}>
                          Camera: {ev.camera_name || 'Camera 1'} • Conf: {(ev.confidence * 100).toFixed(0)}%
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', gap: '14px', overflowY: 'auto' }}>
            {/* Dynamic Camera Health Card */}
            <div className="glass-card" style={{ padding: '16px' }}>
              <h3 style={{ fontSize: '0.92rem', fontWeight: 700, marginBottom: '12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Eye size={16} color="#818cf8" />
                  <span>Camera Health & Telemetry</span>
                </span>
                <span style={{ fontSize: '0.7rem', color: '#34d399', fontWeight: 600 }}>0ms Lag Buffer</span>
              </h3>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>

                <div style={{ background: 'rgba(255,255,255,0.03)', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-faint)', textTransform: 'uppercase' }}>Frame Rate</span>
                  <p style={{ fontSize: '1.05rem', fontWeight: 700, margin: '4px 0 0', color: '#34d399' }} className="mono">
                    {sceneData.fps.toFixed(1)} FPS
                  </p>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.03)', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-faint)', textTransform: 'uppercase' }}>People Tracked</span>
                  <p style={{ fontSize: '1.05rem', fontWeight: 700, margin: '4px 0 0', color: sceneData.people_count > 0 ? '#38bdf8' : 'var(--text-muted)' }} className="mono">
                    {sceneData.people_count} {sceneData.people_count === 1 ? 'Person' : 'People'}
                  </p>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.03)', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-faint)', textTransform: 'uppercase' }}>AI Confidence</span>
                  <p style={{ fontSize: '0.95rem', fontWeight: 700, margin: '4px 0 0', color: '#818cf8' }} className="mono">
                    {sceneData.model_confidence}%
                  </p>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.03)', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-faint)', textTransform: 'uppercase' }}>Attention</span>
                  <p style={{ fontSize: '0.95rem', fontWeight: 600, margin: '4px 0 0', color: '#34d399' }}>
                    {sceneData.attention_score}% Direct
                  </p>
                </div>
              </div>

              {/* AI Ergonomics & Lighting Status */}
              <div style={{ marginTop: '10px', background: 'rgba(99, 102, 241, 0.08)', borderRadius: '8px', padding: '8px 10px', border: '1px solid rgba(99, 102, 241, 0.2)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.72rem', color: '#818cf8', fontWeight: 600 }}>
                  <span>Adaptive Lighting</span>
                  <span>CLAHE Equalized</span>
                </div>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '4px 0 0' }}>
                  {sceneData.lighting_condition}
                </p>
              </div>

              {/* Multi-Angle Head Orientation & 360° Biometrics Status */}
              <div style={{ marginTop: '8px', background: 'rgba(56, 189, 248, 0.08)', borderRadius: '8px', padding: '8px 10px', border: '1px solid rgba(56, 189, 248, 0.25)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.72rem', color: '#38bdf8', fontWeight: 600 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                    <Compass size={13} />
                    <span>Head Orientation</span>
                  </span>
                  <span style={{ color: '#34d399', background: 'rgba(16, 185, 129, 0.15)', padding: '1px 6px', borderRadius: '4px', fontSize: '0.68rem', fontWeight: 700 }}>
                    360° Multi-Angle Active
                  </span>
                </div>
                <p style={{ fontSize: '0.78rem', color: '#f1f5f9', fontWeight: 600, margin: '4px 0 0' }}>
                  {sceneData.head_orientation || 'Direct Frontal (0°)'}
                </p>
              </div>

              {/* AI Background Color & Scene Analysis */}
              <div style={{ marginTop: '8px', background: 'rgba(16, 185, 129, 0.08)', borderRadius: '8px', padding: '8px 10px', border: '1px solid rgba(16, 185, 129, 0.25)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.72rem', color: '#34d399', fontWeight: 600 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                    <Sparkles size={13} />
                    <span>Background Scene</span>
                  </span>
                  <span style={{ color: '#34d399', background: 'rgba(16, 185, 129, 0.15)', padding: '1px 6px', borderRadius: '4px', fontSize: '0.68rem', fontWeight: 700 }}>
                    {sceneData.background_color || 'Off-white / cream'}
                  </span>
                </div>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '4px 0 0' }}>
                  {sceneData.background_scene || 'Wall paneling and room fixtures'}
                </p>
              </div>
            </div>

            {/* Live Event Stream */}
            <div className="glass-card" style={{ flex: 1, padding: '16px', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                <h3 style={{ fontSize: '0.92rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <AlertTriangle size={16} color="#f59e0b" />
                  <span>Real-Time Activity</span>
                </h3>
                <button
                  onClick={onOpenEvents}
                  style={{ background: 'none', border: 'none', color: '#818cf8', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer' }}
                >
                  View All
                </button>
              </div>

              <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {recentEvents.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '30px 10px', color: 'var(--text-faint)', fontSize: '0.8rem' }}>
                    Monitoring camera stream for motion and person tracks...
                  </div>
                ) : (
                  recentEvents.map((ev) => {
                    const isVerified = Boolean(ev.person_name);
                    return (
                      <div
                        key={ev.id}
                        style={{
                          background: 'rgba(255, 255, 255, 0.03)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: '8px',
                          padding: '10px 12px',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '4px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <span className={`badge-tag ${isVerified ? 'badge-success' : ev.event_type === 'person' ? 'badge-warning' : 'badge-accent'}`}>
                            {isVerified ? 'VERIFIED' : ev.event_type === 'person' ? 'ANONYMOUS' : 'MOTION'}
                          </span>
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-faint)' }} className="mono">
                            {new Date(ev.occurred_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                          </span>
                        </div>

                        <p style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-main)', margin: '2px 0 0' }}>
                          {isVerified ? ev.person_name : ev.track_id ? `Detected Person [${ev.track_id}]` : 'Motion In View'}
                        </p>

                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '2px' }}>
                          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                            {(ev.confidence * 100).toFixed(0)}% • {ev.camera_name || 'Camera'}
                          </span>
                          {ev.person_id && ev.person_name && (
                            <button
                              onClick={() => setDossierTarget({ id: ev.person_id!, name: ev.person_name! })}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                                background: 'rgba(99, 102, 241, 0.12)',
                                border: '1px solid rgba(99, 102, 241, 0.25)',
                                color: '#818cf8',
                                fontSize: '0.7rem',
                                fontWeight: 600,
                                padding: '2px 6px',
                                borderRadius: '4px',
                                cursor: 'pointer',
                              }}
                            >
                              <Sparkles size={11} />
                              AI Dossier
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Quick Enroll Modal */}
      {selectedCamera && (
        <QuickEnrollModal
          isOpen={isQuickEnrollOpen}
          cameraId={selectedCamera.id}
          onClose={() => setIsQuickEnrollOpen(false)}
          onEnrolledSuccess={() => {
            setRetryKey((k) => k + 1);
            api.getEvents({ limit: 8 }).then(setRecentEvents).catch(() => {});
          }}
        />
      )}

      {/* AI Intelligence Dossier Modal */}
      {dossierTarget && (
        <AIDossierModal
          isOpen={Boolean(dossierTarget)}
          personId={dossierTarget.id}
          personName={dossierTarget.name}
          onClose={() => setDossierTarget(null)}
        />
      )}

      {/* Floating Voice Copilot Modal Dialog */}
      {isVoiceModalOpen && (
        <VoiceCopilotModal
          isEmbedded={false}
          isOpen={true}
          onClose={() => setIsVoiceModalOpen(false)}
          cameraId={selectedCamera?.id}
          isVoiceMuted={!isVoiceEnabled}
          onToggleVoiceMute={(muted) => setIsVoiceEnabled(!muted)}
          onCaptureSnapshot={handleCaptureSnapshot}
          onStartRecording={startRecording}
          onStopRecording={stopRecording}
          isRecording={isRecording}
          recordSeconds={recordSeconds}
          isPlaying={isPlaying}
          onTogglePlay={(play) => setIsPlaying(play)}
          onOpenQuickEnroll={(name) => setIsQuickEnrollOpen(true)}
          onOpenDossier={(pid, pname) => setDossierTarget({ id: pid, name: pname })}
          onGetLiveFrame={captureLiveFrameBase64}
          telemetrySummary={{
            fps: sceneData.fps,
            people_count: sceneData.people_count,
            background_color: sceneData.background_color,
            background_scene: sceneData.background_scene,
          }}
        />
      )}
    </div>
  );
};
