import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Send,
  Shield,
  Bot,
  User,
  CheckCircle,
  AlertTriangle,
  Globe,
  Camera,
  Activity,
  FileText,
  Search,
} from 'lucide-react';
import { api } from '../services/api';
import { AICopilotResponse } from '../types';

interface Message {
  id: string;
  sender: 'user' | 'ai';
  text: string;
  data?: any;
  suggestedActions?: string[];
  timestamp: string;
}

export const AICopilotView: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      sender: 'ai',
      text: 'Aegis AI Intelligence Copilot online. I analyze real-time camera telemetry, verify enrolled profiles with FaceNet 512-dim biometrics, and perform online directory and background investigations. How can I assist you?',
      suggestedActions: [
        'Daily Executive Security Briefing',
        'Analyze Laptop Primary Webcam',
        'Run Online Background Scan on Staff',
        'Audit Consent & Privacy Compliance',
      ],
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [inputQuery, setInputQuery] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSend = async (queryToSend: string) => {
    const q = queryToSend.trim();
    if (!q || loading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: q,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuery('');
    setLoading(true);

    try {
      const res: AICopilotResponse = await api.askCopilot(q);
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'ai',
        text: res.answer,
        data: res.data,
        suggestedActions: res.suggested_actions,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err: any) {
      const errMsg: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'ai',
        text: `Analysis error: ${err.message || 'Failed to communicate with intelligence engine.'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-scroll-container ai-copilot-page-container">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '44px',
              height: '44px',
              borderRadius: '12px',
              background: 'linear-gradient(135deg, #6366f1 0%, #3b82f6 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 20px rgba(99, 102, 241, 0.4)',
            }}
          >
            <Sparkles size={24} color="#ffffff" />
          </div>
          <div>
            <h1 style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
              AI Intelligence Copilot
            </h1>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '2px 0 0' }}>
              Natural language surveillance reasoning, online background intelligence, and situational queries
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '0.75rem', background: 'rgba(16, 185, 129, 0.1)', color: '#34d399', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '4px 10px', borderRadius: '6px', fontWeight: 600 }}>
            • Neural Engine 2.0 Active
          </span>
        </div>
      </div>

      {/* Preset Chips */}
      <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '4px' }}>
        {[
          'Daily Executive Security Briefing',
          'Analyze Laptop Primary Webcam',
          'Run Online Background Scan on Staff',
          'Check Active Security Alerts',
          'Audit Consent & Privacy Compliance',
        ].map((chip, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(chip)}
            disabled={loading}
            style={{
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              padding: '6px 12px',
              color: 'var(--text-main)',
              fontSize: '0.78rem',
              fontWeight: 500,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              transition: 'all 0.15s ease',
            }}
          >
            {chip}
          </button>
        ))}
      </div>

      {/* Messages Scroll Area */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
          paddingRight: '6px',
        }}
      >
        {messages.map((m) => {
          const isAi = m.sender === 'ai';
          return (
            <div
              key={m.id}
              style={{
                display: 'flex',
                gap: '12px',
                alignItems: 'flex-start',
                maxWidth: isAi ? '85%' : '75%',
                alignSelf: isAi ? 'flex-start' : 'flex-end',
              }}
            >
              {isAi && (
                <div
                  style={{
                    width: '34px',
                    height: '34px',
                    borderRadius: '10px',
                    background: 'linear-gradient(135deg, #6366f1 0%, #3b82f6 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  <Bot size={18} color="#ffffff" />
                </div>
              )}

              <div
                style={{
                  background: isAi ? 'var(--bg-card, #141822)' : 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
                  border: isAi ? '1px solid var(--border-subtle)' : 'none',
                  borderRadius: '12px',
                  padding: '14px 18px',
                  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.2)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px', gap: '16px' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: isAi ? '#818cf8' : '#e0e7ff', textTransform: 'uppercase' }}>
                    {isAi ? 'Aegis Copilot' : 'Operator'}
                  </span>
                  <span style={{ fontSize: '0.7rem', color: isAi ? 'var(--text-faint)' : '#c7d2fe' }}>
                    {m.timestamp}
                  </span>
                </div>

                <p style={{ fontSize: '0.9rem', color: '#ffffff', lineHeight: 1.6, margin: 0 }}>
                  {m.text}
                </p>

                {/* Structured Data View if present */}
                {m.data && Array.isArray(m.data) && (
                  <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {m.data.map((item: any, idx: number) => (
                      <div
                        key={idx}
                        style={{
                          padding: '10px 12px',
                          background: 'rgba(0, 0, 0, 0.25)',
                          borderRadius: '8px',
                          border: '1px solid rgba(255, 255, 255, 0.05)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          fontSize: '0.82rem',
                        }}
                      >
                        <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>{item.name || item.title || JSON.stringify(item)}</span>
                        {item.role && (
                          <span style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', padding: '2px 8px', borderRadius: '4px', fontSize: '0.72rem' }}>
                            {item.role}
                          </span>
                        )}
                        {item.severity && (
                          <span style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#f87171', padding: '2px 8px', borderRadius: '4px', fontSize: '0.72rem' }}>
                            {item.severity}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Suggested Action Chips */}
                {m.suggestedActions && m.suggestedActions.length > 0 && (
                  <div style={{ marginTop: '14px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {m.suggestedActions.map((act, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSend(act)}
                        style={{
                          background: 'rgba(99, 102, 241, 0.12)',
                          border: '1px solid rgba(99, 102, 241, 0.25)',
                          color: '#818cf8',
                          padding: '4px 10px',
                          borderRadius: '6px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        → {act}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {!isAi && (
                <div
                  style={{
                    width: '34px',
                    height: '34px',
                    borderRadius: '10px',
                    background: '#334155',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  <User size={18} color="#ffffff" />
                </div>
              )}
            </div>
          );
        })}

        {loading && (
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            <Sparkles size={18} className="spin-icon" color="#818cf8" />
            <span>Analyzing surveillance intelligence...</span>
          </div>
        )}
      </div>

      {/* Input Bar */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend(inputQuery);
        }}
        style={{
          display: 'flex',
          gap: '10px',
          background: 'var(--bg-card, #11141c)',
          border: '1px solid var(--border-subtle)',
          borderRadius: '12px',
          padding: '8px 12px',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)',
        }}
      >
        <input
          type="text"
          placeholder="Ask AI Copilot (e.g. 'Who is Venkatesh?', 'Analyze camera 0', 'Check online records')..."
          value={inputQuery}
          onChange={(e) => setInputQuery(e.target.value)}
          disabled={loading}
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            color: 'var(--text-main)',
            fontSize: '0.9rem',
            outline: 'none',
            padding: '6px 8px',
          }}
        />
        <button
          type="submit"
          disabled={loading || !inputQuery.trim()}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: 'linear-gradient(135deg, #6366f1 0%, #3b82f6 100%)',
            border: 'none',
            borderRadius: '8px',
            color: '#ffffff',
            padding: '0 18px',
            fontWeight: 600,
            fontSize: '0.85rem',
            cursor: 'pointer',
            opacity: loading || !inputQuery.trim() ? 0.5 : 1,
          }}
        >
          <Send size={16} />
          Send
        </button>
      </form>
    </div>
  );
};
