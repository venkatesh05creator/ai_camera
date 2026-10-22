import React, { useEffect, useState } from 'react';
import { Person } from '../types';
import { api } from '../services/api';
import { Users, UserPlus, Search, ShieldCheck, ShieldAlert, Trash2, Calendar, Mail, FileText, CheckCircle2, AlertCircle, Sparkles, Globe } from 'lucide-react';
import { AIDossierModal } from '../components/AIDossierModal';

export const PeopleDirectory: React.FC = () => {
  const [people, setPeople] = useState<Person[]>([]);
  const [search, setSearch] = useState('');
  const [selectedPerson, setSelectedPerson] = useState<Person | null>(null);
  const [dossierPerson, setDossierPerson] = useState<Person | null>(null);
  const [showModal, setShowModal] = useState(false);

  // Enrollment modal state
  const [wizardStep, setWizardStep] = useState(1);
  const [formName, setFormName] = useState('');
  const [formAge, setFormAge] = useState<number | undefined>(undefined);
  const [formGender, setFormGender] = useState('');
  const [formRole, setFormRole] = useState('resident');
  const [formContact, setFormContact] = useState('');
  const [formNotes, setFormNotes] = useState('');
  const [formConsent, setFormConsent] = useState(false);
  const [photoBase64, setPhotoBase64] = useState<string | null>(null);
  const [enrollMsg, setEnrollMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchPeople = () => {
    api.getPeople(search).then(setPeople).catch(() => {});
  };

  useEffect(() => {
    fetchPeople();
  }, [search]);

  const handleWithdrawConsent = async (person: Person) => {
    if (!confirm(`Are you sure you want to withdraw consent for "${person.name}"? This immediately purges all encrypted biometric templates and sets status to withdrawn.`)) {
      return;
    }
    try {
      await api.withdrawConsent(person.id);
      fetchPeople();
      if (selectedPerson?.id === person.id) {
        setSelectedPerson(null);
      }
    } catch (err: any) {
      alert(`Error withdrawing consent: ${err.message}`);
    }
  };

  const handleDeletePerson = async (person: Person) => {
    if (!confirm(`Permanently delete profile for "${person.name}"?`)) return;
    try {
      await api.deletePerson(person.id);
      fetchPeople();
      if (selectedPerson?.id === person.id) {
        setSelectedPerson(null);
      }
    } catch (err: any) {
      alert(`Error deleting person: ${err.message}`);
    }
  };

  const handlePhotoSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = () => {
        setPhotoBase64(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleFinishEnrollment = async () => {
    if (!formName.trim()) {
      setEnrollMsg({ type: 'error', text: 'Name is required' });
      return;
    }
    if (!formConsent) {
      setEnrollMsg({ type: 'error', text: 'Explicit consent is mandatory under the privacy policy.' });
      return;
    }

    try {
      setEnrollMsg(null);
      // 1. Create person profile
      const newPerson = await api.createPerson({
        name: formName,
        age: formAge,
        gender: formGender || 'Self-Reported',
        role_relationship: formRole,
        contact_details: formContact,
        notes: formNotes,
        photo_base64: photoBase64 || undefined,
      });

      // 2. If photo supplied, extract and encrypt biometric template
      if (photoBase64) {
        await api.enrollFaceImage(newPerson.id, photoBase64);
      }

      fetchPeople();
      setShowModal(false);
      resetModal();
    } catch (err: any) {
      setEnrollMsg({ type: 'error', text: err.message });
    }
  };

  const resetModal = () => {
    setWizardStep(1);
    setFormName('');
    setFormAge(undefined);
    setFormGender('');
    setFormRole('resident');
    setFormContact('');
    setFormNotes('');
    setFormConsent(false);
    setPhotoBase64(null);
    setEnrollMsg(null);
  };

  return (
    <div className="people-directory-container">
      {/* Left List & Toolbar */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '16px', overflow: 'hidden' }}>
        {/* Search & Actions Bar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px' }}>
          <div style={{ position: 'relative', width: '360px' }}>
            <Search size={16} color="var(--text-faint)" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
            <input
              type="text"
              placeholder="Search enrolled people by name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                width: '100%',
                padding: '9px 12px 9px 36px',
                borderRadius: '8px',
                background: 'var(--bg-card)',
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-main)',
                fontSize: '0.85rem',
                outline: 'none',
              }}
            />
          </div>

          <button onClick={() => { resetModal(); setShowModal(true); }} className="btn-primary">
            <UserPlus size={16} />
            <span>Enroll New Person</span>
          </button>
        </div>

        {/* Profiles Grid */}
        <div style={{ flex: 1, overflowY: 'auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '14px', alignContent: 'start' }}>
          {people.length === 0 ? (
            <div style={{ gridColumn: '1 / -1', padding: '60px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
              <Users size={48} color="var(--text-faint)" style={{ margin: '0 auto 12px' }} />
              <p style={{ fontWeight: 600 }}>No Enrolled Profiles Found</p>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-faint)' }}>Only consenting individuals are registered in this directory.</p>
            </div>
          ) : (
            people.map((p) => {
              const isSelected = selectedPerson?.id === p.id;
              return (
                <div
                  key={p.id}
                  onClick={() => setSelectedPerson(p)}
                  className="glass-card glass-card-interactive"
                  style={{
                    padding: '16px',
                    cursor: 'pointer',
                    borderColor: isSelected ? 'var(--accent-primary)' : 'var(--border-subtle)',
                    background: isSelected ? 'rgba(99, 102, 241, 0.08)' : 'var(--bg-glass)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                    <div style={{ width: '46px', height: '46px', borderRadius: '50%', background: 'linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '1.1rem', color: '#fff', flexShrink: 0 }}>
                      {p.name.charAt(0).toUpperCase()}
                    </div>
                    <div style={{ flex: 1, overflow: 'hidden' }}>
                      <h4 style={{ fontSize: '0.98rem', fontWeight: 700, color: 'var(--text-main)', margin: 0, textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                        {p.name}
                      </h4>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                        {p.role_relationship} • Age: {p.age || 'N/A'}
                      </span>
                    </div>
                    {p.consent_active ? (
                      <span className="badge-tag badge-success" title="Active Consent on file">
                        <ShieldCheck size={12} />
                        <span>CONSENTED</span>
                      </span>
                    ) : (
                      <span className="badge-tag badge-danger" title="Consent Withdrawn">
                        <ShieldAlert size={12} />
                        <span>WITHDRAWN</span>
                      </span>
                    )}
                  </div>

                  <div style={{ fontSize: '0.76rem', color: 'var(--text-faint)', display: 'flex', flexDirection: 'column', gap: '4px', borderTop: '1px solid var(--border-subtle)', paddingTop: '10px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span>Templates: {p.templates_count > 0 ? `${p.templates_count} Encrypted (AES-GCM)` : 'None'}</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setDossierPerson(p);
                        }}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          background: 'rgba(99, 102, 241, 0.15)',
                          border: '1px solid rgba(99, 102, 241, 0.3)',
                          color: '#818cf8',
                          padding: '3px 8px',
                          borderRadius: '6px',
                          fontSize: '0.72rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        <Sparkles size={11} />
                        AI Dossier
                      </button>
                    </div>
                    <span>Last Seen: {p.last_seen_at ? new Date(p.last_seen_at).toLocaleDateString() : 'Never'}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Right Drawer: Selected Profile Detail */}
      {selectedPerson && (
        <div className="glass-card" style={{ width: '380px', padding: '24px', display: 'flex', flexDirection: 'column', gap: '18px', overflowY: 'auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0 }}>Profile Details</h3>
            <button onClick={() => setSelectedPerson(null)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1.2rem' }}>✕</button>
          </div>

          <div style={{ textAlign: 'center', padding: '16px 0' }}>
            <div style={{ width: '72px', height: '72px', borderRadius: '50%', background: 'linear-gradient(135deg, #6366f1 0%, #3b82f6 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '1.8rem', color: '#fff', margin: '0 auto 10px' }}>
              {selectedPerson.name.charAt(0).toUpperCase()}
            </div>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0 }}>{selectedPerson.name}</h2>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Role: {selectedPerson.role_relationship}</span>
          </div>

          {/* AI Intelligence Action Card */}
          <button
            onClick={() => setDossierPerson(selectedPerson)}
            style={{
              background: 'linear-gradient(135deg, #6366f1 0%, #3b82f6 100%)',
              color: '#ffffff',
              border: 'none',
              padding: '11px 16px',
              borderRadius: '10px',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              boxShadow: '0 0 16px rgba(99, 102, 241, 0.4)',
            }}
          >
            <Sparkles size={16} />
            <span>Open AI Intelligence Dossier</span>
          </button>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.84rem' }}>
            <div style={{ background: 'rgba(255,255,255,0.02)', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-faint)', textTransform: 'uppercase' }}>Age & Gender (Self-Reported)</span>
              <p style={{ margin: '4px 0 0', fontWeight: 600 }}>{selectedPerson.age || 'Not provided'} • {selectedPerson.gender || 'Not specified'}</p>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.02)', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-faint)', textTransform: 'uppercase' }}>Contact Information</span>
              <p style={{ margin: '4px 0 0', fontWeight: 600 }}>{selectedPerson.contact_details || 'No contact on file'}</p>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.02)', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-faint)', textTransform: 'uppercase' }}>Notes / Authorization Scope</span>
              <p style={{ margin: '4px 0 0', color: 'var(--text-muted)' }}>{selectedPerson.notes || 'None recorded'}</p>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.02)', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-faint)', textTransform: 'uppercase' }}>Consent & Biometrics</span>
              <p style={{ margin: '4px 0 0', color: selectedPerson.consent_active ? '#34d399' : '#f87171', fontWeight: 600 }}>
                {selectedPerson.consent_active ? 'Active Verification Consent' : 'Consent Withdrawn - Biometrics Purged'}
              </p>
            </div>
          </div>

          <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: '8px', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)' }}>
            {selectedPerson.consent_active && (
              <button
                onClick={() => handleWithdrawConsent(selectedPerson)}
                style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', border: '1px solid rgba(245, 158, 11, 0.3)', padding: '9px', borderRadius: '8px', cursor: 'pointer', fontWeight: 600, fontSize: '0.82rem' }}
              >
                Withdraw Consent & Purge Biometrics
              </button>
            )}

            <button
              onClick={() => handleDeletePerson(selectedPerson)}
              style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '9px', borderRadius: '8px', cursor: 'pointer', fontWeight: 600, fontSize: '0.82rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
            >
              <Trash2 size={14} />
              <span>Delete Person Profile</span>
            </button>
          </div>
        </div>
      )}

      {/* Enrollment Wizard Modal */}
      {showModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div className="glass-card" style={{ width: '520px', padding: '28px', background: 'var(--bg-card)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
              <div>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 700, margin: 0 }}>Enroll Person Profile</h3>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Step {wizardStep} of 2</span>
              </div>
              <button onClick={() => setShowModal(false)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '1.2rem', cursor: 'pointer' }}>✕</button>
            </div>

            {enrollMsg && (
              <div style={{ padding: '8px 12px', borderRadius: '6px', marginBottom: '14px', fontSize: '0.82rem', background: enrollMsg.type === 'error' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)', color: enrollMsg.type === 'error' ? '#f87171' : '#34d399', border: `1px solid ${enrollMsg.type === 'error' ? '#ef4444' : '#10b981'}` }}>
                {enrollMsg.text}
              </div>
            )}

            {wizardStep === 1 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>Full Name *</label>
                  <input
                    type="text"
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    placeholder="e.g. Sarah Connor"
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', background: 'var(--bg-main)', border: '1px solid var(--border-subtle)', color: '#fff', fontSize: '0.85rem' }}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <div>
                    <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>Age (User-Supplied)</label>
                    <input
                      type="number"
                      value={formAge || ''}
                      onChange={(e) => setFormAge(e.target.value ? Number(e.target.value) : undefined)}
                      placeholder="e.g. 29"
                      style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', background: 'var(--bg-main)', border: '1px solid var(--border-subtle)', color: '#fff', fontSize: '0.85rem' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>Gender (User-Supplied)</label>
                    <input
                      type="text"
                      value={formGender}
                      onChange={(e) => setFormGender(e.target.value)}
                      placeholder="e.g. Female"
                      style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', background: 'var(--bg-main)', border: '1px solid var(--border-subtle)', color: '#fff', fontSize: '0.85rem' }}
                    />
                  </div>
                </div>

                <div>
                  <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>Role / Relationship</label>
                  <select
                    value={formRole}
                    onChange={(e) => setFormRole(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', background: 'var(--bg-main)', border: '1px solid var(--border-subtle)', color: '#fff', fontSize: '0.85rem' }}
                  >
                    <option value="owner">Owner</option>
                    <option value="resident">Resident</option>
                    <option value="employee">Staff / Employee</option>
                    <option value="authorized_visitor">Authorized Visitor</option>
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>Contact Details</label>
                  <input
                    type="text"
                    value={formContact}
                    onChange={(e) => setFormContact(e.target.value)}
                    placeholder="email or phone number"
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', background: 'var(--bg-main)', border: '1px solid var(--border-subtle)', color: '#fff', fontSize: '0.85rem' }}
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '12px' }}>
                  <button onClick={() => setWizardStep(2)} className="btn-primary">
                    Next: Consent & Photo →
                  </button>
                </div>
              </div>
            )}

            {wizardStep === 2 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {/* Mandatory Consent Checkbox */}
                <div style={{ background: 'rgba(99, 102, 241, 0.08)', padding: '14px', borderRadius: '8px', border: '1px solid rgba(99, 102, 241, 0.25)' }}>
                  <label style={{ display: 'flex', gap: '10px', alignItems: 'flex-start', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={formConsent}
                      onChange={(e) => setFormConsent(e.target.checked)}
                      style={{ marginTop: '3px' }}
                    />
                    <span style={{ fontSize: '0.8rem', color: '#cbd5e1', lineHeight: 1.4 }}>
                      <strong>Consent Confirmation:</strong> I confirm that {formName || 'this person'} has explicitly consented to having an encrypted biometric face template stored for authorized camera verification.
                    </span>
                  </label>
                </div>

                {/* Photo Upload */}
                <div>
                  <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>Face Photo (Optional for immediate extraction)</label>
                  <input type="file" accept="image/*" onChange={handlePhotoSelect} style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }} />
                  {photoBase64 && (
                    <div style={{ marginTop: '10px', textAlign: 'center' }}>
                      <img src={photoBase64} alt="Preview" style={{ width: '80px', height: '80px', borderRadius: '50%', objectFit: 'cover', border: '2px solid var(--accent-primary)' }} />
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '16px' }}>
                  <button onClick={() => setWizardStep(1)} className="btn-secondary">
                    ← Back
                  </button>
                  <button onClick={handleFinishEnrollment} className="btn-primary" disabled={!formConsent}>
                    Complete Enrollment
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* AI Intelligence Dossier Modal */}
      {dossierPerson && (
        <AIDossierModal
          isOpen={Boolean(dossierPerson)}
          personId={dossierPerson.id}
          personName={dossierPerson.name}
          onClose={() => setDossierPerson(null)}
        />
      )}
    </div>
  );
};
