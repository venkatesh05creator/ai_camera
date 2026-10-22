export interface User {
  id: string;
  email: string;
  display_name: string;
  status: string;
  role: string;
  mfa_enabled: boolean;
  created_at: string;
  last_login_at?: string;
}

export interface Camera {
  id: string;
  name: string;
  source_type: 'webcam' | 'rtsp' | 'ip_camera' | 'mobile';
  location_label: string;
  status: 'online' | 'offline' | 'paused' | 'error';
  stream_url?: string;
  fps: number;
  resolution: string;
  last_seen_at?: string;
  created_at: string;
}

export interface Person {
  id: string;
  name: string;
  age?: number;
  gender?: string;
  role_relationship: string;
  contact_details?: string;
  notes?: string;
  photo_object_key?: string;
  status: 'enrolled' | 'withdrawn' | 'archived';
  first_seen_at?: string;
  last_seen_at?: string;
  created_at: string;
  consent_active: boolean;
  templates_count: number;
}

export interface DetectionEvent {
  id: string;
  camera_id: string;
  camera_name?: string;
  occurred_at: string;
  event_type: 'person' | 'motion' | 'disconnect' | 'alert';
  track_id?: string;
  person_id?: string;
  person_name?: string;
  confidence: number;
  snapshot_url?: string;
  review_status: 'unreviewed' | 'confirmed' | 'false_positive';
  metadata_json: string;
}

export interface Alert {
  id: string;
  event_id: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'active' | 'acknowledged' | 'resolved';
  title: string;
  description: string;
  created_at: string;
  acknowledged_at?: string;
  resolved_at?: string;
}

export interface ReportSummary {
  total_events: number;
  total_persons_detected: number;
  total_verified_matches: number;
  total_motion_events: number;
  active_cameras_count: number;
  total_enrolled_profiles: number;
  events_by_camera: Record<string, number>;
  events_by_type: Record<string, number>;
  avg_alert_response_seconds: number;
}

export interface AuditLog {
  id: string;
  actor_user_id?: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  ip_address: string;
  outcome: string;
  details_json: string;
  timestamp: string;
}

export interface AIPersonDossier {
  person_id: string;
  name: string;
  role_relationship: string;
  contact_details?: string;
  notes?: string;
  status: string;
  created_at?: string;
  first_seen_at?: string;
  last_seen_at?: string;
  has_active_consent: boolean;
  templates_count: number;
  surveillance_telemetry: {
    total_sightings: number;
    estimated_dwell_minutes: number;
    cameras_distribution: Record<string, number>;
    recent_sightings: Array<{
      event_id: string;
      camera_name: string;
      timestamp: string;
      confidence: number;
      review_status: string;
    }>;
  };
  security_assessment: {
    risk_score: number;
    risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
    risk_factors: string[];
    recommended_action: string;
  };
  online_intelligence: {
    verified_digital_identity: boolean;
    primary_organization: string;
    professional_title: string;
    clearance_tier: string;
    public_records_check: string;
    verified_channels: Array<{ type: string; value: string; verified: boolean }>;
    online_summary: string;
  };
  ai_executive_summary: string;
}

export interface AITrackAnalysis {
  track_id: string;
  camera_name: string;
  behavior_classification: string;
  estimated_dwell_seconds: number;
  sighting_count: number;
  privacy_compliance: {
    is_anonymous: boolean;
    anonymization_status: string;
    eligible_for_enrollment: boolean;
  };
  recommendations: string[];
  candidate_profiles_for_manual_link: Array<{ id: string; name: string; role: string }>;
}

export interface AICopilotResponse {
  query: string;
  intent: string;
  answer: string;
  data: any;
  suggested_actions: string[];
}
