import React, { useState } from 'react';

interface SettingsModuleProps {
  onBackToCommandCenter?: () => void;
}

export const SettingsModule: React.FC<SettingsModuleProps> = ({
  onBackToCommandCenter,
}) => {
  const [activeTab, setActiveTab] = useState<'assistant' | 'voice' | 'vision' | 'security' | 'privacy'>('assistant');
  const [savedNotice, setSavedNotice] = useState(false);

  // Settings State
  const [assistantName, setAssistantName] = useState('Jarvis');
  const [personality, setPersonality] = useState('jarvis_classic');
  const [ttsSpeed, setTtsSpeed] = useState('1.0');
  const [wakeWordEnabled, setWakeWordEnabled] = useState(true);
  const [faceThreshold, setFaceThreshold] = useState('0.60');
  const [consentEnforced, setConsentEnforced] = useState(true);
  const [soundAlerts, setSoundAlerts] = useState(true);
  const [defaultCity, setDefaultCity] = useState('Bengaluru');

  const handleSave = () => {
    localStorage.setItem('uai_settings', JSON.stringify({
      assistantName,
      personality,
      ttsSpeed,
      wakeWordEnabled,
      faceThreshold,
      consentEnforced,
      soundAlerts,
      defaultCity,
    }));
    setSavedNotice(true);
    setTimeout(() => setSavedNotice(false), 3000);
  };

  return (
    <div className="uai-module-container" style={{ padding: '24px', color: '#f1f5f9' }}>
      {/* Breadcrumb Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <button
            onClick={onBackToCommandCenter}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#38bdf8',
              cursor: 'pointer',
              fontSize: '13px',
              padding: 0,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              marginBottom: '6px',
            }}
          >
            ← Back to Command Center
          </button>
          <h1 style={{ fontSize: '24px', fontWeight: 700, margin: 0 }}>
            System Settings & Preferences
          </h1>
          <p style={{ margin: '4px 0 0 0', color: '#94a3b8', fontSize: '13px' }}>
            Configure Jarvis assistant personality, voice parameters, camera thresholds, and security rules.
          </p>
        </div>
        <button
          onClick={handleSave}
          style={{
            background: '#2563eb',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            padding: '8px 18px',
            fontSize: '13px',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          💾 Save Changes
        </button>
      </div>

      {savedNotice && (
        <div style={{ background: '#064e3b', border: '1px solid #10b981', color: '#6ee7b7', padding: '10px 16px', borderRadius: '8px', marginBottom: '16px', fontSize: '13px' }}>
          ✓ Preferences saved successfully.
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid #334155', paddingBottom: '12px', marginBottom: '24px' }}>
        {[
          { id: 'assistant', label: '🤖 Assistant & Persona' },
          { id: 'voice', label: '🎙️ Voice & Audio' },
          { id: 'vision', label: '📷 Vision & Recognition' },
          { id: 'security', label: '🛡️ Security & Alerts' },
          { id: 'privacy', label: '🔒 Privacy & Governance' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            style={{
              background: activeTab === tab.id ? '#1e293b' : 'transparent',
              color: activeTab === tab.id ? '#38bdf8' : '#94a3b8',
              border: `1px solid ${activeTab === tab.id ? '#38bdf8' : 'transparent'}`,
              borderRadius: '6px',
              padding: '8px 14px',
              fontSize: '13px',
              cursor: 'pointer',
              fontWeight: 500,
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px', padding: '24px', maxWidth: '720px' }}>
        {activeTab === 'assistant' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                Assistant Display Name
              </label>
              <input
                type="text"
                value={assistantName}
                onChange={(e) => setAssistantName(e.target.value)}
                style={{ width: '100%', background: '#1e293b', border: '1px solid #334155', color: '#fff', padding: '8px 12px', borderRadius: '6px', fontSize: '13px' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                Tone & Behavioral Persona
              </label>
              <select
                value={personality}
                onChange={(e) => setPersonality(e.target.value)}
                style={{ width: '100%', background: '#1e293b', border: '1px solid #334155', color: '#fff', padding: '8px 12px', borderRadius: '6px', fontSize: '13px' }}
              >
                <option value="jarvis_classic">Jarvis Classic (Attentive, refined, highly analytical)</option>
                <option value="concise_operator">Concise Operator (Brief, zero fluff, telemetry-focused)</option>
                <option value="deep_engineer">Principal Engineer (Detailed technical breakdowns, code-centric)</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                Default Geographic Focus
              </label>
              <input
                type="text"
                value={defaultCity}
                onChange={(e) => setDefaultCity(e.target.value)}
                style={{ width: '100%', background: '#1e293b', border: '1px solid #334155', color: '#fff', padding: '8px 12px', borderRadius: '6px', fontSize: '13px' }}
              />
            </div>
          </div>
        )}

        {activeTab === 'voice' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600 }}>Jarvis Wake-Word Detection</div>
                <div style={{ fontSize: '12px', color: '#94a3b8' }}>Activate continuous listening when "Jarvis" is spoken</div>
              </div>
              <input
                type="checkbox"
                checked={wakeWordEnabled}
                onChange={(e) => setWakeWordEnabled(e.target.checked)}
                style={{ width: '18px', height: '18px', cursor: 'pointer' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                Speech Synthesis Rate ({ttsSpeed}x)
              </label>
              <input
                type="range"
                min="0.8"
                max="1.5"
                step="0.05"
                value={ttsSpeed}
                onChange={(e) => setTtsSpeed(e.target.value)}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        )}

        {activeTab === 'vision' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                Facial Verification Threshold ({faceThreshold})
              </label>
              <p style={{ margin: '0 0 8px 0', fontSize: '12px', color: '#94a3b8' }}>
                Cosine similarity required to mark an enrolled subject as verified match.
              </p>
              <input
                type="range"
                min="0.50"
                max="0.85"
                step="0.01"
                value={faceThreshold}
                onChange={(e) => setFaceThreshold(e.target.value)}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        )}

        {activeTab === 'security' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600 }}>Audio Alerts on High Severity Incidents</div>
                <div style={{ fontSize: '12px', color: '#94a3b8' }}>Play subtle chime when perimeter or seismic anomalies trigger</div>
              </div>
              <input
                type="checkbox"
                checked={soundAlerts}
                onChange={(e) => setSoundAlerts(e.target.checked)}
                style={{ width: '18px', height: '18px', cursor: 'pointer' }}
              />
            </div>
          </div>
        )}

        {activeTab === 'privacy' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600 }}>Strict Consent Policy Enforcement</div>
                <div style={{ fontSize: '12px', color: '#94a3b8' }}>Mandate signed consent flags before face or screen features engage</div>
              </div>
              <input
                type="checkbox"
                checked={consentEnforced}
                onChange={(e) => setConsentEnforced(e.target.checked)}
                style={{ width: '18px', height: '18px', cursor: 'pointer' }}
              />
            </div>
            <div style={{ background: '#1e293b', padding: '12px', borderRadius: '6px', fontSize: '12px', color: '#94a3b8' }}>
              ✓ Data minimization active. No raw unverified biometric vectors are stored without user-signed consent records.
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

