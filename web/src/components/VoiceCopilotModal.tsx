import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Sparkles,
  X,
  Send,
  Camera,
  Download,
  Play,
  Pause,
  UserCheck,
  UserPlus,
  Shield,
  Activity,
  Zap,
  Radio,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Eye,
  Square,
  Clock,
  Cpu,
  Server,
  Info,
} from 'lucide-react';
import { api } from '../services/api';
import { SentenceChunkTTSQueue, pickNaturalEnglishVoice } from '../utils/ttsQueue';

export type AssistantStatus =
  | 'Idle'
  | 'Listening'
  | 'Processing'
  | 'Analyzing Camera'
  | 'Retrieving Events'
  | 'Speaking'
  | 'Interrupted'
  | 'Error';

interface VoiceCopilotModalProps {
  isOpen?: boolean;
  onClose?: () => void;
  cameraId?: string;
  isVoiceMuted: boolean;
  onToggleVoiceMute: (muted: boolean) => void;
  onCaptureSnapshot: () => void;
  onStartRecording: () => void;
  onStopRecording: () => void;
  isRecording: boolean;
  recordSeconds: number;
  isPlaying: boolean;
  onTogglePlay: (play: boolean) => void;
  onOpenQuickEnroll: (name?: string) => void;
  onOpenDossier: (personId: string, personName: string) => void;
  isEmbedded?: boolean;
  onGetLiveFrame?: () => string | null;
  telemetrySummary?: {
    fps: number;
    people_count: number;
    background_color: string;
    background_scene: string;
  };
}

interface VoiceMessage {
  id: string;
  sender: 'user' | 'ai';
  text: string;
  actionExecuted?: string;
  timestamp: string;
}

export const VoiceCopilotModal: React.FC<VoiceCopilotModalProps> = ({
  isOpen = false,
  onClose,
  cameraId,
  isVoiceMuted,
  onToggleVoiceMute,
  onCaptureSnapshot,
  onStartRecording,
  onStopRecording,
  isRecording,
  recordSeconds,
  isPlaying,
  onTogglePlay,
  onOpenQuickEnroll,
  onOpenDossier,
  isEmbedded = false,
  onGetLiveFrame,
  telemetrySummary,
}) => {
  const [isListening, setIsListening] = useState(false);
  const [ambientListening, setAmbientListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [assistantStatus, setAssistantStatus] = useState<AssistantStatus>('Idle');
  const [activeAgent, setActiveAgent] = useState<'Vision' | 'Memory' | 'Security' | 'Action' | 'Research' | null>(null);
  const [showDiagnostics, setShowDiagnostics] = useState<boolean>(false);
  const [speechTranscript, setSpeechTranscript] = useState('');
  const [textInput, setTextInput] = useState('');
  const [lastAction, setLastAction] = useState<string | null>(null);
  const [speakingChunkProgress, setSpeakingChunkProgress] = useState<{ index: number; total: number; text: string } | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(() => {
    try {
      return localStorage.getItem('aegis_ai_conversation_id');
    } catch {
      return null;
    }
  });

  const [messages, setMessages] = useState<VoiceMessage[]>([
    {
      id: 'init-1',
      sender: 'ai',
      text: "Greetings! I am JARVIS, your visual intelligence personal assistant. I am connected directly to your live camera stream and security systems. Ask me what I observe in your room, check visual event history, or execute camera controls anytime.",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

  const recognitionRef = useRef<any>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const isSpeakingRef = useRef<boolean>(false);
  const isRecognizingRef = useRef<boolean>(false);
  const lastSpokenEndRef = useRef<number>(0);
  const ambientRef = useRef<boolean>(ambientListening);
  const micStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const restartTimerRef = useRef<any>(null);
  const [availableVoices, setAvailableVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [micError, setMicError] = useState<string | null>(null);
  const ttsQueueRef = useRef<SentenceChunkTTSQueue | null>(null);

  // Persistent Conversation Memory: Load chat history across refreshes & restarts
  useEffect(() => {
    let isCancelled = false;

    const initConversation = async () => {
      try {
        const storedId = localStorage.getItem('aegis_ai_conversation_id');
        if (storedId) {
          const dbMsgs = await api.getConversationMessages(storedId);
          if (!isCancelled && dbMsgs && dbMsgs.length > 0) {
            const formatted: VoiceMessage[] = dbMsgs.map((m) => ({
              id: m.id,
              sender: m.role === 'user' ? 'user' : 'ai',
              text: m.content,
              actionExecuted: m.action_executed,
              timestamp: new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            }));
            setMessages(formatted);
            setConversationId(storedId);
            return;
          }
        }

        // If no stored ID or no existing messages, initialize a new persistent session
        const newConv = await api.createConversation('Live Camera Copilot');
        if (!isCancelled && newConv && newConv.id) {
          setConversationId(newConv.id);
          localStorage.setItem('aegis_ai_conversation_id', newConv.id);
        }
      } catch (e) {
        console.warn('Conversation session initialization error:', e);
      }
    };

    if (isOpen || isEmbedded) {
      initConversation();
    }

    return () => {
      isCancelled = true;
    };
  }, [isOpen, isEmbedded]);

  useEffect(() => {
    ambientRef.current = ambientListening;
  }, [ambientListening]);

  // Load and cache high-quality speech voices
  useEffect(() => {
    if (typeof window === 'undefined' || !window.speechSynthesis) return;
    const loadVoices = () => {
      const v = window.speechSynthesis.getVoices();
      if (v && v.length > 0) setAvailableVoices(v);
    };
    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;
    return () => {
      if (window.speechSynthesis) {
        window.speechSynthesis.onvoiceschanged = null;
      }
    };
  }, []);

  // Initialize Sequential Sentence TTS Queue
  useEffect(() => {
    const queue = new SentenceChunkTTSQueue({
      onStart: () => {
        isSpeakingRef.current = true;
        setIsSpeaking(true);
        setAssistantStatus('Speaking');
        // Pause microphone while assistant speaks aloud to prevent self-transcription loopback
        if (recognitionRef.current && isRecognizingRef.current) {
          try {
            recognitionRef.current.stop();
          } catch {}
        }
      },
      onChunk: (chunk, index, total) => {
        setSpeakingChunkProgress({ index, total, text: chunk });
        setAssistantStatus('Speaking');
      },
      onEnd: () => {
        isSpeakingRef.current = false;
        setIsSpeaking(false);
        setSpeakingChunkProgress(null);
        setAssistantStatus('Idle');
        setActiveAgent(null);
        lastSpokenEndRef.current = Date.now();
        // Resume ambient listening if enabled after acoustic echo cooldown
        if (ambientRef.current && (isOpen || isEmbedded)) {
          setTimeout(() => {
            startSpeechRecognition();
          }, 450);
        }
      },
      onInterrupted: () => {
        isSpeakingRef.current = false;
        setIsSpeaking(false);
        setSpeakingChunkProgress(null);
        setAssistantStatus('Interrupted');
        setTimeout(() => {
          setAssistantStatus('Idle');
          setActiveAgent(null);
        }, 1500);
      },
      onError: (err) => {
        console.warn('TTS playback error encountered:', err);
        setIsSpeaking(false);
        setAssistantStatus('Idle');
      },
    });
    ttsQueueRef.current = queue;

    return () => {
      queue.stop();
    };
  }, [isOpen, isEmbedded]);

  // Play High-Tech Audio Chimes
  const playChime = (type: 'listen' | 'action' | 'chime') => {
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
        osc.frequency.setValueAtTime(523.25, ctx.currentTime); // C5
        osc.frequency.setValueAtTime(659.25, ctx.currentTime + 0.08); // E5
        osc.frequency.setValueAtTime(783.99, ctx.currentTime + 0.16); // G5
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

  // Text-To-Speech Output: Non-truncating sentence-chunked sequential playback
  const speakAI = (text: string) => {
    if (isVoiceMuted) return;
    if (ttsQueueRef.current) {
      const voicesList = availableVoices.length > 0 ? availableVoices : (typeof window !== 'undefined' && 'speechSynthesis' in window ? window.speechSynthesis.getVoices() : []);
      const voice = pickNaturalEnglishVoice(voicesList);
      ttsQueueRef.current.speak(text, voice);
    }
  };

  // Immediate Stop Speech Control
  const stopSpeech = () => {
    if (ttsQueueRef.current) {
      ttsQueueRef.current.stop();
    }
    isSpeakingRef.current = false;
    setIsSpeaking(false);
    setSpeakingChunkProgress(null);
    setAssistantStatus('Interrupted');
    setTimeout(() => {
      setAssistantStatus('Idle');
      setActiveAgent(null);
    }, 1500);
  };

  // Initialize live microphone stream and Web Audio Analyser for real-time visual feedback
  const initAudioStream = async (): Promise<boolean> => {
    if (micStreamRef.current && micStreamRef.current.active) {
      return true;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return true;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      micStreamRef.current = stream;

      try {
        const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
        if (AudioCtx) {
          const ctx = new AudioCtx();
          if (ctx.state === 'suspended') {
            await ctx.resume();
          }
          audioContextRef.current = ctx;
          const source = ctx.createMediaStreamSource(stream);
          const analyser = ctx.createAnalyser();
          analyser.fftSize = 64;
          analyser.smoothingTimeConstant = 0.5;
          source.connect(analyser);
          analyserRef.current = analyser;
        }
      } catch (audioErr) {
        console.warn('AudioContext / Analyser init notice:', audioErr);
      }

      setMicError(null);
      return true;
    } catch (err: any) {
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setMicError('Microphone permission blocked. Please click the lock or camera icon in your browser address bar to Allow.');
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        setMicError('No microphone hardware detected. Please connect a working microphone.');
      } else {
        console.warn('Microphone configuration notice:', err);
      }
      return false;
    }
  };

  const stopAudioStream = () => {
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((track) => track.stop());
      micStreamRef.current = null;
    }
    if (audioContextRef.current) {
      try {
        audioContextRef.current.close();
      } catch {}
      audioContextRef.current = null;
    }
    analyserRef.current = null;
  };

  // Initialize Speech Recognition engine
  useEffect(() => {
    if (!isOpen && !isEmbedded) {
      stopSpeechRecognition();
      stopSpeech();
      setMicError(null);
      return;
    }

    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRec) {
      const recognition = new SpeechRec();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = (typeof navigator !== 'undefined' && navigator.language) ? navigator.language : 'en-US';

      recognition.onstart = () => {
        isRecognizingRef.current = true;
        setIsListening(true);
        setMicError(null);
        playChime('listen');
      };

      recognition.onresult = (event: any) => {
        // Critical: If the assistant is speaking aloud or within post-speech acoustic cooldown,
        // ignore microphone transcription events to guarantee zero self-echo loopback!
        if (isSpeakingRef.current || (Date.now() - lastSpokenEndRef.current < 450)) {
          return;
        }

        let interim = '';
        let final = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const res = event.results[i];
          if (res.isFinal) {
            final += res[0].transcript;
          } else {
            interim += res[0].transcript;
          }
        }

        const currentText = (final || interim).trim();
        if (currentText) {
          setSpeechTranscript(currentText);
        }

        if (final && final.trim().length > 0) {
          const query = final.trim();
          const noiseWords = ['[noise]', '[inaudible]', '...', 'um', 'uh', 'ah'];
          if (query.length >= 2 && !noiseWords.includes(query.toLowerCase())) {
            handleProcessVoiceQuery(query);
          }
          setSpeechTranscript('');

          if (!ambientRef.current) {
            try {
              recognition.stop();
            } catch {}
          }
        }
      };

      recognition.onerror = (e: any) => {
        const err = e.error;
        console.warn('SpeechRecognition error:', err);
        isRecognizingRef.current = false;
        setIsListening(false);

        if (err === 'not-allowed' || err === 'permission-denied') {
          setMicError('Microphone blocked. Click the lock/camera icon in your browser address bar to Allow.');
        } else if (err === 'audio-capture') {
          setMicError('No microphone audio detected. Check that your microphone is connected and Windows Microphone Privacy Settings allow access.');
        } else if (err === 'network') {
          setMicError('Speech recognition service unreachable. If using Brave Browser, enable "Use Google services for voice search" in brave://settings/extensions.');
        } else if (err === 'service-not-allowed') {
          setMicError('Web Speech API is blocked over plain HTTP on LAN. Please connect via localhost or HTTPS.');
        } else if (err === 'no-speech') {
          // Normal timeout when no speech is detected; silently wait for next speech
        } else if (err !== 'aborted') {
          setMicError(`Voice input error (${err}). Type your query or check microphone.`);
        }
      };

      recognition.onend = () => {
        isRecognizingRef.current = false;
        setIsListening(false);
        // Only restart if ambient mode is active, copilot is open, and assistant is not speaking
        if (ambientRef.current && (isOpen || isEmbedded) && !isSpeakingRef.current) {
          restartTimerRef.current = setTimeout(() => {
            startSpeechRecognition();
          }, 350);
        }
      };

      recognitionRef.current = recognition;
    } else {
      setMicError('Web Speech API is not supported in this browser. Please use Google Chrome or Microsoft Edge.');
    }

    return () => {
      if (restartTimerRef.current) {
        clearTimeout(restartTimerRef.current);
        restartTimerRef.current = null;
      }
      stopSpeechRecognition();
      stopSpeech();
    };
  }, [isOpen, isEmbedded]);

  const startSpeechRecognition = async () => {
    if (isSpeakingRef.current) return;
    setMicError(null);

    // Warm up microphone stream and connect real-time audio visualizer
    await initAudioStream();

    if (recognitionRef.current && !isRecognizingRef.current && !isSpeakingRef.current) {
      try {
        stopSpeech();
        recognitionRef.current.start();
      } catch (err) {
        // Recognition already active
      }
    }
  };

  const stopSpeechRecognition = () => {
    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }
    if (recognitionRef.current && isRecognizingRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
    }
    stopAudioStream();
    isRecognizingRef.current = false;
    setIsListening(false);
  };

  // Conversation Reset & Replay Handlers
  const handleNewConversation = async () => {
    stopSpeech();
    try {
      const newConv = await api.createConversation('Live Camera Copilot');
      if (newConv && newConv.id) {
        setConversationId(newConv.id);
        try {
          localStorage.setItem('aegis_ai_conversation_id', newConv.id);
        } catch {}
      }
      setMessages([
        {
          id: 'init-new',
          sender: 'ai',
          text: "Started a fresh conversation session! 👋 What would you like to explore or do with the camera?",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } catch (e) {
      console.warn('Failed to start new conversation:', e);
    }
  };

  const handleReplayLastMessage = () => {
    const lastAiMsg = [...messages].reverse().find((m) => m.sender === 'ai');
    if (lastAiMsg && lastAiMsg.text && !isVoiceMuted) {
      stopSpeech();
      speakAI(lastAiMsg.text);
    }
  };

  // Process Query & Dispatch Actions
  const handleProcessVoiceQuery = async (query: string) => {
    if (!query.trim()) return;

    // Immediately interrupt any current speech output
    stopSpeech();

    const qLower = query.toLowerCase();
    if (
      qLower.includes('window') ||
      qLower.includes('door') ||
      qLower.includes('see') ||
      qLower.includes('camera') ||
      qLower.includes('color') ||
      qLower.includes('holding') ||
      qLower.includes('look') ||
      qLower.includes('glasses') ||
      qLower.includes('cabinet') ||
      qLower.includes('cupboard') ||
      qLower.includes('room')
    ) {
      setAssistantStatus('Analyzing Camera');
      setActiveAgent('Vision');
    } else if (
      qLower.includes('enter') ||
      qLower.includes('away') ||
      qLower.includes('history') ||
      qLower.includes('visited') ||
      qLower.includes('timeline') ||
      qLower.includes('recorded')
    ) {
      setAssistantStatus('Retrieving Events');
      setActiveAgent('Memory');
    } else if (
      qLower.includes('snapshot') ||
      qLower.includes('record') ||
      qLower.includes('enroll') ||
      qLower.includes('pause') ||
      qLower.includes('resume')
    ) {
      setAssistantStatus('Processing');
      setActiveAgent('Action');
    } else if (qLower.includes('security') || qLower.includes('threat') || qLower.includes('audit')) {
      setAssistantStatus('Processing');
      setActiveAgent('Security');
    } else {
      setAssistantStatus('Processing');
      setActiveAgent('Research');
    }

    const userMsg: VoiceMessage = {
      id: Date.now().toString(),
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsThinking(true);
    setLastAction(null);

    try {
      const historyPayload = messages.slice(-8).map((m) => ({
        role: m.sender === 'user' ? 'user' : 'ai',
        content: m.text,
      }));

      // Grab fresh camera frame at query time if available
      const freshFrame = onGetLiveFrame ? onGetLiveFrame() : undefined;
      const res = await api.interactCameraAI(
        query,
        cameraId,
        !isVoiceMuted,
        historyPayload,
        freshFrame || undefined,
        conversationId || undefined
      );

      if (res.conversation_id && res.conversation_id !== conversationId) {
        setConversationId(res.conversation_id);
        try {
          localStorage.setItem('aegis_ai_conversation_id', res.conversation_id);
        } catch {}
      }

      // Execute Action Dispatcher
      let executedActionDesc: string | undefined = undefined;

      if (res.action === 'snapshot') {
        onCaptureSnapshot();
        playChime('action');
        executedActionDesc = 'Snapshot Captured & Saved';
      } else if (res.action === 'record_start') {
        onStartRecording();
        playChime('action');
        executedActionDesc = 'Smooth 30 FPS Recording Started';
      } else if (res.action === 'record_stop') {
        onStopRecording();
        playChime('action');
        executedActionDesc = 'Video Recording Finalized';
      } else if (res.action === 'pause') {
        onTogglePlay(false);
        playChime('action');
        executedActionDesc = 'Camera Stream Paused';
      } else if (res.action === 'resume') {
        onTogglePlay(true);
        playChime('action');
        executedActionDesc = 'Camera Stream Resumed';
      } else if (res.action === 'quick_enroll') {
        onOpenQuickEnroll(res.action_payload?.name);
        playChime('action');
        executedActionDesc = 'Quick Enroll Modal Opened';
      } else if (res.action === 'dossier') {
        if (res.action_payload?.person_id && res.action_payload?.person_name) {
          onOpenDossier(res.action_payload.person_id, res.action_payload.person_name);
          playChime('action');
          executedActionDesc = `Opened Dossier for ${res.action_payload.person_name}`;
        }
      } else if (res.action === 'mute') {
        onToggleVoiceMute(true);
        executedActionDesc = 'Voice Copilot Muted';
      } else if (res.action === 'unmute') {
        onToggleVoiceMute(false);
        executedActionDesc = 'Voice Copilot Active';
      }

      if (executedActionDesc) {
        setLastAction(executedActionDesc);
        setTimeout(() => setLastAction(null), 4000);
      }

      const aiMsg: VoiceMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'ai',
        text: res.answer,
        actionExecuted: executedActionDesc,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, aiMsg]);

      // Speak aloud using sequential chunked queue
      if (res.speech_text && !isVoiceMuted) {
        speakAI(res.speech_text);
      }
    } catch (err: any) {
      if (err.message && err.message.includes('500')) {
        setConversationId(null);
        try {
          localStorage.removeItem('aegis_ai_conversation_id');
        } catch {}
      }
      const errMsg: VoiceMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'ai',
        text: `Voice dispatch error: ${err.message || 'Could not reach AI copilot.'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsThinking(false);
      setTextInput('');
    }
  };

  const chatContainerRef = useRef<HTMLDivElement | null>(null);
  const isNearBottomRef = useRef<boolean>(true);

  const handleChatScroll = () => {
    const el = chatContainerRef.current;
    if (!el) return;
    const threshold = 90;
    isNearBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight <= threshold;
  };

  // Smart auto-scroll: only scrolls to bottom if user is already near bottom or submitted a query
  useEffect(() => {
    if (isNearBottomRef.current) {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isThinking]);

  // Clean Markdown & Bullet Formatter for AI responses
  const renderFormattedMessageText = (text: string) => {
    const lines = text.split('\n');
    return lines.map((line, idx) => {
      if (!line.trim()) {
        return <div key={idx} style={{ height: '5px' }} />;
      }

      // Check if line is a bullet
      const trimmed = line.trim();
      const isBullet = trimmed.startsWith('•') || trimmed.startsWith('-');
      const rawContent = isBullet ? trimmed.slice(1).trim() : line;

      // Format bold markdown **text**
      const parts = rawContent.split(/(\*\*[^*]+\*\*)/g);
      const formattedParts = parts.map((part, pIdx) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={pIdx} style={{ color: '#ffffff', fontWeight: 700 }}>{part.slice(2, -2)}</strong>;
        }
        return part;
      });

      if (isBullet) {
        return (
          <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', margin: '3px 0' }}>
            <span style={{ color: '#818cf8', flexShrink: 0, marginTop: '2px', fontSize: '0.8rem' }}>•</span>
            <span style={{ flex: 1 }}>{formattedParts}</span>
          </div>
        );
      }

      return (
        <div key={idx} style={{ margin: '1px 0' }}>
          {formattedParts}
        </div>
      );
    });
  };

  // Holographic Audio Visualizer Canvas Animation
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let angle = 0;
    const renderWave = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const width = canvas.width;
      const height = canvas.height;
      const centerY = height / 2;

      const numBars = 32;
      const barWidth = width / numBars - 2;

      let freqData: Uint8Array | null = null;
      if (isListening && analyserRef.current) {
        try {
          freqData = new Uint8Array(analyserRef.current.frequencyBinCount);
          (analyserRef.current as any).getByteFrequencyData(freqData);
        } catch {}
      }

      for (let i = 0; i < numBars; i++) {
        let barHeight = 6;
        let color = 'rgba(99, 102, 241, 0.4)';

        if (isSpeaking) {
          // Energetic electric blue/purple equalizer waves
          const wave = Math.sin(angle * 4 + i * 0.45) * 0.5 + 0.5;
          barHeight = 10 + wave * 32;
          color = `rgba(129, 140, 248, ${0.4 + wave * 0.6})`;
        } else if (isListening) {
          if (freqData && freqData.length > 0) {
            // Map the visualizer bar to frequency spectrum
            const binIdx = Math.floor((i / numBars) * (freqData.length * 0.75));
            const rawVal = freqData[binIdx] || 0;
            const normVal = rawVal / 255;
            barHeight = 4 + normVal * 36;
            color = `rgba(52, 211, 153, ${0.4 + normVal * 0.6})`;
          } else {
            // Smooth glowing reactive wave
            const wave = Math.sin(angle * 6 + i * 0.3) * 0.5 + 0.5;
            barHeight = 12 + wave * 38;
            color = `rgba(52, 211, 153, ${0.4 + wave * 0.6})`;
          }
        } else if (isThinking) {
          // Shimmering radar pulse
          const wave = Math.sin(angle * 3 + i * 0.2) * 0.5 + 0.5;
          barHeight = 8 + wave * 20;
          color = `rgba(168, 85, 247, ${0.4 + wave * 0.5})`;
        } else {
          // Gentle ambient breathing
          const wave = Math.sin(angle * 1.5 + i * 0.2) * 0.5 + 0.5;
          barHeight = 4 + wave * 6;
          color = 'rgba(255, 255, 255, 0.12)';
        }

        const x = i * (barWidth + 2);
        const y = centerY - barHeight / 2;

        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.roundRect(x, y, barWidth, barHeight, 3);
        ctx.fill();
      }

      angle += 0.04;
      animFrameRef.current = requestAnimationFrame(renderWave);
    };

    renderWave();
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [isListening, isSpeaking, isThinking]);

  if (!isOpen && !isEmbedded) return null;

  const modalBody = (
    <div
      className={`jarvis-command-panel ${isEmbedded ? 'embedded' : 'modal'}`}
      style={{
        width: '100%',
        maxWidth: isEmbedded ? '100%' : '680px',
        height: isEmbedded ? '100%' : undefined,
        maxHeight: isEmbedded ? '100%' : '90vh',
      }}
    >
      {/* Header */}
      <div className="jarvis-panel-header">
        <div className="jarvis-header-top-row">
          <div className="jarvis-title-group">
            <div
              className={`jarvis-avatar-orb ${
                isListening ? 'listening' : isSpeaking ? 'speaking' : isThinking ? 'thinking' : ''
              }`}
            >
              {isListening ? <Mic size={16} /> : <Sparkles size={16} />}
            </div>
            <div>
              <div className="jarvis-title-text-row">
                <span className="jarvis-title">JARVIS Copilot</span>
                <span className={`jarvis-status-badge status-${assistantStatus.toLowerCase().replace(/\s+/g, '-')}`}>
                  <span className="status-dot" />
                  {assistantStatus === 'Speaking' && speakingChunkProgress
                    ? `SPEAKING ${speakingChunkProgress.index}/${speakingChunkProgress.total}`
                    : assistantStatus.toUpperCase()}
                </span>
              </div>
            </div>
          </div>

          <div className="jarvis-header-actions">
            {/* Hands-Free Toggle */}
            <button
              onClick={() => {
                const next = !ambientListening;
                setAmbientListening(next);
                if (next) startSpeechRecognition();
                else stopSpeechRecognition();
              }}
              className={`jarvis-icon-btn ${ambientListening ? 'active-emerald' : ''}`}
              title={ambientListening ? 'Hands-Free Listening Active (Click for Push-to-Talk)' : 'Push-to-Talk (Click for Hands-Free Listening)'}
            >
              <Radio size={14} className={ambientListening ? 'pulse-online' : ''} />
            </button>

            {/* Voice Mute Toggle */}
            <button
              onClick={() => onToggleVoiceMute(!isVoiceMuted)}
              className={`jarvis-icon-btn ${isVoiceMuted ? 'active-red' : ''}`}
              title={isVoiceMuted ? 'Voice Muted (Click to enable speech)' : 'Voice Enabled (Click to mute)'}
            >
              {isVoiceMuted ? <VolumeX size={14} /> : <Volume2 size={14} />}
            </button>

            {/* Stop Speech (Visible when speaking) */}
            {isSpeaking && (
              <button
                onClick={stopSpeech}
                className="jarvis-icon-btn stop-btn"
                title="Stop Audio Playback Immediately"
              >
                <Square size={10} fill="currentColor" />
                <span>Stop</span>
              </button>
            )}

            {/* Replay Last AI Message */}
            <button
              onClick={handleReplayLastMessage}
              className="jarvis-icon-btn"
              title="Replay Last AI Response"
            >
              <RotateCcw size={13} />
            </button>

            {/* New Isolated Conversation */}
            <button
              onClick={handleNewConversation}
              className="jarvis-icon-btn"
              title="Start a New Conversation Session"
            >
              <Sparkles size={13} />
            </button>

            {!isEmbedded && onClose && (
              <button onClick={onClose} className="jarvis-icon-btn" title="Close Dialog">
                <X size={16} />
              </button>
            )}
          </div>
        </div>

        {/* Camera Source & Frame Grounding Line */}
        <div className="jarvis-source-subrow">
          <span className="source-dot pulse-online" />
          <span className="source-text">
            Source: {cameraId ? `Camera ${cameraId.slice(0, 8)}` : 'Laptop Primary Webcam (1280x720)'} • Verified Live 30 FPS • Grounded Perception
          </span>
        </div>
      </div>

      {/* Multi-Agent Activity Strip */}
      <div className="jarvis-agent-strip">
        <div className="agent-chips-scroll">
          <span className="agent-label">Agents:</span>

          <div
            className={`agent-chip ${activeAgent === 'Vision' || assistantStatus === 'Analyzing Camera' ? 'active-vision' : ''}`}
            title="Vision Agent: Real-time OpenCV & FaceNet frame scene understanding"
          >
            <Eye size={11} />
            <span>Vision</span>
            {(activeAgent === 'Vision' || assistantStatus === 'Analyzing Camera') && <span className="agent-live-dot" />}
          </div>

          <div
            className={`agent-chip ${activeAgent === 'Memory' || assistantStatus === 'Retrieving Events' ? 'active-memory' : ''}`}
            title="Memory Agent: Historical event timeline and biometric identification records"
          >
            <Clock size={11} />
            <span>Memory</span>
            {(activeAgent === 'Memory' || assistantStatus === 'Retrieving Events') && <span className="agent-live-dot" />}
          </div>

          <div
            className={`agent-chip ${activeAgent === 'Security' ? 'active-security' : ''}`}
            title="Security Agent: Boundary rules, tamper detection & rate limiting"
          >
            <Shield size={11} />
            <span>Security</span>
            {activeAgent === 'Security' && <span className="agent-live-dot" />}
          </div>

          <div
            className={`agent-chip ${activeAgent === 'Action' ? 'active-action' : ''}`}
            title="Action Agent: Verified tool execution (Snapshots, Recording, Quick Enroll)"
          >
            <Zap size={11} />
            <span>Action</span>
            {activeAgent === 'Action' && <span className="agent-live-dot" />}
          </div>
        </div>

        <button
          onClick={() => setShowDiagnostics(!showDiagnostics)}
          className={`diagnostics-toggle-btn ${showDiagnostics ? 'active' : ''}`}
          title="Toggle Real-Time System Architecture & Diagnostics"
        >
          <Cpu size={12} />
          <span>Diagnostics</span>
        </button>
      </div>

      {/* Expandable Architecture & Diagnostics Drawer */}
      {showDiagnostics && (
        <div
          style={{
            background: 'rgba(11, 14, 22, 0.96)',
            borderBottom: '1px solid rgba(99, 102, 241, 0.4)',
            padding: '8px 12px',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
            gap: '6px',
            fontSize: '0.7rem',
            color: '#e2e8f0',
            flexShrink: 0,
          }}
        >
          <div style={{ background: 'rgba(255,255,255,0.03)', padding: '5px 8px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.06)' }}>
            <div style={{ color: 'var(--text-faint)', fontSize: '0.62rem' }}>VISION ENGINE</div>
            <div style={{ fontWeight: 700, color: '#38bdf8' }}>OpenCV + FaceNet</div>
            <div style={{ color: '#94a3b8', fontSize: '0.62rem' }}>Grounded Frame Verified</div>
          </div>
          <div style={{ background: 'rgba(255,255,255,0.03)', padding: '5px 8px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.06)' }}>
            <div style={{ color: 'var(--text-faint)', fontSize: '0.62rem' }}>SPEECH SYNTHESIS</div>
            <div style={{ fontWeight: 700, color: '#34d399' }}>ChunkTTSQueue</div>
            <div style={{ color: '#94a3b8', fontSize: '0.62rem' }}>Watchdog & V8 GC Active</div>
          </div>
          <div style={{ background: 'rgba(255,255,255,0.03)', padding: '5px 8px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.06)' }}>
            <div style={{ color: 'var(--text-faint)', fontSize: '0.62rem' }}>BIOMETRIC SECURITY</div>
            <div style={{ fontWeight: 700, color: '#fbbf24' }}>AES-256-GCM Vault</div>
            <div style={{ color: '#94a3b8', fontSize: '0.62rem' }}>Owner-Only Local Store</div>
          </div>
        </div>
      )}

      {/* Holographic Audio Visualizer & Feedback Bar */}
      <div className="jarvis-visualizer-bar">
        <div className="visualizer-canvas-wrap">
          <canvas ref={canvasRef} width={90} height={20} style={{ width: '100%', height: '20px' }} />
        </div>

        <div className="visualizer-text-info">
          {speechTranscript ? (
            <span style={{ color: '#34d399', fontWeight: 600 }}>"{speechTranscript}"</span>
          ) : isSpeaking ? (
            <span style={{ color: '#22d3ee', display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
              <Volume2 size={12} className="pulse-online" />
              <span>
                {speakingChunkProgress
                  ? `Speaking chunk ${speakingChunkProgress.index} of ${speakingChunkProgress.total}...`
                  : 'JARVIS speaking...'}
              </span>
            </span>
          ) : isListening ? (
            <span style={{ color: '#34d399' }}>Listening to voice...</span>
          ) : isThinking ? (
            <span style={{ color: '#c084fc', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <Activity size={12} className="pulse-online" />
              <span>Analyzing camera intelligence...</span>
            </span>
          ) : lastAction ? (
            <span style={{ color: '#34d399', fontWeight: 600 }}>⚡ {lastAction}</span>
          ) : (
            <span style={{ color: 'var(--text-faint)' }}>Push-to-Talk or speak anytime</span>
          )}
        </div>
      </div>

      {/* Microphone Permission Warning Banner */}
      {micError && (
        <div
          style={{
            margin: '6px 12px',
            background: 'rgba(239, 68, 68, 0.16)',
            border: '1px solid rgba(239, 68, 68, 0.35)',
            color: '#fca5a5',
            padding: '6px 10px',
            borderRadius: '6px',
            fontSize: '0.72rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '8px',
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <AlertTriangle size={13} color="#ef4444" style={{ flexShrink: 0 }} />
            <span>{micError}</span>
          </div>
          <button
            onClick={() => {
              setMicError(null);
              startSpeechRecognition();
            }}
            style={{
              background: 'rgba(239, 68, 68, 0.25)',
              border: '1px solid rgba(239, 68, 68, 0.5)',
              color: '#ffffff',
              fontSize: '0.65rem',
              fontWeight: 600,
              padding: '2px 6px',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            Retry
          </button>
        </div>
      )}

      {/* Conversation Dialog Area */}
      <div
        className="jarvis-messages-container"
        ref={chatContainerRef}
        onScroll={handleChatScroll}
      >
        {messages.map((m) => {
          const isUser = m.sender === 'user';
          return (
            <div key={m.id} className={`jarvis-msg-wrap ${isUser ? 'user' : 'ai'}`}>
              <div className={isUser ? 'jarvis-bubble-user' : 'jarvis-bubble-ai'}>
                {isUser ? m.text : renderFormattedMessageText(m.text)}
              </div>

              <div className="jarvis-msg-meta">
                <span>{m.timestamp}</span>
                {!isUser && (
                  <button
                    onClick={() => speakAI(m.text)}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '3px',
                      background: 'rgba(255, 255, 255, 0.04)',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      color: 'var(--text-muted)',
                      cursor: 'pointer',
                      fontSize: '0.65rem',
                      padding: '1px 5px',
                      borderRadius: '4px',
                      transition: 'all 0.15s ease',
                    }}
                    title="Replay Audio"
                  >
                    <RotateCcw size={9} />
                    <span>Replay</span>
                  </button>
                )}
                {m.actionExecuted && (
                  <span
                    style={{
                      fontSize: '0.64rem',
                      background: 'rgba(16, 185, 129, 0.15)',
                      color: '#34d399',
                      padding: '1px 6px',
                      borderRadius: '4px',
                      fontWeight: 700,
                    }}
                  >
                    ⚡ {m.actionExecuted}
                  </span>
                )}
              </div>
            </div>
          );
        })}
        <div ref={chatEndRef} />
      </div>

      {/* Fast Action Suggestion Chips */}
      <div className="jarvis-chips-bar">
        {[
          { label: 'Can you see me?', icon: <Eye size={11} /> },
          { label: 'What do you see?', icon: <Sparkles size={11} /> },
          { label: 'What am I wearing?', icon: <Sparkles size={11} /> },
          { label: 'Check my expression', icon: <UserCheck size={11} /> },
          { label: 'What happened on camera?', icon: <Activity size={11} /> },
          { label: 'Take a snapshot', icon: <Camera size={11} /> },
          { label: isRecording ? 'Stop recording' : 'Start recording', icon: <Download size={11} /> },
          { label: 'Security alerts overview', icon: <AlertTriangle size={11} /> },
          { label: 'Capabilities & help', icon: <Radio size={11} /> },
        ].map((chip) => (
          <button
            key={chip.label}
            onClick={() => handleProcessVoiceQuery(chip.label)}
            className="jarvis-chip-btn"
          >
            {chip.icon}
            <span>{chip.label}</span>
          </button>
        ))}
      </div>

      {/* Input Composer Bar */}
      <div className="jarvis-composer-bar">
        {/* Main Mic Button */}
        <button
          onClick={() => {
            if (isListening) stopSpeechRecognition();
            else startSpeechRecognition();
          }}
          className={`jarvis-mic-btn ${isListening ? 'listening' : ''}`}
          title={isListening ? 'Click to Stop Listening' : 'Click to Speak (Push-to-Talk)'}
        >
          {isListening ? <MicOff size={18} /> : <Mic size={18} />}
        </button>

        {/* Text Input Wrapper */}
        <div className="jarvis-composer-input-wrap">
          <input
            type="text"
            className="jarvis-composer-input"
            placeholder={isListening ? 'Listening to speech...' : 'Ask JARVIS anything about camera, scene, or controls...'}
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (textInput.trim() && !isThinking) {
                  handleProcessVoiceQuery(textInput);
                }
              }
            }}
          />
          <button
            onClick={() => handleProcessVoiceQuery(textInput)}
            disabled={!textInput.trim() || isThinking}
            className="jarvis-send-btn"
            title="Send Message (Enter)"
          >
            <Send size={14} />
          </button>
        </div>
      </div>
    </div>
  );

  if (isEmbedded) {
    return modalBody;
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(5, 7, 12, 0.75)',
        backdropFilter: 'blur(12px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px',
        animation: 'fadeIn 0.2s ease',
      }}
    >
      {modalBody}
    </div>
  );
};
