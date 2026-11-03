import React, { useState } from 'react';
import { 
  MapPin, 
  Plus, 
  Search, 
  Trash2, 
  Globe, 
  Navigation, 
  ShieldCheck 
} from 'lucide-react';

interface LocationRecord {
  id: string;
  label: string;
  country: string;
  state: string;
  district?: string;
  city: string;
  pin_code?: string;
  latitude: number;
  longitude: number;
  radius_km: number;
}

interface LocationZonesModuleProps {
  markers: any[];
  onBackToCommandCenter?: () => void;
}

export const LocationZonesModule: React.FC<LocationZonesModuleProps> = ({ markers, onBackToCommandCenter }) => {
  const [selectedRadius, setSelectedRadius] = useState<number>(5);
  const [locations, setLocations] = useState<LocationRecord[]>([
    {
      id: 'loc-1',
      label: 'Primary Workstation Facility',
      country: 'India',
      state: 'Karnataka',
      district: 'Bengaluru Urban',
      city: 'Bengaluru',
      pin_code: '560001',
      latitude: 12.9716,
      longitude: 77.5946,
      radius_km: 5.0,
    },
    {
      id: 'loc-2',
      label: 'North Sector Monitored Gate',
      country: 'India',
      state: 'Delhi NCR',
      district: 'New Delhi',
      city: 'New Delhi',
      pin_code: '110001',
      latitude: 28.6139,
      longitude: 77.2090,
      radius_km: 2.0,
    }
  ]);

  const [newLabel, setNewLabel] = useState('');
  const [newCity, setNewCity] = useState('');
  const [newState, setNewState] = useState('');
  const [newCountry, setNewCountry] = useState('India');
  const [newLat, setNewLat] = useState('12.9716');
  const [newLng, setNewLng] = useState('77.5946');

  const handleAddLocation = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLabel.trim()) return;
    const loc: LocationRecord = {
      id: `loc-${Date.now()}`,
      label: newLabel.trim(),
      country: newCountry.trim(),
      state: newState.trim(),
      city: newCity.trim(),
      latitude: parseFloat(newLat) || 12.9716,
      longitude: parseFloat(newLng) || 77.5946,
      radius_km: selectedRadius,
    };
    setLocations([...locations, loc]);
    setNewLabel('');
    setNewCity('');
    setNewState('');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 160px)', background: '#070f26', borderRadius: 14, border: '1px solid rgba(0, 210, 255, 0.25)', overflow: 'hidden' }}>
      {/* Top Header */}
      <div style={{ padding: '12px 18px', background: 'rgba(10, 20, 50, 0.95)', borderBottom: '1px solid rgba(0, 210, 255, 0.2)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 34, height: 34, borderRadius: 8, background: 'linear-gradient(135deg, #a855f7 0%, #6366f1 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <MapPin size={18} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: '0.96rem', fontWeight: 700, color: '#ffffff' }}>Location & Geofenced Security Zones</span>
              <span style={{ fontSize: '0.66rem', padding: '2px 6px', borderRadius: 4, background: 'rgba(168, 85, 247, 0.2)', color: '#c084fc', fontWeight: 600 }}>
                {locations.length} Zones Active
              </span>
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
              India & International location formats • Geofence distance rings (1km, 5km, 10km, 25km) • Camera coverage radii
            </div>
          </div>
        </div>

        {/* Distance Filter Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(7, 14, 35, 0.8)', padding: 3, borderRadius: 6, border: '1px solid rgba(0, 210, 255, 0.2)' }}>
          <span style={{ fontSize: '0.68rem', color: '#94a3b8', paddingLeft: 6 }}>Coverage Radius:</span>
          {[1, 5, 10, 25].map((km) => (
            <button
              key={km}
              onClick={() => setSelectedRadius(km)}
              style={{
                padding: '4px 8px',
                borderRadius: 4,
                fontSize: '0.7rem',
                fontWeight: selectedRadius === km ? 700 : 500,
                background: selectedRadius === km ? 'rgba(0, 210, 255, 0.25)' : 'transparent',
                border: 'none',
                color: selectedRadius === km ? '#00d2ff' : '#94a3b8',
                cursor: 'pointer'
              }}
            >
              {km} km
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 18, display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Add Location Form */}
        <div style={{ background: 'rgba(11, 22, 53, 0.75)', border: '1px solid rgba(0, 210, 255, 0.25)', borderRadius: 12, padding: 16 }}>
          <h3 style={{ margin: '0 0 10px 0', fontSize: '0.88rem', fontWeight: 700, color: '#00d2ff', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Plus size={15} /> Define Monitored Security Zone / Facility
          </h3>
          <form onSubmit={handleAddLocation} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr)) auto', gap: 10, alignItems: 'end' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.68rem', color: '#94a3b8', marginBottom: 4 }}>Site / Zone Label</label>
              <input
                required
                type="text"
                placeholder="e.g. Headquarters Campus"
                value={newLabel}
                onChange={(e) => setNewLabel(e.target.value)}
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, background: 'rgba(7, 14, 35, 0.8)', border: '1px solid rgba(0, 210, 255, 0.2)', color: '#fff', fontSize: '0.78rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.68rem', color: '#94a3b8', marginBottom: 4 }}>City / District</label>
              <input
                type="text"
                placeholder="e.g. Bengaluru, Karnataka"
                value={newCity}
                onChange={(e) => setNewCity(e.target.value)}
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, background: 'rgba(7, 14, 35, 0.8)', border: '1px solid rgba(0, 210, 255, 0.2)', color: '#fff', fontSize: '0.78rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.68rem', color: '#94a3b8', marginBottom: 4 }}>Latitude</label>
              <input
                type="text"
                placeholder="12.9716"
                value={newLat}
                onChange={(e) => setNewLat(e.target.value)}
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, background: 'rgba(7, 14, 35, 0.8)', border: '1px solid rgba(0, 210, 255, 0.2)', color: '#fff', fontSize: '0.78rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.68rem', color: '#94a3b8', marginBottom: 4 }}>Longitude</label>
              <input
                type="text"
                placeholder="77.5946"
                value={newLng}
                onChange={(e) => setNewLng(e.target.value)}
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, background: 'rgba(7, 14, 35, 0.8)', border: '1px solid rgba(0, 210, 255, 0.2)', color: '#fff', fontSize: '0.78rem' }}
              />
            </div>

            <button
              type="submit"
              style={{
                height: 33,
                background: 'linear-gradient(135deg, #00d2ff 0%, #2563eb 100%)',
                border: 'none',
                borderRadius: 6,
                padding: '0 16px',
                color: '#fff',
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              Add Zone
            </button>
          </form>
        </div>

        {/* Saved Zones Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
          {locations.map((loc) => (
            <div key={loc.id} style={{ background: 'rgba(11, 22, 53, 0.85)', border: '1px solid rgba(0, 210, 255, 0.2)', borderRadius: 10, padding: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <span style={{ fontSize: '0.86rem', fontWeight: 700, color: '#fff' }}>{loc.label}</span>
                <span style={{ fontSize: '0.64rem', padding: '1px 6px', borderRadius: 4, background: 'rgba(168, 85, 247, 0.2)', color: '#c084fc', fontWeight: 600 }}>
                  {loc.radius_km} km Geofence
                </span>
              </div>

              <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginBottom: 6 }}>
                {loc.city ? `${loc.city}, ` : ''}{loc.state ? `${loc.state}, ` : ''}{loc.country} {loc.pin_code ? `(${loc.pin_code})` : ''}
              </div>

              <div style={{ background: 'rgba(7, 14, 35, 0.6)', padding: '6px 10px', borderRadius: 6, fontSize: '0.68rem', color: '#cbd5e1', display: 'flex', justifyContent: 'space-between' }}>
                <span>GPS: <strong>{loc.latitude.toFixed(4)}, {loc.longitude.toFixed(4)}</strong></span>
                <span style={{ color: '#34d399' }}>● Active Boundary</span>
              </div>

              <div style={{ marginTop: 10, display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  onClick={() => setLocations(locations.filter((l) => l.id !== loc.id))}
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
