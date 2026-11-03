import React, { useState } from 'react';
import { api } from '../services/api';

interface AutomationControlModuleProps {
  onBackToCommandCenter?: () => void;
}

export const AutomationControlModule: React.FC<AutomationControlModuleProps> = ({
  onBackToCommandCenter,
}) => {
  const [explicitConsent, setExplicitConsent] = useState(false);
  const [isCapturing, setIsCapturing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<any | null>(null);
  const [userQuery, setUserQuery] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // Approval-gated file operations state
  const [filePath, setFilePath] = useState('');
  const [fileContent, setFileContent] = useState('');
  const [fileOpResult, setFileOpResult] = useState<any | null>(null);
  const [pendingApproval, setPendingApproval] = useState<string | null>(null);

  // Screen capture & diagnosis
  const handleCaptureAndAnalyze = async () => {
    if (!explicitConsent) {
      setErrorMsg('Explicit user consent is mandatory before capturing or analyzing screen data.');
      return;
    }
    setErrorMsg('');
    setIsCapturing(true);

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
        throw new Error('Screen capture API (getDisplayMedia) is not supported in this browser.');
      }

      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: { displaySurface: 'monitor' },
        audio: false,
      });

      const track = stream.getVideoTracks()[0];
      const imageCapture = new (window as any).ImageCapture(track);
      const bitmap = await imageCapture.grabFrame();

      const canvas = document.createElement('canvas');
      canvas.width = bitmap.width;
      canvas.height = bitmap.height;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.drawImage(bitmap, 0, 0);
      }
      const dataUrl = canvas.toDataURL('image/png');

      // Stop stream tracks
      stream.getTracks().forEach((t) => t.stop());

      // Send to backend
      const res = await api.analyzeScreenContent(
        dataUrl,
        userQuery || 'Diagnose visible screen errors and inspect active windows',
        true
      );

      setAnalysisResult(res);
    } catch (err: any) {
      setErrorMsg(err.message || 'Screen capture was cancelled or failed.');
    } finally {
      setIsCapturing(false);
    }
  };

  // Safe file reader (sandboxed inspection)
  const handleReadFile = async () => {
    if (!filePath.trim()) return;
    try {
      const res = await api.readWorkspaceDocument(filePath.trim());
      setFileOpResult(res);
    } catch (err: any) {
      setFileOpResult({ error: err.message || 'Failed to read file' });
    }
  };

  // Propose write operation (requires approval)
  const handleProposeWrite = () => {
    if (!filePath.trim()) return;
    setPendingApproval(`Write ${fileContent.length} bytes to ${filePath}?`);
  };

  const handleConfirmWrite = async () => {
    if (!pendingApproval) return;
    try {
      const res = await api.writeWorkspaceDocument(filePath.trim(), fileContent, true, true);
      setFileOpResult(res);
      setPendingApproval(null);
    } catch (err: any) {
      setFileOpResult({ error: err.message || 'Write operation failed' });
      setPendingApproval(null);
    }
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
            Automation & Computer Control
          </h1>
          <p style={{ margin: '4px 0 0 0', color: '#94a3b8', fontSize: '13px' }}>
            Screen understanding, OCR error diagnosis, approval-gated file management, and autonomous tasks.
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {/* Screen Understanding Card */}
        <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px', padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
            <span style={{ fontSize: '20px' }}>🖥️</span>
            <h2 style={{ fontSize: '16px', fontWeight: 600, margin: 0 }}>Screen Understanding & Diagnosis</h2>
          </div>

          <p style={{ fontSize: '13px', color: '#94a3b8', lineHeight: 1.5, marginBottom: '16px' }}>
            Jarvis can inspect your display to diagnose stack traces, code errors, or UI anomalies.
            Strict privacy controls ensure screen capture only occurs with your explicit consent.
          </p>

          <div
            style={{
              background: explicitConsent ? '#064e3b33' : '#1e293b55',
              border: `1px solid ${explicitConsent ? '#10b981' : '#334155'}`,
              borderRadius: '8px',
              padding: '12px 16px',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
            }}
          >
            <input
              type="checkbox"
              id="consent-check"
              checked={explicitConsent}
              onChange={(e) => setExplicitConsent(e.target.checked)}
              style={{ width: '16px', height: '16px', cursor: 'pointer' }}
            />
            <label htmlFor="consent-check" style={{ fontSize: '13px', cursor: 'pointer', userSelect: 'none' }}>
              <strong>Grant explicit consent</strong> for one-time screen inspection.
            </label>
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>
              What should Jarvis look for? (Optional)
            </label>
            <input
              type="text"
              placeholder="e.g., Explain why my pytest test failed or find the syntax error"
              value={userQuery}
              onChange={(e) => setUserQuery(e.target.value)}
              style={{
                width: '100%',
                background: '#1e293b',
                border: '1px solid #334155',
                color: '#fff',
                padding: '8px 12px',
                borderRadius: '6px',
                fontSize: '13px',
              }}
            />
          </div>

          <button
            onClick={handleCaptureAndAnalyze}
            disabled={!explicitConsent || isCapturing}
            style={{
              background: explicitConsent ? '#2563eb' : '#334155',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              padding: '10px 18px',
              fontSize: '13px',
              fontWeight: 600,
              cursor: explicitConsent && !isCapturing ? 'pointer' : 'not-allowed',
              opacity: explicitConsent ? 1 : 0.6,
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            {isCapturing ? 'Capturing & Analyzing...' : '📸 Capture Screen & Run Diagnosis'}
          </button>

          {errorMsg && (
            <div style={{ marginTop: '14px', background: '#451a1a', border: '1px solid #dc2626', borderRadius: '6px', padding: '10px', color: '#fca5a5', fontSize: '12px' }}>
              ⚠️ {errorMsg}
            </div>
          )}

          {analysisResult && (
            <div style={{ marginTop: '16px', background: '#1e293b', borderRadius: '8px', padding: '14px', border: '1px solid #334155' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ fontSize: '12px', color: '#10b981', fontWeight: 600 }}>Diagnosis Complete</span>
                <span style={{ fontSize: '11px', color: '#64748b' }}>
                  {analysisResult.screen_geometry?.width}x{analysisResult.screen_geometry?.height} ({analysisResult.screen_geometry?.format})
                </span>
              </div>
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: '12px', color: '#e2e8f0', background: '#0f172a', padding: '10px', borderRadius: '6px', maxHeight: '180px', overflowY: 'auto' }}>
                {analysisResult.diagnosis || JSON.stringify(analysisResult, null, 2)}
              </pre>
            </div>
          )}
        </div>

        {/* Approval-Gated File Management & Safe Tools Card */}
        <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px', padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
            <span style={{ fontSize: '20px' }}>🛡️</span>
            <h2 style={{ fontSize: '16px', fontWeight: 600, margin: 0 }}>Approval-Gated Safe Actions</h2>
          </div>

          <p style={{ fontSize: '13px', color: '#94a3b8', lineHeight: 1.5, marginBottom: '16px' }}>
            Jarvis operates strictly within authenticated boundaries. High-impact operations such as writing code or modifying system configuration require human authorization.
          </p>

          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>
              Target File Path (Relative or Absolute)
            </label>
            <input
              type="text"
              placeholder="e.g. backend/app/main.py"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              style={{
                width: '100%',
                background: '#1e293b',
                border: '1px solid #334155',
                color: '#fff',
                padding: '8px 12px',
                borderRadius: '6px',
                fontSize: '13px',
              }}
            />
          </div>

          <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
            <button
              onClick={handleReadFile}
              style={{
                background: '#334155',
                color: '#f8fafc',
                border: 'none',
                borderRadius: '6px',
                padding: '8px 14px',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              📖 Read File
            </button>
            <button
              onClick={handleProposeWrite}
              style={{
                background: '#4338ca',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                padding: '8px 14px',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              ✍️ Propose Write
            </button>
          </div>

          {pendingApproval && (
            <div style={{ background: '#7c2d12', border: '1px solid #f97316', borderRadius: '8px', padding: '12px', marginBottom: '14px' }}>
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#ffedd5', marginBottom: '8px' }}>
                ⚠️ Human Authorization Required
              </div>
              <p style={{ margin: 0, fontSize: '12px', color: '#fed7aa', marginBottom: '10px' }}>
                {pendingApproval}
              </p>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={handleConfirmWrite}
                  style={{
                    background: '#10b981',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '4px',
                    padding: '6px 12px',
                    fontSize: '11px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Approve Execution
                </button>
                <button
                  onClick={() => setPendingApproval(null)}
                  style={{
                    background: '#64748b',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '4px',
                    padding: '6px 12px',
                    fontSize: '11px',
                    cursor: 'pointer',
                  }}
                >
                  Deny
                </button>
              </div>
            </div>
          )}

          {fileOpResult && (
            <div style={{ background: '#1e293b', borderRadius: '8px', padding: '12px', border: '1px solid #334155' }}>
              <div style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '6px' }}>Result:</div>
              <pre style={{ margin: 0, fontSize: '11px', color: '#e2e8f0', background: '#0f172a', padding: '8px', borderRadius: '4px', maxHeight: '160px', overflowY: 'auto' }}>
                {typeof fileOpResult === 'string' ? fileOpResult : JSON.stringify(fileOpResult, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
