import React, { useState } from 'react';
import { 
  Crosshair, 
  Tag, 
  Search, 
  Plus, 
  Trash2, 
  Package, 
  AlertTriangle, 
  CheckCircle2, 
  Activity 
} from 'lucide-react';
import { Asset } from '../types';

interface ObjectTrackingModuleProps {
  assets?: Asset[];
  onAddCustomLabel?: (name: string, category: string, identifier?: string) => Promise<void>;
  onDeleteAsset?: (id: string) => Promise<void>;
  onBackToCommandCenter?: () => void;
}

export const ObjectTrackingModule: React.FC<ObjectTrackingModuleProps> = ({
  assets = [],
  onAddCustomLabel = async () => {},
  onDeleteAsset = async () => {},
  onBackToCommandCenter,
}) => {
  const [manualLabel, setManualLabel] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('luggage');
  const [customIdentifier, setCustomIdentifier] = useState('');
  const [searchFilter, setSearchFilter] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleSaveLabel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualLabel.trim()) return;
    setIsSubmitting(true);
    setFeedback(null);
    try {
      await onAddCustomLabel(manualLabel.trim(), selectedCategory, customIdentifier.trim() || undefined);
      setFeedback(`Custom label '${manualLabel}' approved and saved to persistent object registry.`);
      setManualLabel('');
      setCustomIdentifier('');
    } catch (err: any) {
      setFeedback(`Failed to save object label: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredAssets = assets.filter((a) =>
    a.name.toLowerCase().includes(searchFilter.toLowerCase()) ||
    a.category.toLowerCase().includes(searchFilter.toLowerCase()) ||
    (a.identifier && a.identifier.toLowerCase().includes(searchFilter.toLowerCase()))
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 160px)', background: '#070f26', borderRadius: 14, border: '1px solid rgba(0, 210, 255, 0.25)', overflow: 'hidden' }}>
      {/* Top Header */}
      <div style={{ padding: '12px 18px', background: 'rgba(10, 20, 50, 0.95)', borderBottom: '1px solid rgba(0, 210, 255, 0.2)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 34, height: 34, borderRadius: 8, background: 'linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Crosshair size={18} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: '0.96rem', fontWeight: 700, color: '#ffffff' }}>Multi-Object Tracking & Custom Labeling</span>
              <span style={{ fontSize: '0.66rem', padding: '2px 6px', borderRadius: 4, background: 'rgba(0, 210, 255, 0.15)', color: '#00d2ff', fontWeight: 600 }}>
                {assets.length} Tracked Objects
              </span>
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
              Custom manual labels ("This is my luggage") • Temporary tracking IDs • Natural language object search
            </div>
          </div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 18, display: 'flex', flexDirection: 'column', gap: 16 }}>
        {feedback && (
          <div style={{ padding: '8px 14px', borderRadius: 6, background: feedback.includes('Failed') ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)', border: feedback.includes('Failed') ? '1px solid #ef4444' : '1px solid #10b981', color: feedback.includes('Failed') ? '#fca5a5' : '#86efac', fontSize: '0.78rem' }}>
            {feedback}
          </div>
        )}

        {/* Manual Labeling Form */}
        <div style={{ background: 'rgba(11, 22, 53, 0.75)', border: '1px solid rgba(0, 210, 255, 0.25)', borderRadius: 12, padding: 16 }}>
          <h3 style={{ margin: '0 0 10px 0', fontSize: '0.88rem', fontWeight: 700, color: '#00d2ff', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Tag size={15} /> Label & Remember Custom Object (e.g., "This is my luggage. Remember it.")
          </h3>
          <form onSubmit={handleSaveLabel} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr)) auto', gap: 12, alignItems: 'end' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.7rem', color: '#94a3b8', marginBottom: 4 }}>Object Label / Description</label>
              <input
                required
                type="text"
                placeholder='e.g. My Black Samsonite Luggage'
                value={manualLabel}
                onChange={(e) => setManualLabel(e.target.value)}
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, background: 'rgba(7, 14, 35, 0.8)', border: '1px solid rgba(0, 210, 255, 0.2)', color: '#fff', fontSize: '0.78rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.7rem', color: '#94a3b8', marginBottom: 4 }}>Object Category</label>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, background: 'rgba(7, 14, 35, 0.8)', border: '1px solid rgba(0, 210, 255, 0.2)', color: '#fff', fontSize: '0.78rem' }}
              >
                <option value="luggage">Luggage / Suitcase</option>
                <option value="bag">Backpack / Bag</option>
                <option value="package">Package / Delivery Box</option>
                <option value="vehicle">Personal Vehicle</option>
                <option value="bicycle">Bicycle / Motorcycle</option>
                <option value="pet">Pet / Animal</option>
                <option value="equipment">Tools & Hardware</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.7rem', color: '#94a3b8', marginBottom: 4 }}>Visual Tag / Distinguishing Marks</label>
              <input
                type="text"
                placeholder="e.g. Red ribbon on handle"
                value={customIdentifier}
                onChange={(e) => setCustomIdentifier(e.target.value)}
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, background: 'rgba(7, 14, 35, 0.8)', border: '1px solid rgba(0, 210, 255, 0.2)', color: '#fff', fontSize: '0.78rem' }}
              />
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              style={{
                height: 33,
                background: 'linear-gradient(135deg, #00d2ff 0%, #2563eb 100%)',
                border: 'none',
                borderRadius: 6,
                padding: '0 16px',
                color: '#fff',
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: isSubmitting ? 'not-allowed' : 'pointer'
              }}
            >
              {isSubmitting ? 'Saving...' : 'Save Approved Label'}
            </button>
          </form>
        </div>

        {/* Search Bar */}
        <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(11, 22, 53, 0.8)', border: '1px solid rgba(0, 210, 255, 0.25)', borderRadius: 8, padding: '6px 12px', gap: 8 }}>
          <Search size={14} color="#00d2ff" />
          <input
            type="text"
            placeholder="Search tracked objects (e.g. luggage, delivery, vehicle)..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            style={{ flex: 1, background: 'transparent', border: 'none', color: '#fff', fontSize: '0.78rem', outline: 'none' }}
          />
        </div>

        {/* Tracked Objects Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 12 }}>
          {filteredAssets.map((asset) => (
            <div key={asset.id} style={{ background: 'rgba(11, 22, 53, 0.85)', border: '1px solid rgba(0, 210, 255, 0.2)', borderRadius: 10, padding: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <span style={{ fontSize: '0.86rem', fontWeight: 700, color: '#fff' }}>{asset.name}</span>
                <span style={{ fontSize: '0.64rem', padding: '1px 6px', borderRadius: 4, background: 'rgba(0, 210, 255, 0.15)', color: '#00d2ff', textTransform: 'uppercase' }}>
                  {asset.category}
                </span>
              </div>

              <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginBottom: 8 }}>
                Location: <strong>{asset.location_label || 'Workstation Bay'}</strong>
              </div>

              {asset.identifier && (
                <div style={{ fontSize: '0.68rem', color: '#cbd5e1', marginBottom: 8, background: 'rgba(7, 14, 35, 0.6)', padding: '4px 8px', borderRadius: 4 }}>
                  Tag / Identifier: <strong>{asset.identifier}</strong>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10, borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 8 }}>
                <span style={{ fontSize: '0.66rem', color: '#34d399', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#10b981' }} />
                  Track Active
                </span>
                <button
                  onClick={() => onDeleteAsset(asset.id)}
                  style={{ background: 'transparent', border: 'none', color: '#f87171', cursor: 'pointer', padding: 2 }}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
