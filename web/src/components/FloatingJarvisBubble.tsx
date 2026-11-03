import React, { useState, useEffect, useRef } from 'react';
import { 
  Bot, 
  Mic, 
  MicOff, 
  Square, 
  Send, 
  X, 
  Sparkles, 
  Volume2, 
  VolumeX, 
  AlertCircle,
  Eye,
  Camera,
  Activity
} from 'lucide-react';
import { AudioSessionManager, AudioState } from '../utils/AudioSessionManager';
import { api } from '../services/api';

interface FloatingJarvisBubbleProps {
  onNavigateToModule?: (moduleKey: string) => void;
  onCameraInspectRequested?: () => void;
}

export const FloatingJarvisBubble: React.FC<FloatingJarvisBubbleProps> = ({
  onNavigateToModule,
  onCameraInspectRequested,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [audioState, setAudioState] = useState<AudioState>('IDLE');
  const [transcript, setTranscript] = useState('');
  const [inputText, setInputText] = useState('');
  const [isHandsFree, setIsHandsFree] = useState(false);
  const [lastResponse, setLastResponse] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const audioManager = useRef(AudioSessionManager.getInstance()).current;

  useEffect(() => {
    audioManager.registerCallbacks({
      onStateChange: (state, msg) => {
        setAudioState(state);
      },
      onTranscript: (liveTranscript, isFinal) => {
        setTranscript(liveTranscript);
        if (isFinal) {
          setInputText(liveTranscript);
        }
      },
      onCommandReady: (command) => {
        handleExecuteCommand(command);
      },
      onError: (err) => {
        console.warn('[FloatingJarvis] Audio error:', err);
      },
    });

    setIsHandsFree(audioManager.isHandsFreeActive());
  }, []);

  const handleToggleHandsFree = () => {
    const next = !isHandsFree;
    setIsHandsFree(next);
    audioManager.setHandsFree(next);
  };

  const handleMicClick = () => {
    if (audioState === 'LISTENING' || audioState === 'USER_SPEECH_DETECTED') {
      audioManager.stopListening();
    } else if (audioState === 'SPEAKING') {
      audioManager.interrupt();
    } else {
      audioManager.startListening();
    }
  };

  const handleExecuteCommand = async (command: string) => {
    if (!command.trim() || isLoading) return;
    setIsLoading(true);
    setTranscript(`"${command}"`);

    const lower = command.toLowerCase();

    // Contextual Routing
    if (lower.includes('camera') || lower.includes('inspect') || lower.includes('who is there')) {
      if (onCameraInspectRequested) onCameraInspectRequested();
    }
    if (lower.includes('live wall') || lower.includes('monitoring')) {
      if (onNavigateToModule) onNavigateToModule('live_monitoring');
    } else if (lower.includes('person') || lower.includes('people') || lower.includes('who is that')) {
      if (onNavigateToModule) onNavigateToModule('people');
    } else if (lower.includes('report') || lower.includes('audit')) {
      if (onNavigateToModule) onNavigateToModule('reports');
    } else if (lower.includes('event') || lower.includes('security')) {
      if (onNavigateToModule) onNavigateToModule('events');
    } else if (lower.includes('health') || lower.includes('diagnostic')) {
      if (onNavigateToModule) onNavigateToModule('health');
    }

    try {
      const res = await api.interactCameraAI(command, 'primary', true);

      const speech = res.speech_text || res.answer || 'Action completed.';
      setLastResponse(speech);
      audioManager.speakResponse(speech);
    } catch (err: any) {
      const errMsg = 'I encountered an issue processing your request.';
      setLastResponse(errMsg);
      audioManager.speakResponse(errMsg);
    } finally {
      setIsLoading(false);
      setInputText('');
    }
  };

  const getStateColor = () => {
    switch (audioState) {
      case 'LISTENING':
      case 'USER_SPEECH_DETECTED':
        return '#10b981'; // Green
      case 'PROCESSING':
        return '#f59e0b'; // Amber
      case 'SPEAKING':
        return '#38bdf8'; // Cyan
      case 'ERROR':
      case 'PERMISSION_DENIED':
        return '#ef4444'; // Red
      default:
        return '#00d2ff'; // Default Jarvis Cyan
    }
  };

  const getStateLabel = () => {
    switch (audioState) {
      case 'LISTENING':
        return 'Listening hands-free...';
      case 'USER_SPEECH_DETECTED':
        return 'Speech detected...';
      case 'PROCESSING':
        return 'Thinking...';
      case 'SPEAKING':
        return 'Speaking...';
      case 'WAITING_FOR_NEXT_COMMAND':
        return 'Ready for next command';
      case 'PERMISSION_DENIED':
        return 'Mic permission needed';
      default:
        return isHandsFree ? 'Hands-Free Ready' : 'Jarvis Online';
    }
  };

  return (
    <>
      {/* ── GLOBAL FLOATING BUBBLE ────────────────────────────────────────── */}
      <div
        id="jarvis-global-floating-bubble"
        style={{
          position: 'fixed',
          bottom: '22px',
          right: '22px',
          zIndex: 99999,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-end',
          pointerEvents: 'auto',
          fontFamily: 'Inter, system-ui, sans-serif',
        }}
      >
        {/* Expanded Panel */}
        {isOpen && (
          <div
            style={{
              width: '340px',
              maxWidth: '92vw',
              background: 'rgba(7, 14, 35, 0.96)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(0, 210, 255, 0.3)',
              borderRadius: '16px',
              boxShadow: '0 12px 40px rgba(0, 0, 0, 0.7), 0 0 24px rgba(0, 210, 255, 0.25)',
              padding: '16px',
              marginBottom: '12px',
              color: '#f8fafc',
              animation: 'fadeInUp 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
          >
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ width: '26px', height: '26px', borderRadius: '50%', background: getStateColor(), display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Bot size={15} color="#000" />
                </div>
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 700, color: '#fff' }}>Jarvis Assistant</div>
                  <div style={{ fontSize: '10px', color: getStateColor(), fontWeight: 600 }}>{getStateLabel()}</div>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <button
                  onClick={handleToggleHandsFree}
                  title={isHandsFree ? 'Disable Hands-Free Mode' : 'Enable Hands-Free Continuous Voice'}
                  style={{
                    background: isHandsFree ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255,255,255,0.06)',
                    border: `1px solid ${isHandsFree ? '#10b981' : 'rgba(255,255,255,0.15)'}`,
                    color: isHandsFree ? '#34d399' : '#94a3b8',
                    padding: '3px 8px',
                    borderRadius: '6px',
                    fontSize: '10px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  <Mic size={10} />
                  <span>{isHandsFree ? 'Hands-Free' : 'Push-to-Talk'}</span>
                </button>

                <button
                  onClick={() => setIsOpen(false)}
                  style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '2px' }}
                >
                  <X size={16} />
                </button>
              </div>
            </div>

            {/* Live Transcript / Speech Indicator */}
            {(transcript || audioState === 'SPEAKING' || lastResponse) && (
              <div
                style={{
                  background: 'rgba(15, 23, 42, 0.7)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '10px',
                  padding: '10px 12px',
                  marginBottom: '12px',
                  fontSize: '12px',
                  lineHeight: 1.4,
                  maxHeight: '120px',
                  overflowY: 'auto',
                }}
              >
                {audioState === 'SPEAKING' ? (
                  <div style={{ color: '#38bdf8' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px', fontWeight: 600 }}>
                      <Volume2 size={12} /> Jarvis Speaking:
                    </div>
                    <span>{lastResponse}</span>
                  </div>
                ) : (
                  <div>
                    <span style={{ color: '#94a3b8' }}>Detected: </span>
                    <span style={{ color: '#fff', fontWeight: 500 }}>{transcript || lastResponse}</span>
                  </div>
                )}
              </div>
            )}

            {/* Quick Action Chips */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', marginBottom: '12px' }}>
              {[
                'Inspect my camera',
                'Show detected person',
                'System health check',
                'Generate audit report',
              ].map((chip, idx) => (
                <button
                  key={idx}
                  onClick={() => handleExecuteCommand(chip)}
                  style={{
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '6px',
                    padding: '3px 8px',
                    fontSize: '10px',
                    color: '#cbd5e1',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {chip}
                </button>
              ))}
            </div>

            {/* Input Bar with Instant Send & Mic */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleExecuteCommand(inputText);
              }}
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <input
                type="text"
                placeholder={isHandsFree ? 'Listening hands-free...' : 'Ask Jarvis anything...'}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                style={{
                  flex: 1,
                  background: 'rgba(15, 23, 42, 0.8)',
                  border: '1px solid rgba(0, 210, 255, 0.25)',
                  borderRadius: '8px',
                  color: '#fff',
                  padding: '7px 10px',
                  fontSize: '12px',
                  outline: 'none',
                }}
              />

              <button
                type="button"
                onClick={handleMicClick}
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '8px',
                  background: audioState === 'LISTENING' ? '#10b981' : audioState === 'SPEAKING' ? '#ef4444' : 'rgba(255,255,255,0.08)',
                  border: '1px solid rgba(255,255,255,0.15)',
                  color: '#fff',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                title={audioState === 'SPEAKING' ? 'Stop Speaking' : audioState === 'LISTENING' ? 'Stop Listening' : 'Speak'}
              >
                {audioState === 'SPEAKING' ? <Square size={13} /> : audioState === 'LISTENING' ? <Mic size={14} /> : <Mic size={14} />}
              </button>

              <button
                type="submit"
                disabled={isLoading || !inputText.trim()}
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '8px',
                  background: 'linear-gradient(135deg, #00d2ff 0%, #2563eb 100%)',
                  border: 'none',
                  color: '#fff',
                  cursor: isLoading || !inputText.trim() ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  opacity: isLoading || !inputText.trim() ? 0.5 : 1,
                }}
              >
                <Send size={13} />
              </button>
            </form>
          </div>
        )}

        {/* ── Main Orb Button ──────────────────────────────────────────────── */}
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Status pill tag */}
          <div
            style={{
              background: 'rgba(7, 14, 35, 0.9)',
              border: `1px solid ${getStateColor()}`,
              borderRadius: '20px',
              padding: '4px 10px',
              fontSize: '11px',
              fontWeight: 600,
              color: getStateColor(),
              boxShadow: '0 4px 14px rgba(0,0,0,0.5)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background: getStateColor(),
                boxShadow: `0 0 8px ${getStateColor()}`,
              }}
            />
            <span>{audioState === 'SPEAKING' ? 'Speaking' : audioState === 'LISTENING' ? 'Listening' : isHandsFree ? 'Hands-Free' : 'Jarvis'}</span>
          </div>

          <button
            onClick={() => setIsOpen(!isOpen)}
            aria-label="Toggle Jarvis Assistant"
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              background: 'radial-gradient(circle, #0284c7 0%, #030712 100%)',
              border: `2px solid ${getStateColor()}`,
              color: '#fff',
              boxShadow: `0 0 24px ${getStateColor()}88, 0 6px 18px rgba(0,0,0,0.7)`,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
              transform: isOpen ? 'scale(1.05)' : 'scale(1)',
            }}
          >
            <Bot size={26} color="#ffffff" />
          </button>
        </div>
      </div>
    </>
  );
};
