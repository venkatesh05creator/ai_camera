import React, { useState } from 'react';
import { 
  Clock, 
  Trash2, 
  Plus, 
  MessageSquare, 
  ShieldCheck, 
  Lock, 
  CheckCircle2, 
  Search 
} from 'lucide-react';

interface ConversationsMemoryModuleProps {
  conversations?: any[];
  activeConvId?: string | null;
  onSelectConversation?: (id: string) => void;
  onDeleteConversation?: (id: string) => Promise<void>;
  onNewConversation?: () => void;
  memories?: any[];
  onAddMemory?: (key: string, value: string, category: string) => Promise<void>;
  onDeleteMemory?: (id: string) => Promise<void>;
  onBackToCommandCenter?: () => void;
}

export const ConversationsMemoryModule: React.FC<ConversationsMemoryModuleProps> = ({
  conversations = [],
  activeConvId = null,
  onSelectConversation = () => {},
  onDeleteConversation = async () => {},
  onNewConversation = () => {},
  memories = [],
  onAddMemory = async () => {},
  onDeleteMemory = async () => {},
  onBackToCommandCenter,
}) => {
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');
  const [newCat, setNewCat] = useState('preference');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleCreateMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKey.trim() || !newValue.trim()) return;
    setIsSubmitting(true);
    setFeedback(null);
    try {
      await onAddMemory(newKey.trim(), newValue.trim(), newCat);
      setFeedback(`Memory '${newKey}' saved and approved for Jarvis context.`);
      setNewKey('');
      setNewValue('');
    } catch (err: any) {
      setFeedback(`Failed to save memory: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 160px)', background: '#070f26', borderRadius: 14, border: '1px solid rgba(0, 210, 255, 0.25)', overflow: 'hidden' }}>
      {/* Top Header */}
      <div style={{ padding: '12px 18px', background: 'rgba(10, 20, 50, 0.95)', borderBottom: '1px solid rgba(0, 210, 255, 0.2)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 34, height: 34, borderRadius: 8, background: 'linear-gradient(135deg, #00d2ff 0%, #0284c7 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Clock size={18} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: '0.96rem', fontWeight: 700, color: '#ffffff' }}>Persistent Conversations & Memory Bank</span>
              <span style={{ fontSize: '0.66rem', padding: '2px 6px', borderRadius: 4, background: 'rgba(0, 210, 255, 0.15)', color: '#00d2ff', fontWeight: 600 }}>
                {memories.length} Verified Memories
              </span>
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
              Multi-session SQLite conversation history • User-approved persistent memory • Explicit memory control
            </div>
          </div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 18, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 16 }}>
        {/* Left Pane: Conversation Sessions */}
        <div style={{ background: 'rgba(11, 22, 53, 0.8)', border: '1px solid rgba(0, 210, 255, 0.2)', borderRadius: 10, padding: 16, display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <span style={{ fontSize: '0.86rem', fontWeight: 700, color: '#fff' }}>Saved Chat Sessions ({conversations.length})</span>
            <button
              onClick={onNewConversation}
              style={{ background: 'rgba(0, 210, 255, 0.15)', border: '1px solid rgba(0, 210, 255, 0.3)', borderRadius: 4, padding: '3px 8px', color: '#00d2ff', fontSize: '0.68rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}
            >
              <Plus size={11} /> New
            </button>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {conversations.map((c) => {
              const isSelected = activeConvId === c.id;
              return (
                <div
                  key={c.id}
                  onClick={() => onSelectConversation(c.id)}
                  style={{
                    padding: '8px 12px',
                    borderRadius: 6,
                    background: isSelected ? 'rgba(0, 210, 255, 0.2)' : 'rgba(7, 14, 35, 0.7)',
                    border: isSelected ? '1px solid #00d2ff' : '1px solid rgba(255, 255, 255, 0.06)',
                    cursor: 'pointer',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                  }}
                >
                  <div>
                    <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#fff' }}>
                      {c.title || `Session ${c.id.slice(0, 8)}`}
                    </div>
                    <div style={{ fontSize: '0.66rem', color: '#94a3b8' }}>
                      {new Date(c.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })} • {c.message_count || 0} messages
                    </div>
                  </div>

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteConversation(c.id);
                    }}
                    style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 4 }}
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Pane: User-Approved Memory Bank */}
        <div style={{ background: 'rgba(11, 22, 53, 0.8)', border: '1px solid rgba(0, 210, 255, 0.2)', borderRadius: 10, padding: 16, display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <span style={{ fontSize: '0.86rem', fontWeight: 700, color: '#fff' }}>Explicit User Memory Bank</span>
            <span style={{ fontSize: '0.64rem', color: '#34d399', display: 'flex', alignItems: 'center', gap: 4 }}>
              <ShieldCheck size={12} /> User-Controlled
            </span>
          </div>

          {feedback && (
            <div style={{ padding: '6px 10px', borderRadius: 4, background: 'rgba(16, 185, 129, 0.15)', color: '#86efac', fontSize: '0.72rem', marginBottom: 10 }}>
              {feedback}
            </div>
          )}

          {/* Add Memory Form */}
          <form onSubmit={handleCreateMemory} style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 14, background: 'rgba(7, 14, 35, 0.6)', padding: 10, borderRadius: 6 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                required
                type="text"
                placeholder="Memory Key (e.g. primary_language, office_gate)"
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                style={{ flex: 1, padding: '5px 8px', borderRadius: 4, background: 'rgba(0,0,0,0.5)', border: '1px solid rgba(0, 210, 255, 0.2)', color: '#fff', fontSize: '0.72rem' }}
              />
              <select
                value={newCat}
                onChange={(e) => setNewCat(e.target.value)}
                style={{ padding: '5px 8px', borderRadius: 4, background: 'rgba(0,0,0,0.5)', border: '1px solid rgba(0, 210, 255, 0.2)', color: '#fff', fontSize: '0.72rem' }}
              >
                <option value="preference">Preference</option>
                <option value="fact">Fact</option>
                <option value="rule">Rule</option>
                <option value="location">Location</option>
              </select>
            </div>

            <textarea
              required
              rows={2}
              placeholder="Memory Content / Instructions for Jarvis..."
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              style={{ width: '100%', padding: '5px 8px', borderRadius: 4, background: 'rgba(0,0,0,0.5)', border: '1px solid rgba(0, 210, 255, 0.2)', color: '#fff', fontSize: '0.72rem' }}
            />

            <button
              type="submit"
              disabled={isSubmitting}
              style={{ alignSelf: 'flex-end', background: 'linear-gradient(135deg, #00d2ff 0%, #2563eb 100%)', border: 'none', borderRadius: 4, padding: '4px 12px', color: '#fff', fontSize: '0.7rem', fontWeight: 700, cursor: isSubmitting ? 'not-allowed' : 'pointer' }}
            >
              Save Approved Memory
            </button>
          </form>

          {/* Active Memories List */}
          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {memories.map((m) => (
              <div key={m.id} style={{ padding: '8px 10px', borderRadius: 6, background: 'rgba(7, 14, 35, 0.7)', border: '1px solid rgba(255, 255, 255, 0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                    <span style={{ fontSize: '0.76rem', fontWeight: 700, color: '#00d2ff' }}>{m.memory_key}</span>
                    <span style={{ fontSize: '0.6rem', padding: '1px 5px', borderRadius: 3, background: 'rgba(255, 255, 255, 0.08)', color: '#94a3b8', textTransform: 'uppercase' }}>
                      {m.category}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.72rem', color: '#cbd5e1' }}>{m.memory_value}</div>
                </div>

                <button
                  onClick={() => onDeleteMemory(m.id)}
                  style={{ background: 'transparent', border: 'none', color: '#f87171', cursor: 'pointer', padding: 2 }}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
