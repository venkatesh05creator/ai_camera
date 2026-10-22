import React, { useEffect, useRef, useState } from 'react';
import {
  Mic,
  MicOff,
  Send,
  Volume2,
  VolumeX,
  Maximize2,
  Minimize2,
  Video,
  VideoOff,
  TrendingUp,
  TrendingDown,
  ExternalLink,
  ShieldCheck,
  Cpu,
  HardDrive,
  Battery,
  Clock,
  Sparkles,
  RefreshCw,
  Play,
  MessageSquare,
  Activity,
  Layers,
  CheckCircle2,
} from 'lucide-react';
import { api } from '../services/api';
import { Camera } from '../types';

interface HolographicHUDProps {
  cameras: Camera[];
}

interface StockItem {
  sym: string;
  name: string;
  price: number;
  pct: number;
  mom: number;
  above: boolean;
  spark: number[];
  signal: string;
  err?: boolean;
  stale?: boolean;
}

interface ChatTurn {
  id: string;
  sender: 'user' | 'jarvis' | 'sys';
  text: string;
  timestamp: string;
  action?: string;
}

export const HolographicHUDView: React.FC<HolographicHUDProps> = ({ cameras }) => {
  // Voice & Copilot State
  const [assistantState, setAssistantState] = useState<'idle' | 'listening' | 'thinking' | 'speaking'>('idle');
  const [inputQuery, setInputQuery] = useState('');
  const [isVoiceMuted, setIsVoiceMuted] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [lastAction, setLastAction] = useState<string | null>(null);
  const [speechTranscript, setSpeechTranscript] = useState('');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showCameraPip, setShowCameraPip] = useState(true);
  const [selectedCameraId, setSelectedCameraId] = useState<string>(cameras[0]?.id || '0');

  // Telemetry & Market State
  const [stocks, setStocks] = useState<StockItem[]>([]);
  const [sysVitals, setSysVitals] = useState({
    cpu: 18,
    ram: 42,
    disk: 45,
    free: 140,
    bat: 95,
    plug: true,
    up: 120,
  });
  const [currentTime, setCurrentTime] = useState('');
  const [currentDate, setCurrentDate] = useState('');
  const [quantumLinkOk, setQuantumLinkOk] = useState(true);

  // Chat History
  const [chatLog, setChatLog] = useState<ChatTurn[]>([
    {
      id: '1',
      sender: 'sys',
      text: 'Aegis Holographic 3D HUD online. Neural visual pipelines linked at 30 FPS.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
    {
      id: '2',
      sender: 'jarvis',
      text: 'Good day. Visual surveillance armed. Speak or type to execute executive commands, market scans, or vision checks.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

  // Canvas Refs
  const reactorCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const waveCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const recognitionRef = useRef<any>(null);
  const animFrameRef = useRef<number | null>(null);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const audioLevelRef = useRef<number>(0.1);

  // Quick Action Chips
  const quickPrompts = [
    { label: '💬 Open WhatsApp', query: 'Can you open WhatsApp?' },
    { label: '▶️ Play YouTube', query: 'Play synthwave music on YouTube' },
    { label: '📈 Market Briefing', query: 'Stock market report and technical briefing' },
    { label: '📸 Take Snapshot', query: 'Take a snapshot from the camera' },
    { label: '🕒 Local Time', query: 'What is the current time and date?' },
    { label: '🛡️ Security Status', query: 'What is the active security and perimeter status?' },
    { label: '🔍 Describe Scene', query: 'Describe what you see in the camera and background' },
  ];

  // Sound Chime Player
  const playHudSound = (type: 'listen' | 'action' | 'done') => {
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      if (type === 'listen') {
        osc.type = 'sine';
        osc.frequency.setValueAtTime(440, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.12);
        gain.gain.setValueAtTime(0.06, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.22);
      } else if (type === 'action') {
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(523.25, ctx.currentTime);
        osc.frequency.setValueAtTime(659.25, ctx.currentTime + 0.08);
        osc.frequency.setValueAtTime(783.99, ctx.currentTime + 0.16);
        gain.gain.setValueAtTime(0.08, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.32);
      } else {
        osc.type = 'sine';
        osc.frequency.setValueAtTime(659.25, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(523.25, ctx.currentTime + 0.15);
        gain.gain.setValueAtTime(0.05, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
      }

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.35);
    } catch {
      // Audio autoplay policy handled
    }
  };

  // Clock Update
  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setCurrentTime(now.toLocaleTimeString([], { hour12: false }));
      setCurrentDate(
        now.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).toUpperCase()
      );
    };
    updateClock();
    const timer = setInterval(updateClock, 1000);
    return () => clearInterval(timer);
  }, []);

  // Poll Telemetry & Market Watchlist from Backend
  useEffect(() => {
    const fetchState = async () => {
      try {
        const res = await fetch('/api/state', { cache: 'no-store' });
        if (res.ok) {
          const data = await res.json();
          if (data.stocks) setStocks(data.stocks);
          if (data.sys) setSysVitals(data.sys);
          setQuantumLinkOk(true);
        } else {
          setQuantumLinkOk(false);
        }
      } catch {
        setQuantumLinkOk(false);
      }
    };

    fetchState();
    const interval = setInterval(fetchState, 1500);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll chat log
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [chatLog, speechTranscript]);

  // Speech Recognition Setup
  useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = navigator.language || 'en-US';

      recognition.onstart = () => {
        setIsListening(true);
        setAssistantState('listening');
        playHudSound('listen');
      };

      recognition.onresult = (event: any) => {
        let interim = '';
        let final = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            final += event.results[i][0].transcript;
          } else {
            interim += event.results[i][0].transcript;
          }
        }
        setSpeechTranscript(final || interim);

        if (final && final.trim().length >= 2) {
          handleSendQuery(final.trim());
          setSpeechTranscript('');
          try {
            recognition.stop();
          } catch {}
        }
      };

      recognition.onerror = () => {
        setIsListening(false);
        if (assistantState === 'listening') setAssistantState('idle');
      };

      recognition.onend = () => {
        setIsListening(false);
        if (assistantState === 'listening') setAssistantState('idle');
      };

      recognitionRef.current = recognition;
    }

    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {}
      }
    };
  }, [assistantState]);

  // Toggle Voice Recognition
  const toggleListening = () => {
    if (isListening) {
      try {
        recognitionRef.current?.stop();
      } catch {}
      setIsListening(false);
      setAssistantState('idle');
    } else {
      try {
        // Cancel ongoing TTS before listening
        if ('speechSynthesis' in window) {
          window.speechSynthesis.cancel();
        }
        recognitionRef.current?.start();
      } catch (e) {
        console.warn('Microphone start error:', e);
      }
    }
  };

  // Text-To-Speech Playback
  const speakAI = (text: string) => {
    if (isVoiceMuted || !('speechSynthesis' in window)) return;
    try {
      window.speechSynthesis.cancel();
      const cleanText = text.replace(/[*#_`]/g, '').trim();
      const utterance = new SpeechSynthesisUtterance(cleanText);
      utterance.rate = 1.05;
      utterance.pitch = 0.98;

      const voices = window.speechSynthesis.getVoices();
      const naturalVoice = voices.find(
        (v) =>
          (v.name.includes('Natural') || v.name.includes('Neural') || v.name.includes('David') || v.name.includes('Google UK')) &&
          v.lang.startsWith('en')
      ) || voices.find((v) => v.lang.startsWith('en'));

      if (naturalVoice) utterance.voice = naturalVoice;

      utterance.onstart = () => {
        setAssistantState('speaking');
      };
      utterance.onend = () => {
        setAssistantState('idle');
      };
      utterance.onerror = () => {
        setAssistantState('idle');
      };

      window.speechSynthesis.speak(utterance);
    } catch {
      setAssistantState('idle');
    }
  };

  // Dispatch Query & Actions
  const handleSendQuery = async (queryToSend: string) => {
    const q = queryToSend.trim();
    if (!q) return;

    // Add user turn to chat
    const userTurn: ChatTurn = {
      id: Date.now().toString(),
      sender: 'user',
      text: q,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    setChatLog((prev) => [...prev, userTurn]);
    setInputQuery('');
    setAssistantState('thinking');

    try {
      const historyPayload = chatLog.slice(-6).map((m) => ({
        role: m.sender === 'user' ? 'user' : 'ai',
        content: m.text,
      }));

      const res = await api.interactCameraAI(
        q,
        selectedCameraId,
        !isVoiceMuted,
        historyPayload
      );

      // Handle Executive Action Dispatcher
      let actionDesc: string | undefined = undefined;
      if (res.action === 'open_url') {
        if (res.action_payload?.url) {
          window.open(res.action_payload.url, '_blank');
        }
        playHudSound('action');
        actionDesc = res.action_payload?.label || 'Opened Link';
      } else if (res.action === 'app_launch') {
        playHudSound('action');
        actionDesc = res.action_payload?.label || 'Application Launched';
      } else if (res.action === 'market_briefing') {
        playHudSound('action');
        actionDesc = 'Market Watchlist Synchronized';
      } else if (res.action === 'snapshot') {
        playHudSound('action');
        actionDesc = 'Camera Snapshot Captured';
      } else if (res.action === 'mute') {
        setIsVoiceMuted(true);
        actionDesc = 'Voice Copilot Muted';
      } else if (res.action === 'unmute') {
        setIsVoiceMuted(false);
        actionDesc = 'Voice Copilot Active';
      }

      if (actionDesc) {
        setLastAction(actionDesc);
        setTimeout(() => setLastAction(null), 4500);
      }

      // Add JARVIS response to chat
      const aiTurn: ChatTurn = {
        id: (Date.now() + 1).toString(),
        sender: 'jarvis',
        text: res.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        action: actionDesc,
      };
      setChatLog((prev) => [...prev, aiTurn]);

      // Speak aloud
      if (res.speech_text && !isVoiceMuted) {
        speakAI(res.speech_text);
      } else {
        setAssistantState('idle');
      }
    } catch (err: any) {
      const errTurn: ChatTurn = {
        id: (Date.now() + 1).toString(),
        sender: 'sys',
        text: `Command error: ${err.message || 'Could not communicate with JARVIS core.'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setChatLog((prev) => [...prev, errTurn]);
      setAssistantState('idle');
    }
  };

  // 3D Canvas Reactor Animation
  useEffect(() => {
    const canvas = reactorCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let startTime = performance.now();

    const particles = Array.from({ length: 48 }, () => ({
      angle: Math.random() * Math.PI * 2,
      dist: 50 + Math.random() * 85,
      speed: 0.005 + Math.random() * 0.015,
      radius: 1 + Math.random() * 2,
      alpha: 0.2 + Math.random() * 0.7,
    }));

    const renderReactor = (time: number) => {
      const elapsed = (time - startTime) / 1000;
      const w = canvas.width;
      const h = canvas.height;
      const cx = w / 2;
      const cy = h / 2;

      ctx.clearRect(0, 0, w, h);

      // State-dependent color & glow
      let baseHue = 195; // Cyan
      let pulseMultiplier = 1.0;
      let rotSpeed = 1.0;

      if (assistantState === 'listening') {
        baseHue = 145; // Emerald Green
        pulseMultiplier = 1.4 + 0.3 * Math.sin(elapsed * 12);
        rotSpeed = 1.8;
      } else if (assistantState === 'thinking') {
        baseHue = 270; // Purple / Indigo
        pulseMultiplier = 1.2 + 0.4 * Math.sin(elapsed * 8);
        rotSpeed = 3.2;
      } else if (assistantState === 'speaking') {
        baseHue = 205; // Electric Azure
        pulseMultiplier = 1.5 + 0.5 * Math.abs(Math.sin(elapsed * 10));
        rotSpeed = 2.2;
      }

      // Outer Flux Ring
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(elapsed * 0.25 * rotSpeed);
      ctx.strokeStyle = `hsla(${baseHue}, 90%, 65%, 0.35)`;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([12, 10, 4, 10]);
      ctx.beginPath();
      ctx.arc(0, 0, 110 * pulseMultiplier * 0.85, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      // Middle Segmented Target Ring
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(-elapsed * 0.45 * rotSpeed);
      ctx.strokeStyle = `hsla(${baseHue}, 100%, 70%, 0.65)`;
      ctx.lineWidth = 2.5;
      ctx.setLineDash([35, 14]);
      ctx.beginPath();
      ctx.arc(0, 0, 85 * pulseMultiplier * 0.85, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      // Inner Counter-Rotating Dial
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(elapsed * 0.8 * rotSpeed);
      ctx.strokeStyle = `hsla(${baseHue}, 95%, 75%, 0.8)`;
      ctx.lineWidth = 1.8;
      ctx.setLineDash([6, 6]);
      ctx.beginPath();
      ctx.arc(0, 0, 60 * pulseMultiplier * 0.85, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      // Rotating Neural Orbit Particles
      for (const p of particles) {
        p.angle += p.speed * rotSpeed;
        const px = cx + Math.cos(p.angle) * p.dist * (0.8 + 0.2 * pulseMultiplier);
        const py = cy + Math.sin(p.angle) * p.dist * (0.8 + 0.2 * pulseMultiplier);
        ctx.fillStyle = `hsla(${baseHue}, 100%, 80%, ${p.alpha})`;
        ctx.beginPath();
        ctx.arc(px, py, p.radius, 0, Math.PI * 2);
        ctx.fill();
      }

      // 3D Wireframe Globe Latitude Rings
      ctx.save();
      ctx.translate(cx, cy);
      ctx.strokeStyle = `hsla(${baseHue}, 80%, 60%, 0.3)`;
      ctx.lineWidth = 1;
      for (let lat = -40; lat <= 40; lat += 20) {
        const rad = Math.cos((lat * Math.PI) / 180) * 45;
        const yOff = Math.sin((lat * Math.PI) / 180) * 25;
        ctx.beginPath();
        ctx.ellipse(0, yOff, rad, rad * 0.45, 0, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.restore();

      // Glowing Center ARC Core
      const grad = ctx.createRadialGradient(cx, cy, 2, cx, cy, 38 * pulseMultiplier);
      grad.addColorStop(0, `hsla(${baseHue}, 100%, 95%, 1)`);
      grad.addColorStop(0.35, `hsla(${baseHue}, 90%, 75%, 0.75)`);
      grad.addColorStop(0.7, `hsla(${baseHue}, 90%, 55%, 0.3)`);
      grad.addColorStop(1, `hsla(${baseHue}, 90%, 45%, 0)`);

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, 38 * pulseMultiplier, 0, Math.PI * 2);
      ctx.fill();

      // Pulsing Center Core Ring
      ctx.strokeStyle = `hsla(${baseHue}, 100%, 90%, 0.9)`;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(cx, cy, 22 * pulseMultiplier, 0, Math.PI * 2);
      ctx.stroke();

      animFrameRef.current = requestAnimationFrame(renderReactor);
    };

    animFrameRef.current = requestAnimationFrame(renderReactor);

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [assistantState]);

  // Audio Oscilloscope Wave Animation
  useEffect(() => {
    const canvas = waveCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;
    let t = 0;

    const renderWave = () => {
      const w = canvas.width;
      const h = canvas.height;
      const mid = h / 2;
      t += 0.04;

      ctx.clearRect(0, 0, w, h);

      // Centerline
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.2)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, mid);
      ctx.lineTo(w, mid);
      ctx.stroke();

      let amp = 0.12;
      let waveHue = 195;
      if (assistantState === 'listening') {
        amp = 0.55 + 0.3 * Math.sin(t * 8);
        waveHue = 145;
      } else if (assistantState === 'thinking') {
        amp = 0.35 + 0.2 * Math.sin(t * 5);
        waveHue = 270;
      } else if (assistantState === 'speaking') {
        amp = 0.65 + 0.35 * Math.sin(t * 11) * Math.cos(t * 6);
        waveHue = 205;
      }

      // Draw Multi-tier Neon Sine Waves
      for (let k = 0; k < 3; k++) {
        ctx.beginPath();
        for (let x = 0; x <= w; x += 4) {
          const nx = x / w;
          const env = Math.sin(nx * Math.PI);
          const y =
            mid +
            Math.sin(nx * (10 + k * 6) + t * (2 + k) * 1.5) * (h * 0.4) * amp * env +
            Math.sin(nx * 32 + t * 4) * (h * 0.08) * amp;
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = `hsla(${waveHue + k * 10}, 95%, ${70 - k * 12}%, ${0.9 - k * 0.25})`;
        ctx.lineWidth = 2.2 - k * 0.5;
        ctx.stroke();
      }

      animId = requestAnimationFrame(renderWave);
    };

    animId = requestAnimationFrame(renderWave);

    return () => cancelAnimationFrame(animId);
  }, [assistantState]);

  return (
    <div className={`holographic-hud-wrapper ${isFullscreen ? 'hud-fullscreen' : ''}`}>
      {/* HUD Header Bar */}
      <header className="hud-header">
        <div className="hud-header-left">
          <div className="hud-reactor-badge">
            <span className="pulse-dot" />
            <span className="hud-title-text">J.A.R.V.I.S MARK VII</span>
          </div>
          <span className="hud-tag">EXECUTIVE COMMAND · HYBRID AI</span>
        </div>

        <div className="hud-header-center">
          <div className="hud-clock mono">{currentTime || '00:00:00'}</div>
          <div className="hud-date mono">{currentDate || 'FRIDAY, 23 OCTOBER 2026'}</div>
        </div>

        <div className="hud-header-right">
          <div className={`hud-quantum-pill ${quantumLinkOk ? 'link-ok' : 'link-standby'}`}>
            <span className="quantum-orb" />
            <span className="mono">{quantumLinkOk ? 'QUANTUM LINK OK' : 'LOCAL STANDBY'}</span>
          </div>

          <button
            onClick={() => setIsVoiceMuted(!isVoiceMuted)}
            className="hud-tool-btn"
            title={isVoiceMuted ? 'Unmute Voice' : 'Mute Voice'}
          >
            {isVoiceMuted ? <VolumeX size={16} color="#f87171" /> : <Volume2 size={16} color="#38bdf8" />}
          </button>

          <button
            onClick={() => setShowCameraPip(!showCameraPip)}
            className={`hud-tool-btn ${showCameraPip ? 'btn-active' : ''}`}
            title="Toggle Live Camera PiP Feed"
          >
            {showCameraPip ? <Video size={16} color="#10b981" /> : <VideoOff size={16} color="var(--text-muted)" />}
          </button>

          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="hud-tool-btn"
            title="Toggle Fullscreen"
          >
            {isFullscreen ? <Minimize2 size={16} color="#38bdf8" /> : <Maximize2 size={16} color="#38bdf8" />}
          </button>
        </div>
      </header>

      {/* Main Holographic Grid */}
      <div className="hud-grid-layout">
        {/* ================= LEFT COLUMN: AUDIO & NEURAL PIPELINE ================= */}
        <section className="hud-col hud-col-left">
          {/* Audio Waveform Oscilloscope */}
          <div className="hud-panel">
            <div className="hud-panel-title">
              <Activity size={14} color="#38bdf8" />
              <span>VOICE FREQUENCY OSCILLOSCOPE</span>
            </div>
            <div className="wave-canvas-container">
              <canvas ref={waveCanvasRef} width={340} height={70} className="wave-canvas" />
            </div>
            <div className="hud-panel-subbar">
              <span className="mono status-indicator">{assistantState.toUpperCase()}</span>
              <span className="mono stream-status">MIC STREAM ACTIVE</span>
            </div>
          </div>

          {/* Neural Core Pipeline */}
          <div className="hud-panel">
            <div className="hud-panel-title">
              <Layers size={14} color="#818cf8" />
              <span>NEURAL CORE PIPELINE</span>
            </div>

            <div className="hud-nodes-row">
              <div className={`hud-node-pill ${isListening ? 'active' : ''}`}>
                <span className="node-label">MIC</span>
                <span className="node-sub">Stream</span>
              </div>
              <div className={`hud-node-pill ${assistantState === 'listening' ? 'active' : ''}`}>
                <span className="node-label">EAR</span>
                <span className="node-sub">Whisper</span>
              </div>
              <div className={`hud-node-pill ${assistantState === 'thinking' ? 'active' : ''}`}>
                <span className="node-label">MIND</span>
                <span className="node-sub">Groq 3.3</span>
              </div>
              <div className={`hud-node-pill ${lastAction ? 'active' : ''}`}>
                <span className="node-label">HANDS</span>
                <span className="node-sub">Execute</span>
              </div>
              <div className={`hud-node-pill ${assistantState === 'speaking' ? 'active' : ''}`}>
                <span className="node-label">VOICE</span>
                <span className="node-sub">Speech</span>
              </div>
            </div>

            <div className="hud-kv-table mono">
              <div className="kv-row">
                <span className="kv-key">ENGINE MODEL</span>
                <span className="kv-val">Groq / Llama-3.3 + Aegis Local</span>
              </div>
              <div className="kv-row">
                <span className="kv-key">SPEECH LATENCY</span>
                <span className="kv-val">0.32 s</span>
              </div>
              <div className="kv-row">
                <span className="kv-key">COGNITION TIME</span>
                <span className="kv-val">0.28 s</span>
              </div>
              <div className="kv-row">
                <span className="kv-key">LAST COMMAND</span>
                <span className="kv-val">{lastAction || 'Perimeter Scanner'}</span>
              </div>
              <div className="kv-row">
                <span className="kv-key">BIOMETRIC PRIVACY</span>
                <span className="kv-val" style={{ color: '#10b981' }}>FaceNet 512-dim AES-256</span>
              </div>
              <div className="kv-row">
                <span className="kv-key">FAILOVER</span>
                <span className="kv-val" style={{ color: '#38bdf8' }}>AUTO-SWITCH HYBRID</span>
              </div>
            </div>
          </div>

          {/* Telemetry Logs & Live Chat Transcript */}
          <div className="hud-panel hud-panel-chat flex-1">
            <div className="hud-panel-title">
              <MessageSquare size={14} color="#38bdf8" />
              <span>TELEMETRY LOGS & COPILOT CHAT</span>
            </div>

            <div ref={chatScrollRef} className="hud-chat-scroll">
              {chatLog.map((turn) => (
                <div key={turn.id} className={`hud-chat-msg msg-${turn.sender}`}>
                  <div className="msg-meta mono">
                    <span className="sender-tag">
                      {turn.sender === 'user' ? 'YOU ▸' : turn.sender === 'jarvis' ? 'JARVIS ▸' : 'SYS ▸'}
                    </span>
                    <span className="timestamp">{turn.timestamp}</span>
                  </div>
                  <div className="msg-body">{turn.text}</div>
                  {turn.action && (
                    <div className="msg-action-badge">
                      <CheckCircle2 size={12} color="#10b981" />
                      <span>{turn.action}</span>
                    </div>
                  )}
                </div>
              ))}

              {speechTranscript && (
                <div className="hud-chat-msg msg-user listening-interim">
                  <span className="sender-tag">INTERIM ▸</span>
                  <span className="interim-text">"{speechTranscript}"</span>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* ================= CENTER COLUMN: 3D REACTOR CORE & VOICE CONSOLE ================= */}
        <section className="hud-col hud-col-center">
          {/* Action Notification Banner */}
          {lastAction && (
            <div className="hud-action-banner">
              <Sparkles size={16} color="#38bdf8" />
              <span>{lastAction}</span>
            </div>
          )}

          {/* 3D Reactor Core Interactive Canvas */}
          <div className="reactor-core-wrapper" onClick={toggleListening} title="Click to toggle Voice Listening">
            <canvas ref={reactorCanvasRef} width={340} height={340} className="reactor-core-canvas" />

            {/* Status Pulse Center Label */}
            <div className="reactor-status-box">
              <div className={`status-main-label mono status-${assistantState}`}>
                {assistantState.toUpperCase()}
              </div>
              <div className="status-sub-label mono">
                {assistantState === 'listening'
                  ? 'LISTENING TO SPEECH...'
                  : assistantState === 'thinking'
                  ? 'ANALYZING INTENT...'
                  : assistantState === 'speaking'
                  ? 'SPEAKING RESPONSE...'
                  : 'QUANTUM CORE ACTIVE'}
              </div>
            </div>
          </div>

          {/* Live Interactive Voice & Text Console */}
          <div className="hud-interactive-console">
            {/* Quick Trigger Chips */}
            <div className="quick-chips-row">
              {quickPrompts.map((chip, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendQuery(chip.query)}
                  className="quick-chip-btn"
                >
                  {chip.label}
                </button>
              ))}
            </div>

            {/* Voice & Text Input Bar */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendQuery(inputQuery);
              }}
              className="hud-input-bar"
            >
              <button
                type="button"
                onClick={toggleListening}
                className={`hud-mic-trigger ${isListening ? 'mic-listening' : ''}`}
                title={isListening ? 'Stop listening' : 'Start voice recognition'}
              >
                {isListening ? <Mic size={20} color="#10b981" /> : <Mic size={20} color="#38bdf8" />}
              </button>

              <input
                type="text"
                value={inputQuery}
                onChange={(e) => setInputQuery(e.target.value)}
                placeholder={
                  isListening
                    ? 'Listening... Speak your command'
                    : 'Ask JARVIS: "Can you open WhatsApp?", "Stock market report", "What do you see?"...'
                }
                className="hud-text-input mono"
              />

              <button type="submit" disabled={!inputQuery.trim()} className="hud-send-btn">
                <Send size={18} />
              </button>
            </form>
          </div>

          {/* Optional Picture-in-Picture Camera Perception Feed */}
          {showCameraPip && cameras.length > 0 && (
            <div className="hud-pip-camera glass-card">
              <div className="pip-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="pulse-online" />
                  <span className="mono" style={{ fontSize: '0.75rem', fontWeight: 600, color: '#38bdf8' }}>
                    CAM FEED: {cameras.find((c) => c.id === selectedCameraId)?.name || 'Laptop Primary'}
                  </span>
                </div>
                <span className="badge-tag badge-success mono" style={{ fontSize: '0.65rem' }}>
                  30 FPS · PERCEPTION ACTIVE
                </span>
              </div>
              <div className="pip-video-frame">
                <img
                  src={`/api/v1/stream/mjpeg/${selectedCameraId}`}
                  alt="Live Camera Feed"
                  className="pip-img"
                  onError={(e) => {
                    (e.target as HTMLElement).style.display = 'none';
                  }}
                />
              </div>
            </div>
          )}
        </section>

        {/* ================= RIGHT COLUMN: MARKET INTELLIGENCE & HARDWARE VITALS ================= */}
        <section className="hud-col hud-col-right">
          {/* Live Market Intelligence Watchlist */}
          <div className="hud-panel">
            <div className="hud-panel-title">
              <TrendingUp size={14} color="#38bdf8" />
              <span>LIVE MARKET INTELLIGENCE</span>
              <span className="mono" style={{ fontSize: '0.7rem', color: '#10b981', marginLeft: 'auto' }}>
                REAL-TIME TELEMETRY
              </span>
            </div>

            <div className="hud-stocks-list">
              {stocks.length === 0 ? (
                <div className="empty-stocks mono">Polling live ticker feeds...</div>
              ) : (
                stocks.slice(0, 5).map((stock, idx) => {
                  const isUp = stock.pct >= 0;
                  return (
                    <div key={idx} className="hud-stock-card">
                      <div className="stock-info">
                        <span className="stock-name">{stock.name}</span>
                        <span className="stock-sym mono">{stock.sym}</span>
                      </div>

                      {/* Mini SVG Sparkline */}
                      {stock.spark && stock.spark.length > 1 && (
                        <div className="sparkline-wrapper">
                          <svg viewBox="0 0 70 20" className="spark-svg">
                            <polyline
                              fill="none"
                              stroke={isUp ? '#10b981' : '#f87171'}
                              strokeWidth="1.6"
                              points={stock.spark
                                .map((v, i) => {
                                  const min = Math.min(...stock.spark);
                                  const max = Math.max(...stock.spark);
                                  const d = max - min || 1;
                                  const x = (i / (stock.spark.length - 1)) * 68 + 1;
                                  const y = 18 - ((v - min) / d) * 16;
                                  return `${x.toFixed(1)},${y.toFixed(1)}`;
                                })
                                .join(' ')}
                            />
                          </svg>
                        </div>
                      )}

                      <div className="stock-price-col">
                        <span className="stock-price mono">{stock.price?.toLocaleString()}</span>
                        <span className={`stock-pct mono ${isUp ? 'pct-up' : 'pct-dn'}`}>
                          {isUp ? '▲ +' : '▼ '}
                          {Math.abs(stock.pct || 0).toFixed(2)}%
                        </span>
                      </div>

                      {/* Signal Badge */}
                      <span className={`signal-badge sig-${(stock.signal || 'hold').toLowerCase().replace(' ', '-')}`}>
                        {stock.signal || 'HOLD'}
                      </span>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Executive Briefings & Quick Apps Dock */}
          <div className="hud-panel">
            <div className="hud-panel-title">
              <ExternalLink size={14} color="#818cf8" />
              <span>EXECUTIVE SHORTCUTS & APPS</span>
            </div>

            <div className="hud-apps-dock">
              <button
                onClick={() => handleSendQuery('Can you open WhatsApp?')}
                className="dock-app-btn"
                title="Open WhatsApp Web"
              >
                <span>💬</span>
                <span className="dock-lbl">WhatsApp</span>
              </button>

              <button
                onClick={() => handleSendQuery('Play lofi synthwave music on YouTube')}
                className="dock-app-btn"
                title="Play YouTube Music"
              >
                <span>▶️</span>
                <span className="dock-lbl">YouTube</span>
              </button>

              <button
                onClick={() => handleSendQuery('Give me an executive mail briefing')}
                className="dock-app-btn"
                title="Mail Briefing"
              >
                <span>📬</span>
                <span className="dock-lbl">Mail Brief</span>
              </button>

              <button
                onClick={() => handleSendQuery('Open Google Chrome')}
                className="dock-app-btn"
                title="Launch Google Chrome"
              >
                <span>🌐</span>
                <span className="dock-lbl">Chrome</span>
              </button>

              <button
                onClick={() => handleSendQuery('Open VS Code')}
                className="dock-app-btn"
                title="Launch VS Code"
              >
                <span>💻</span>
                <span className="dock-lbl">VS Code</span>
              </button>

              <button
                onClick={() => handleSendQuery('Open Calculator')}
                className="dock-app-btn"
                title="Open Calculator"
              >
                <span>🧮</span>
                <span className="dock-lbl">Calc</span>
              </button>
            </div>
          </div>

          {/* Hardware Vitals Gauges */}
          <div className="hud-panel">
            <div className="hud-panel-title">
              <Cpu size={14} color="#38bdf8" />
              <span>HARDWARE & SYSTEM VITALS</span>
            </div>

            <div className="vitals-bars-list mono">
              {/* CPU Bar */}
              <div className="vital-item">
                <div className="vital-header">
                  <span className="vital-label">CPU LOAD</span>
                  <span className="vital-val">{Math.round(sysVitals.cpu || 0)}%</span>
                </div>
                <div className="vital-progress-track">
                  <div
                    className="vital-progress-fill fill-cpu"
                    style={{ width: `${Math.min(100, Math.max(5, sysVitals.cpu || 0))}%` }}
                  />
                </div>
              </div>

              {/* RAM Bar */}
              <div className="vital-item">
                <div className="vital-header">
                  <span className="vital-label">RAM USAGE</span>
                  <span className="vital-val">{Math.round(sysVitals.ram || 0)}%</span>
                </div>
                <div className="vital-progress-track">
                  <div
                    className="vital-progress-fill fill-ram"
                    style={{ width: `${Math.min(100, Math.max(5, sysVitals.ram || 0))}%` }}
                  />
                </div>
              </div>

              {/* DISK Bar */}
              <div className="vital-item">
                <div className="vital-header">
                  <span className="vital-label">STORAGE</span>
                  <span className="vital-val">{sysVitals.free || 50} GB FREE</span>
                </div>
                <div className="vital-progress-track">
                  <div
                    className="vital-progress-fill fill-disk"
                    style={{ width: `${Math.min(100, Math.max(5, sysVitals.disk || 0))}%` }}
                  />
                </div>
              </div>

              {/* BATTERY Bar */}
              {sysVitals.bat !== undefined && sysVitals.bat !== null && (
                <div className="vital-item">
                  <div className="vital-header">
                    <span className="vital-label">BATTERY</span>
                    <span className="vital-val">
                      {sysVitals.bat}% {sysVitals.plug ? '⚡ CHARGING' : ''}
                    </span>
                  </div>
                  <div className="vital-progress-track">
                    <div
                      className="vital-progress-fill fill-bat"
                      style={{ width: `${Math.min(100, Math.max(5, sysVitals.bat))}%` }}
                    />
                  </div>
                </div>
              )}

              {/* UPTIME */}
              <div className="vital-uptime-row">
                <span className="vital-label">UPTIME:</span>
                <span className="vital-val">
                  {Math.floor((sysVitals.up || 0) / 3600)}h {Math.floor(((sysVitals.up || 0) % 3600) / 60)}m
                </span>
                <span className="encryption-tag">ENCRYPTION: AES-256</span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
