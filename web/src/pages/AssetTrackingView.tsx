import React, { useEffect, useState } from 'react';
import { 
  PackageSearch, 
  Car, 
  Laptop, 
  Package, 
  Tag, 
  MapPin, 
  Clock, 
  Plus, 
  Trash2, 
  CheckCircle, 
  AlertCircle,
  Camera as CameraIcon,
  Search,
  Filter
} from 'lucide-react';
import { getAuthToken } from '../services/api';

interface Asset {
  id: string;
  name: string;
  category: string;
  tracking_method: string;
  identifier: string | null;
  status: string;
  last_seen_at: string | null;
  location_label: string;
  camera_id: string | null;
  created_at: string;
}

interface AssetSummary {
  total_assets: number;
  by_category: Record<string, number>;
  by_status: Record<string, number>;
  recent_sightings: Array<{
    id: string;
    name: string;
    category: string;
    location: string;
    status: string;
    last_seen_at: string | null;
  }>;
}

export const AssetTrackingView: React.FC = () => {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [summary, setSummary] = useState<AssetSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Registration Modal State
  const [showAddModal, setShowAddModal] = useState(false);
  const [formName, setFormName] = useState('');
  const [formCategory, setFormCategory] = useState('vehicle');
  const [formMethod, setFormMethod] = useState('visual');
  const [formIdentifier, setFormIdentifier] = useState('');
  const [formLocation, setFormLocation] = useState('Driveway / Garage');

  const fetchAssets = async () => {
    setLoading(true);
    const token = getAuthToken();
    const headers = {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/json',
    };

    try {
      const [assetsRes, summaryRes] = await Promise.all([
        fetch('/api/v1/assets', { headers }),
        fetch('/api/v1/assets/summary', { headers }),
      ]);

      if (assetsRes.ok) {
        const json = await assetsRes.json();
        setAssets(json);
      }
      if (summaryRes.ok) {
        const sJson = await summaryRes.json();
        setSummary(sJson);
      }
    } catch (err) {
      console.error('Failed to fetch assets:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssets();
  }, []);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim()) return;

    const token = getAuthToken();
    try {
      const res = await fetch('/api/v1/assets', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: formName.trim(),
          category: formCategory,
          tracking_method: formMethod,
          identifier: formIdentifier.trim() || undefined,
          location_label: formLocation.trim() || 'Home Area',
        }),
      });

      if (res.ok) {
        setShowAddModal(false);
        setFormName('');
        setFormIdentifier('');
        fetchAssets();
      }
    } catch (err) {
      console.error('Failed to register asset:', err);
    }
  };

  const handleDelete = async (assetId: string) => {
    if (!confirm('Are you sure you want to remove this tracked asset?')) return;
    const token = getAuthToken();
    try {
      const res = await fetch(`/api/v1/assets/${assetId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        fetchAssets();
      }
    } catch (err) {
      console.error('Failed to delete asset:', err);
    }
  };

  const filteredAssets = assets.filter((a) => {
    const matchesCat = selectedCategory === 'all' || a.category === selectedCategory;
    const matchesSearch =
      !searchQuery.trim() ||
      a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (a.identifier && a.identifier.toLowerCase().includes(searchQuery.toLowerCase())) ||
      a.location_label.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCat && matchesSearch;
  });

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'vehicle':
        return <Car size={18} color="#38bdf8" />;
      case 'equipment':
        return <Laptop size={18} color="#a855f7" />;
      case 'goods':
        return <Package size={18} color="#f59e0b" />;
      default:
        return <Tag size={18} color="#10b981" />;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '16px', padding: '20px' }}>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <PackageSearch size={24} color="#6366f1" />
            <h2 style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
              Universal Asset & Object Tracking
            </h2>
          </div>
          <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Register and monitor vehicles, personal belongings, and equipment across all authorized surveillance cameras.
          </p>
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 18px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
            color: '#fff',
            border: 'none',
            fontWeight: 600,
            fontSize: '0.88rem',
            cursor: 'pointer',
            boxShadow: '0 4px 12px rgba(99, 102, 241, 0.3)',
          }}
        >
          <Plus size={16} /> Register New Asset
        </button>
      </div>

      {/* Summary KPI Cards */}
      {summary && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
          <div style={{ background: 'var(--bg-card)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Total Tracked Assets</div>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--text-main)', marginTop: '4px' }}>
              {summary.total_assets}
            </div>
          </div>
          <div style={{ background: 'var(--bg-card)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Vehicles Registered</div>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#38bdf8', marginTop: '4px' }}>
              {summary.by_category.vehicle || 0}
            </div>
          </div>
          <div style={{ background: 'var(--bg-card)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Equipment & Goods</div>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#a855f7', marginTop: '4px' }}>
              {(summary.by_category.equipment || 0) + (summary.by_category.goods || 0)}
            </div>
          </div>
          <div style={{ background: 'var(--bg-card)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Stationary in Monitored Zones</div>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#10b981', marginTop: '4px' }}>
              {summary.by_status.stationary || summary.by_status.active || 0}
            </div>
          </div>
        </div>
      )}

      {/* Search & Category Filter Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: '6px' }}>
          {['all', 'vehicle', 'equipment', 'goods', 'personal_item'].map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              style={{
                padding: '6px 14px',
                borderRadius: '8px',
                background: selectedCategory === cat ? 'rgba(99, 102, 241, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                border: `1px solid ${selectedCategory === cat ? '#6366f1' : 'transparent'}`,
                color: selectedCategory === cat ? '#818cf8' : 'var(--text-muted)',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
                textTransform: 'capitalize',
              }}
            >
              {cat.replace('_', ' ')}
            </button>
          ))}
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '8px',
            padding: '6px 12px',
            width: '260px',
          }}
        >
          <Search size={14} color="#94a3b8" />
          <input
            type="text"
            placeholder="Search assets or license plate..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-main)',
              fontSize: '0.82rem',
              outline: 'none',
              width: '100%',
            }}
          />
        </div>
      </div>

      {/* Asset Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '14px', flex: 1, overflowY: 'auto' }}>
        {filteredAssets.map((asset) => (
          <div
            key={asset.id}
            style={{
              background: 'var(--bg-card)',
              borderRadius: '12px',
              border: '1px solid var(--border-subtle)',
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              gap: '12px',
            }}
          >
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div
                    style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '8px',
                      background: 'rgba(255, 255, 255, 0.05)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {getCategoryIcon(asset.category)}
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)' }}>
                      {asset.name}
                    </h3>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                      {asset.category} • Method: {asset.tracking_method}
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => handleDelete(asset.id)}
                  title="Remove asset"
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    padding: '4px',
                  }}
                >
                  <Trash2 size={16} />
                </button>
              </div>

              {/* Status and Details */}
              <div style={{ marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.82rem' }}>
                {asset.identifier && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-main)' }}>
                    <Tag size={14} color="#94a3b8" />
                    <strong>Plate / Identifier:</strong> {asset.identifier}
                  </div>
                )}
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)' }}>
                  <MapPin size={14} color="#94a3b8" />
                  <span>{asset.location_label || 'Location not tagged'}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)' }}>
                  <Clock size={14} color="#94a3b8" />
                  <span>Last seen: {asset.last_seen_at ? new Date(asset.last_seen_at).toLocaleString() : 'Never'}</span>
                </div>
              </div>
            </div>

            <div
              style={{
                borderTop: '1px solid var(--border-subtle)',
                paddingTop: '10px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <span
                style={{
                  padding: '3px 8px',
                  borderRadius: '4px',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  background: asset.status === 'active' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(99, 102, 241, 0.15)',
                  color: asset.status === 'active' ? '#10b981' : '#818cf8',
                }}
              >
                ● {asset.status}
              </span>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                Protected by Aegis
              </span>
            </div>
          </div>
        ))}

        {filteredAssets.length === 0 && (
          <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
            <PackageSearch size={40} style={{ margin: '0 auto 12px', opacity: 0.4 }} />
            <h3 style={{ color: 'var(--text-main)', margin: '0 0 6px' }}>No Tracked Assets Found</h3>
            <p style={{ fontSize: '0.85rem', margin: 0 }}>
              Register your vehicle, laptop, or inventory to automatically detect and log camera sightings.
            </p>
          </div>
        )}
      </div>

      {/* Register Asset Modal */}
      {showAddModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(6px)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
        >
          <div
            style={{
              background: 'var(--bg-card)',
              borderRadius: '16px',
              border: '1px solid var(--border-subtle)',
              width: '100%',
              maxWidth: '460px',
              padding: '24px',
              boxShadow: '0 20px 40px rgba(0, 0, 0, 0.5)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-main)' }}>
                Register Tracked Asset
              </h3>
              <button
                onClick={() => setShowAddModal(false)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1.1rem' }}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px' }}>
                  Asset Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Tesla Model 3, Work ThinkPad, Tool Box"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: '8px',
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-main)',
                    fontSize: '0.88rem',
                    outline: 'none',
                  }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px' }}>
                    Category
                  </label>
                  <select
                    value={formCategory}
                    onChange={(e) => setFormCategory(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '10px',
                      borderRadius: '8px',
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border-subtle)',
                      color: 'var(--text-main)',
                      fontSize: '0.85rem',
                      outline: 'none',
                    }}
                  >
                    <option value="vehicle">Vehicle (Car/Bike)</option>
                    <option value="equipment">Equipment (Laptop/Tool)</option>
                    <option value="goods">Goods / Package</option>
                    <option value="personal_item">Personal Belonging</option>
                    <option value="pet">Pet</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px' }}>
                    Tracking Method
                  </label>
                  <select
                    value={formMethod}
                    onChange={(e) => setFormMethod(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '10px',
                      borderRadius: '8px',
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border-subtle)',
                      color: 'var(--text-main)',
                      fontSize: '0.85rem',
                      outline: 'none',
                    }}
                  >
                    <option value="visual">Visual Detection</option>
                    <option value="plate">License Plate OCR</option>
                    <option value="barcode">Barcode / QR</option>
                    <option value="manual">Stationary Tag</option>
                  </select>
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px' }}>
                  License Plate / Tag / Serial Number (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. DL-01-AB-1234, SN: 9948271"
                  value={formIdentifier}
                  onChange={(e) => setFormIdentifier(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: '8px',
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-main)',
                    fontSize: '0.88rem',
                    outline: 'none',
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px' }}>
                  Default Home Location
                </label>
                <input
                  type="text"
                  placeholder="e.g. Garage Bay 1, Master Desk, Front Porch"
                  value={formLocation}
                  onChange={(e) => setFormLocation(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: '8px',
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-main)',
                    fontSize: '0.88rem',
                    outline: 'none',
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  style={{
                    padding: '10px 16px',
                    borderRadius: '8px',
                    background: 'transparent',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-muted)',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  style={{
                    padding: '10px 20px',
                    borderRadius: '8px',
                    background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
                    color: '#fff',
                    border: 'none',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Confirm Registration
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

