import React, { useRef, useEffect } from 'react';
import { 
  Bot, 
  Sparkles, 
  Mic, 
  Send, 
  Volume2, 
  VolumeX, 
  Plus, 
  Copy, 
  CheckCheck, 
  RefreshCw 
} from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at?: string;
  speech_text?: string;
  action_executed?: string;
}

interface AIAssistantModuleProps {
  chatMessages?: Message[];
  aiQuery?: string;
  setAiQuery?: (val: string) => void;
  aiLoading?: boolean;
  ttsEnabled?: boolean;
  setTtsEnabled?: (val: boolean) => void;
  isHandsFreeMode?: boolean;
  setIsHandsFreeMode?: (val: boolean) => void;
  onSend?: (e?: React.FormEvent, customQuery?: string) => void;
  onVoiceInput?: () => void;
  conversations?: any[];
  activeConvId?: string | null;
  onSelectConversation?: (id: string) => void;
  onNewConversation?: () => void;
  copiedMsgId?: string | null;
  onCopyMessage?: (text: string, id: string) => void;
  onBackToCommandCenter?: () => void;
}

export const AIAssistantModule: React.FC<AIAssistantModuleProps> = ({
  chatMessages = [],
  aiQuery = '',
  setAiQuery = () => {},
  aiLoading = false,
  ttsEnabled = false,
  setTtsEnabled = () => {},
  isHandsFreeMode = false,
  setIsHandsFreeMode = () => {},
  onSend = () => {},
  onVoiceInput = () => {},
  conversations = [],
  activeConvId = null,
  onSelectConversation = () => {},
  onNewConversation = () => {},
  copiedMsgId = null,
  onCopyMessage = () => {},
  onBackToCommandCenter,
}) => {
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [chatMessages, aiLoading]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 160px)', background: '#070f26', borderRadius: 14, border: '1px solid rgba(0, 210, 255, 0.25)', overflow: 'hidden' }}>
      {/* Top Header Bar */}
      <div style={{ padding: '12px 18px', background: 'rgba(10, 20, 50, 0.95)', borderBottom: '1px solid rgba(0, 210, 255, 0.2)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {onBackToCommandCenter && (
            <button
              onClick={onBackToCommandCenter}
              style={{
                background: 'rgba(255,255,255,0.08)',
                border: '1px solid rgba(255,255,255,0.15)',
                color: '#38bdf8',
                borderRadius: 6,
                padding: '4px 8px',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer',
                marginRight: 6,
              }}
            >
              ← Back
            </button>
          )}
          <div style={{ width: 34, height: 34, borderRadius: 8, background: 'linear-gradient(135deg, #00d2ff 0%, #2563eb 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 12px rgba(0, 210, 255, 0.4)' }}>
            <Bot size={20} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: '0.96rem', fontWeight: 700, color: '#ffffff' }}>JARVIS Universal AI Assistant</span>
              <span style={{ fontSize: '0.66rem', padding: '2px 6px', borderRadius: 4, background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', fontWeight: 600 }}>
                ● Active Reasoner (₹0 Engine)
              </span>
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
              Multimodal intelligence • Camera perception • Persistent memory • Code & Math reasoning
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <select 
            value={activeConvId || ''} 
            onChange={(e) => onSelectConversation(e.target.value)}
            style={{ background: 'rgba(7, 14, 35, 0.8)', border: '1px solid rgba(0, 210, 255, 0.3)', borderRadius: 6, color: '#fff', padding: '5px 8px', fontSize: '0.72rem', outline: 'none' }}
          >
            <option value="">Current Session ({chatMessages.length} turns)</option>
            {conversations.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title || `Session ${c.id.slice(0, 6)}`}
              </option>
            ))}
          </select>

          <button
            onClick={onNewConversation}
            style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 6, color: '#cbd5e1', padding: '5px 10px', fontSize: '0.72rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}
          >
            <Plus size={13} /> New Chat
          </button>

          <button
            onClick={() => setIsHandsFreeMode(!isHandsFreeMode)}
            style={{
              background: isHandsFreeMode ? 'rgba(16, 185, 129, 0.25)' : 'rgba(255,255,255,0.06)',
              border: isHandsFreeMode ? '1px solid #10b981' : '1px solid rgba(255,255,255,0.15)',
              borderRadius: 6,
              color: isHandsFreeMode ? '#34d399' : '#cbd5e1',
              padding: '5px 10px',
              fontSize: '0.72rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 4
            }}
          >
            <Mic size={13} /> {isHandsFreeMode ? 'Hands-Free Loop Active' : 'Hands-Free'}
          </button>

          <button
            onClick={() => setTtsEnabled(!ttsEnabled)}
            style={{
              background: ttsEnabled ? 'rgba(0, 210, 255, 0.25)' : 'rgba(255,255,255,0.06)',
              border: ttsEnabled ? '1px solid #00d2ff' : '1px solid rgba(255,255,255,0.15)',
              borderRadius: 6,
              color: ttsEnabled ? '#00d2ff' : '#cbd5e1',
              padding: '5px 10px',
              fontSize: '0.72rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 4
            }}
          >
            {ttsEnabled ? <Volume2 size={13} /> : <VolumeX size={13} />} Speech Output
          </button>
        </div>
      </div>

      {/* Message History Viewport */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {chatMessages.map((msg) => {
          const isUser = msg.role === 'user';
          return (
            <div key={msg.id} style={{ display: 'flex', flexDirection: 'column', alignItems: isUser ? 'flex-end' : 'flex-start', width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, paddingLeft: 4, paddingRight: 4 }}>
                <span style={{ fontSize: '0.68rem', fontWeight: 700, color: isUser ? '#60a5fa' : '#00d2ff' }}>
                  {isUser ? 'You (Authorized Owner)' : 'JARVIS AI Engine'}
                </span>
                {msg.created_at && (
                  <span style={{ fontSize: '0.62rem', color: '#64748b' }}>
                    {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                )}
              </div>

              <div
                style={{
                  maxWidth: '85%',
                  padding: '10px 14px',
                  borderRadius: isUser ? '14px 14px 2px 14px' : '14px 14px 14px 2px',
                  background: isUser ? 'linear-gradient(135deg, #1e40af 0%, #2563eb 100%)' : 'rgba(11, 22, 53, 0.95)',
                  border: isUser ? '1px solid rgba(59, 130, 246, 0.5)' : '1px solid rgba(0, 210, 255, 0.25)',
                  color: '#ffffff',
                  fontSize: '0.84rem',
                  lineHeight: 1.5,
                  boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word'
                }}
              >
                {!isUser && (
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 4 }}>
                    <button
                      onClick={() => onCopyMessage(msg.content, msg.id)}
                      title="Copy response"
                      style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 2 }}
                    >
                      {copiedMsgId === msg.id ? <CheckCheck size={13} color="#10b981" /> : <Copy size={13} />}
                    </button>
                  </div>
                )}
                {msg.content}
              </div>
            </div>
          );
        })}

        {aiLoading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderRadius: 8, background: 'rgba(0, 210, 255, 0.1)', border: '1px solid rgba(0, 210, 255, 0.3)', color: '#00d2ff', fontSize: '0.78rem', width: 'fit-content' }}>
            <RefreshCw size={14} className="animate-spin" />
            <span>JARVIS is synthesizing reasoning, inspecting camera perception & verified tools...</span>
          </div>
        )}
      </div>

      {/* Suggested Quick Action Chips */}
      <div style={{ padding: '8px 18px', background: 'rgba(10, 20, 50, 0.7)', borderTop: '1px solid rgba(0, 210, 255, 0.12)', display: 'flex', gap: 6, overflowX: 'auto', scrollbarWidth: 'none' }}>
        {[
          'Inspect current live camera view',
          'Search today\'s security events',
          'Show enrolled people in database',
          'Find my labelled luggage',
          'Diagnose recent system alerts',
          'Check local weather & air quality'
        ].map((chip) => (
          <button
            key={chip}
            onClick={() => {
              setAiQuery(chip);
              onSend(undefined, chip);
            }}
            style={{
              padding: '4px 10px',
              borderRadius: 9999,
              background: 'rgba(15, 23, 42, 0.8)',
              border: '1px solid rgba(0, 210, 255, 0.25)',
              color: '#cbd5e1',
              fontSize: '0.7rem',
              whiteSpace: 'nowrap',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 4
            }}
          >
            <Sparkles size={11} color="#00d2ff" />
            <span>{chip}</span>
          </button>
        ))}
      </div>

      {/* Bottom Input Form */}
      <form onSubmit={(e) => onSend(e)} style={{ padding: '12px 18px', background: 'rgba(10, 20, 50, 0.95)', borderTop: '1px solid rgba(0, 210, 255, 0.2)' }}>
        <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(7, 14, 35, 0.9)', border: isHandsFreeMode ? '1px solid #10b981' : '1px solid rgba(0, 210, 255, 0.3)', borderRadius: 10, padding: '6px 12px', gap: 8 }}>
          <input
            type="text"
            placeholder={isHandsFreeMode ? "Listening hands-free... (speak or type here)" : "Message JARVIS (ask questions, execute tasks, analyze cameras, solve math/code)..."}
            value={aiQuery}
            onChange={(e) => setAiQuery(e.target.value)}
            disabled={aiLoading}
            style={{ flex: 1, background: 'transparent', border: 'none', color: '#fff', fontSize: '0.84rem', outline: 'none' }}
          />

          <button
            type="button"
            onClick={onVoiceInput}
            title="Speech-to-Text Input"
            style={{ background: 'transparent', border: 'none', color: isHandsFreeMode ? '#10b981' : '#00d2ff', cursor: 'pointer', padding: 4 }}
          >
            <Mic size={18} />
          </button>

          <button
            type="submit"
            disabled={aiLoading || !aiQuery.trim()}
            style={{
              background: 'linear-gradient(135deg, #00d2ff 0%, #2563eb 100%)',
              border: 'none',
              borderRadius: 8,
              padding: '6px 14px',
              color: '#fff',
              fontSize: '0.78rem',
              fontWeight: 700,
              cursor: aiLoading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            <Send size={13} /> Send
          </button>
        </div>
      </form>
    </div>
  );
};
