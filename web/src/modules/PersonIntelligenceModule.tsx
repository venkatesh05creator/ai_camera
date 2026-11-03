import React, { useState } from 'react';
import { 
  Users, 
  ShieldCheck, 
  Plus, 
  Trash2, 
  Search, 
  Eye, 
  UserCheck, 
  Lock, 
  CheckCircle2, 
  AlertCircle, 
  FileText 
} from 'lucide-react';
import { Person } from '../types';

interface EnrolledPerson {
  id: string;
  name: string;
  role: string;
  age?: number;
  gender?: string;
  is_consented: boolean;
  templates_count: number;
  last_seen?: string;
  notes?: string;
}

interface PersonIntelligenceModuleProps {
  people?: EnrolledPerson[];
  onEnrollPerson?: (name: string, role: string, notes?: string, isConsented?: boolean) => Promise<void>;
  onDeletePerson?: (id: string) => Promise<void>;
  onBackToCommandCenter?: () => void;
}

export const PersonIntelligenceModule: React.FC<PersonIntelligenceModuleProps> = ({
  people = [],
  onEnrollPerson = async () => {},
  onDeletePerson = async () => {},
  onBackToCommandCenter,
}) => {
  const [activeTab, setActiveTab] = useState<'enrolled' | 'unknown' | 'verification' | 'enroll'>('enrolled');
  const [searchQuery, setSearchQuery] = useState('');
  const [newName, setNewName] = useState('');
  const [newRole, setNewRole] = useState('Authorized Member');
  const [newNotes, setNewNotes] = useState('');
  const [consentConfirmed, setConsentConfirmed] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  // Simulated live unknown observations (temporary anonymous tracking IDs per Part 7)
  const unknownObservations = [
    {
      temp_id: 'P-014',
      camera_name: 'Laptop Primary Webcam',
      location: 'Workstation Room',
      timestamp: 'Today, 12:28:40 UTC',
      confidence: 0.94,
      clothing_upper: 'Dark blue jacket',
      clothing_lower: 'Dark trousers',
      accessories: 'Eyeglasses',
      frame_position: 'Center (X: 0.48, Y: 0.52)',
      movement_direction: 'Stationary / Facing camera',
      review_status: 'Unreviewed',
    },
    {
      temp_id: 'P-015',
      camera_name: 'Workstation Node 0',
      location: 'Main Desk',
      timestamp: 'Today, 12:15:12 UTC',
      confidence: 0.91,
      clothing_upper: 'Grey sweater',
      clothing_lower: 'Jeans',
      accessories: 'None visible',
      frame_position: 'Right corridor (X: 0.72, Y: 0.44)',
      movement_direction: 'Approaching entrance',
      review_status: 'Unreviewed',
    }
  ];

  const handleEnroll = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setIsSubmitting(true);
    setFeedback(null);
    try {
      await onEnrollPerson(newName.trim(), newRole.trim(), newNotes.trim(), consentConfirmed);
      setFeedback(`Identity '${newName}' enrolled successfully with explicit consent record.`);
      setNewName('');
      setNewNotes('');
      setActiveTab('enrolled');
    } catch (err: any) {
      setFeedback(`Enrollment failed: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredPeople = people.filter((p) =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.role.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 160px)', background: '#070f26', borderRadius: 14, border: '1px solid rgba(0, 210, 255, 0.25)', overflow: 'hidden' }}>
      {/* Top Header */}
      <div style={{ padding: '12px 18px', background: 'rgba(10, 20, 50, 0.95)', borderBottom: '1px solid rgba(0, 210, 255, 0.2)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 34, height: 34, borderRadius: 8, background: 'linear-gradient(135deg, #00d2ff 0%, #2563eb 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Users size={18} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: '0.96rem', fontWeight: 700, color: '#ffffff' }}>Person Identification & Intelligence Center</span>
              <span style={{ fontSize: '0.66rem', padding: '2px 6px', borderRadius: 4, background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', fontWeight: 600 }}>
                ● Strict Privacy & Consent Active
              </span>
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
              Consented enrolled profiles • Anonymous unknown detections • Calibrated confidence • Zero sensitive attribute guessing
            </div>
          </div>
        </div>

        {/* Tab Switcher */}
        <div style={{ display: 'flex', background: 'rgba(7, 14, 35, 0.8)', padding: 3, borderRadius: 6, border: '1px solid rgba(0, 210, 255, 0.2)' }}>
          {[
            { id: 'enrolled', label: `Consented Profiles (${people.length})` },
            { id: 'unknown', label: `Unknown Detections (${unknownObservations.length})` },
            { id: 'verification', label: 'Biometric Verification' },
            { id: 'enroll', label: '+ Enroll Person' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              style={{
                padding: '4px 10px',
                borderRadius: 4,
                fontSize: '0.72rem',
                fontWeight: activeTab === tab.id ? 700 : 500,
                background: activeTab === tab.id ? 'linear-gradient(135deg, #00d2ff 0%, #2563eb 100%)' : 'transparent',
                border: 'none',
                color: activeTab === tab.id ? '#ffffff' : '#94a3b8',
                cursor: 'pointer'
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
        {feedback && (
          <div style={{ padding: '8px 14px', borderRadius: 6, background: feedback.includes('failed') ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)', border: feedback.includes('failed') ? '1px solid #ef4444' : '1px solid #10b981', color: feedback.includes('failed') ? '#fca5a5' : '#86efac', fontSize: '0.78rem' }}>
            {feedback}
          </div>
        )}

        {/* TAB 1: Consented Profiles */}
        {activeTab === 'enrolled' && (
          <>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', background: 'rgba(11, 22, 53, 0.8)', border: '1px solid rgba(0, 210, 255, 0.25)', borderRadius: 8, padding: '6px 12px', gap: 8 }}>
                <Search size={14} color="#00d2ff" />
                <input
                  type="text"
                  placeholder="Search enrolled profiles by name or role..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{ flex: 1, background: 'transparent', border: 'none', color: '#fff', fontSize: '0.78rem', outline: 'none' }}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
              {filteredPeople.map((p) => (
                <div key={p.id} style={{ background: 'rgba(11, 22, 53, 0.85)', border: '1px solid rgba(0, 210, 255, 0.2)', borderRadius: 10, padding: 14, display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                  <div style={{ width: 44, height: 44, borderRadius: 8, background: 'linear-gradient(135deg, #1e40af 0%, #3b82f6 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 700, fontSize: '1.1rem', flexShrink: 0 }}>
                    {p.name.charAt(0).toUpperCase()}
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                      <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#fff' }}>{p.name}</div>
                      <span style={{ fontSize: '0.62rem', padding: '1px 6px', borderRadius: 4, background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 3 }}>
                        <ShieldCheck size={10} /> CONSENTED
                      </span>
                    </div>

                    <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginBottom: 6 }}>
                      {p.role} • {p.age ? `Age: ${p.age}` : 'Age: N/A'}
                    </div>

                    <div style={{ fontSize: '0.68rem', color: '#64748b', display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <span>Biometric Templates: <strong>{p.templates_count > 0 ? `${p.templates_count} Encrypted (AES-GCM)` : 'None'}</strong></span>
                      <span>Last Seen: <strong>{p.last_seen || 'Recently active'}</strong></span>
                      {p.notes && <span style={{ fontStyle: 'italic', color: '#94a3b8' }}>Notes: {p.notes}</span>}
                    </div>

                    <div style={{ marginTop: 10, display: 'flex', gap: 6 }}>
                      <button
                        onClick={() => onDeletePerson(p.id)}
                        style={{ padding: '3px 8px', borderRadius: 4, background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#f87171', fontSize: '0.66rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 3 }}
                      >
                        <Trash2 size={10} /> Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {/* TAB 2: Anonymous Unknown Detections */}
        {activeTab === 'unknown' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ padding: '8px 12px', background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.3)', borderRadius: 6, color: '#fcd34d', fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: 6 }}>
              <AlertCircle size={14} color="#f59e0b" />
              <span><strong>Privacy Policy:</strong> Unknown persons remain strictly anonymous with temporary IDs. Visual appearance descriptions (clothing, accessories, movement) are stored without guessing age, gender, ethnicity, or personal identity.</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 12 }}>
              {unknownObservations.map((obs) => (
                <div key={obs.temp_id} style={{ background: 'rgba(11, 22, 53, 0.85)', border: '1px solid rgba(0, 210, 255, 0.2)', borderRadius: 10, padding: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: '0.84rem', fontWeight: 700, color: '#00d2ff' }}>Observation #{obs.temp_id}</span>
                      <span style={{ fontSize: '0.62rem', padding: '1px 5px', borderRadius: 4, background: 'rgba(255, 255, 255, 0.08)', color: '#94a3b8' }}>
                        Temporary Track ID
                      </span>
                    </div>
                    <span style={{ fontSize: '0.66rem', color: '#34d399', fontWeight: 600 }}>Confidence: {(obs.confidence * 100).toFixed(0)}%</span>
                  </div>

                  <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginBottom: 8 }}>
                    Recorded at: <strong>{obs.camera_name} ({obs.location})</strong> • {obs.timestamp}
                  </div>

                  <div style={{ background: 'rgba(7, 14, 35, 0.7)', borderRadius: 6, padding: '8px 10px', fontSize: '0.7rem', color: '#cbd5e1', display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <div>• <strong>Upper Clothing:</strong> {obs.clothing_upper}</div>
                    <div>• <strong>Lower Clothing:</strong> {obs.clothing_lower}</div>
                    <div>• <strong>Visible Accessories:</strong> {obs.accessories}</div>
                    <div>• <strong>Frame Coordinates:</strong> {obs.frame_position}</div>
                    <div>• <strong>Movement Direction:</strong> {obs.movement_direction}</div>
                  </div>

                  <div style={{ marginTop: 10, display: 'flex', justifyContent: 'flex-end', gap: 6 }}>
                    <button
                      onClick={() => {
                        setNewNotes(`Observed as ${obs.temp_id} in ${obs.clothing_upper} at ${obs.camera_name}`);
                        setActiveTab('enroll');
                      }}
                      style={{ padding: '4px 10px', borderRadius: 4, background: 'rgba(0, 210, 255, 0.15)', border: '1px solid rgba(0, 210, 255, 0.3)', color: '#00d2ff', fontSize: '0.7rem', cursor: 'pointer' }}
                    >
                      Enroll with Consent
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 3: Biometric Verification Tool */}
        {activeTab === 'verification' && (
          <div style={{ background: 'rgba(11, 22, 53, 0.85)', border: '1px solid rgba(0, 210, 255, 0.2)', borderRadius: 10, padding: 18 }}>
            <h3 style={{ margin: '0 0 10px 0', fontSize: '0.9rem', color: '#00d2ff', display: 'flex', alignItems: 'center', gap: 6 }}>
              <UserCheck size={16} /> Calibrated Face Verification Pipeline
            </h3>
            <p style={{ fontSize: '0.74rem', color: '#94a3b8', margin: '0 0 14px 0' }}>
              Verification is performed strictly against consented enrolled templates. Calibrated confidence measures are reported honestly:
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10, marginBottom: 16 }}>
              {[
                { title: '1. VERIFIED ENROLLED PERSON', desc: 'Calibrated similarity > 0.82 with consenting profile', color: '#10b981' },
                { title: '2. POSSIBLE MATCH — REVIEW', desc: 'Similarity between 0.65 - 0.81, human verification required', color: '#f59e0b' },
                { title: '3. UNKNOWN PERSON', desc: 'No biometric match found in consenting registry', color: '#00d2ff' },
                { title: '4. INSUFFICIENT QUALITY', desc: 'Low resolution, severe angle, or poor illumination', color: '#ef4444' },
                { title: '5. VERIFICATION UNAVAILABLE', desc: 'Camera offline or consent withdrawn', color: '#64748b' },
              ].map((state) => (
                <div key={state.title} style={{ padding: '10px 12px', borderRadius: 6, background: 'rgba(7, 14, 35, 0.8)', border: `1px solid ${state.color}` }}>
                  <div style={{ fontSize: '0.72rem', fontWeight: 700, color: state.color, marginBottom: 4 }}>{state.title}</div>
                  <div style={{ fontSize: '0.66rem', color: '#94a3b8' }}>{state.desc}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 4: Enroll Consenting Person */}
        {activeTab === 'enroll' && (
          <div style={{ background: 'rgba(11, 22, 53, 0.85)', border: '1px solid rgba(0, 210, 255, 0.2)', borderRadius: 10, padding: 18, maxWidth: 600 }}>
            <h3 style={{ margin: '0 0 10px 0', fontSize: '0.9rem', color: '#00d2ff', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Plus size={16} /> Enroll New Authorized Identity
            </h3>

            <form onSubmit={handleEnroll} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.7rem', color: '#94a3b8', marginBottom: 4 }}>Full Name</label>
                <input
                  required
                  type="text"
                  placeholder="e.g. John Doe"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  style={{ width: '100%', padding: '7px 10px', borderRadius: 6, background: 'rgba(7, 14, 35, 0.9)', border: '1px solid rgba(0, 210, 255, 0.2)', color: '#fff', fontSize: '0.78rem' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.7rem', color: '#94a3b8', marginBottom: 4 }}>Role / Relationship</label>
                <input
                  type="text"
                  placeholder="e.g. Owner, Family Member, Resident, Authorized Staff"
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value)}
                  style={{ width: '100%', padding: '7px 10px', borderRadius: 6, background: 'rgba(7, 14, 35, 0.9)', border: '1px solid rgba(0, 210, 255, 0.2)', color: '#fff', fontSize: '0.78rem' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.7rem', color: '#94a3b8', marginBottom: 4 }}>Owner Notes</label>
                <textarea
                  rows={2}
                  placeholder="Optional context, schedules or access rules..."
                  value={newNotes}
                  onChange={(e) => setNewNotes(e.target.value)}
                  style={{ width: '100%', padding: '7px 10px', borderRadius: 6, background: 'rgba(7, 14, 35, 0.9)', border: '1px solid rgba(0, 210, 255, 0.2)', color: '#fff', fontSize: '0.78rem' }}
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', background: 'rgba(16, 185, 129, 0.1)', borderRadius: 6, border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                <input
                  type="checkbox"
                  id="consentCheck"
                  checked={consentConfirmed}
                  onChange={(e) => setConsentConfirmed(e.target.checked)}
                />
                <label htmlFor="consentCheck" style={{ fontSize: '0.72rem', color: '#86efac', cursor: 'pointer' }}>
                  I confirm explicit, voluntary consent has been granted for biometric verification under the application privacy policy.
                </label>
              </div>

              <button
                type="submit"
                disabled={isSubmitting || !consentConfirmed}
                style={{
                  background: 'linear-gradient(135deg, #00d2ff 0%, #2563eb 100%)',
                  border: 'none',
                  borderRadius: 6,
                  padding: '8px 18px',
                  color: '#fff',
                  fontSize: '0.78rem',
                  fontWeight: 700,
                  cursor: (isSubmitting || !consentConfirmed) ? 'not-allowed' : 'pointer'
                }}
              >
                {isSubmitting ? 'Saving...' : 'Enroll Profile'}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};
