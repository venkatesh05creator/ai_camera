import { Alert, AuditLog, Camera, DetectionEvent, Person, ReportSummary, User } from '../types';

const API_BASE = '/api/v1';

let authToken: string | null = localStorage.getItem('access_token');

export function setAuthToken(token: string | null) {
  authToken = token;
  if (token) {
    localStorage.setItem('access_token', token);
  } else {
    localStorage.removeItem('access_token');
  }
}

export function getAuthToken(): string | null {
  return authToken || localStorage.getItem('access_token');
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const token = getAuthToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((options.headers as Record<string, string>) || {}),
  };

  try {
    const res = await fetch(url, { ...options, headers });
    if (res.status === 401) {
      if (!endpoint.includes('/auth/login') && !endpoint.includes('/auth/register')) {
        setAuthToken(null);
        window.dispatchEvent(new CustomEvent('auth:unauthorized'));
      }
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Authentication required');
    }
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Request failed with status ${res.status}`);
    }
    if (res.status === 204 || res.headers.get('content-length') === '0') {
      return {} as T;
    }
    const text = await res.text();
    return text ? (JSON.parse(text) as T) : ({} as T);
  } catch (err: any) {
    console.warn(`API Error [${endpoint}]:`, err.message);
    throw err;
  }
}

export const api = {
  // Auth
  login: async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Invalid email or password');
    }
    const data = await res.json();
    setAuthToken(data.access_token);
    return data;
  },
  register: async (email: string, password: string, displayName?: string) => {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, display_name: displayName }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Registration failed');
    }
    return await res.json();
  },
  logout: () => {
    setAuthToken(null);
    window.dispatchEvent(new CustomEvent('auth:logout'));
  },
  ensureAuthenticated: async () => {
    const token = getAuthToken();
    if (!token) {
      throw new Error('Not authenticated');
    }
    return await api.getMe();
  },
  getMe: () => request<User>('/auth/me'),

  // Cameras
  getCameras: () => request<Camera[]>('/cameras'),
  registerCamera: (data: Partial<Camera>) =>
    request<Camera>('/cameras', { method: 'POST', body: JSON.stringify(data) }),
  updateCamera: (id: string, data: Partial<Camera>) =>
    request<Camera>(`/cameras/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteCamera: (id: string) => request<void>(`/cameras/${id}`, { method: 'DELETE' }),
  captureSnapshot: (id: string) =>
    request<{ snapshot_url: string }>(`/cameras/${id}/snapshot`, { method: 'POST' }),

  // People & Consent
  getPeople: (query?: string) =>
    request<Person[]>(`/people${query ? `?q=${encodeURIComponent(query)}` : ''}`),
  createPerson: (data: Partial<Person> & { photo_base64?: string }) =>
    request<Person>('/people', { method: 'POST', body: JSON.stringify(data) }),
  updatePerson: (id: string, data: Partial<Person>) =>
    request<Person>(`/people/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deletePerson: (id: string) => request<void>(`/people/${id}`, { method: 'DELETE' }),
  grantConsent: (personId: string, consentScope = 'face_verification') =>
    request(`/people/${personId}/consent`, {
      method: 'POST',
      body: JSON.stringify({ confirm_explicit_consent: true, consent_scope: consentScope, notice_version: '1.0' }),
    }),
  withdrawConsent: (personId: string) =>
    request<{ status: string; detail: string }>(`/people/${personId}/withdraw`, { method: 'POST' }),
  enrollFaceImage: (personId: string, imageBase64: string) =>
    request<{ status: string; template_id: string; embedding_dim: number }>(`/people/${personId}/enroll`, {
      method: 'POST',
      body: JSON.stringify({ image_base64: imageBase64 }),
    }),

  // Events & Alerts
  getEvents: (params?: { camera_id?: string; event_type?: string; limit?: number }) => {
    const sp = new URLSearchParams();
    if (params?.camera_id) sp.set('camera_id', params.camera_id);
    if (params?.event_type) sp.set('event_type', params.event_type);
    if (params?.limit) sp.set('limit', String(params.limit));
    return request<DetectionEvent[]>(`/events?${sp.toString()}`);
  },
  reviewEvent: (id: string, reviewStatus: 'confirmed' | 'false_positive') =>
    request<{ status: string }>(`/events/${id}/review`, {
      method: 'PUT',
      body: JSON.stringify({ review_status: reviewStatus }),
    }),

  getAlerts: () => request<Alert[]>('/alerts'),
  acknowledgeAlert: (id: string) =>
    request<Alert>(`/alerts/${id}/acknowledge`, { method: 'PUT' }),
  resolveAlert: (id: string) =>
    request<Alert>(`/alerts/${id}/resolve`, { method: 'PUT' }),

  // Reports & Analytics
  getReportSummary: () => request<ReportSummary>('/reports/summary'),
  getAuditLogs: () => request<AuditLog[]>('/audit-logs'),

  // AI Intelligence & Copilot
  getPersonDossier: (personId: string, includeOnline = true) =>
    request<import('../types').AIPersonDossier>(`/ai/person/${personId}/dossier?include_online=${includeOnline}`),

  triggerOnlineLookup: (personId: string) =>
    request<{ status: string; message: string; online_intelligence: any; security_assessment: any }>(
      `/ai/person/${personId}/online-lookup`,
      { method: 'POST' }
    ),

  getTrackAnalysis: (trackId: string, cameraName = 'Live Camera') =>
    request<import('../types').AITrackAnalysis>(
      `/ai/track/${trackId}/analysis?camera_name=${encodeURIComponent(cameraName)}`
    ),

  askCopilot: (query: string) =>
    request<import('../types').AICopilotResponse>('/ai/copilot', {
      method: 'POST',
      body: JSON.stringify({ query }),
    }),

  quickEnrollFromLiveFeed: (data: {
    name: string;
    role_relationship?: string;
    contact_details?: string;
    notes?: string;
    camera_id: string;
    confirm_explicit_consent: boolean;
  }) =>
    request<{ status: string; message: string; person_id: string; name: string }>(
      '/ai/quick-enroll-from-feed',
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    ),

  getLearningStatus: () =>
    request<{
      learning_active: boolean;
      samples_learned: number;
      current_person_id: string | null;
      current_person_name: string;
      last_adapted_seconds_ago: number | null;
      angles_adapted: string[];
      lighting_profiles: string[];
      model_confidence_score: number;
      status_message: string;
      scene_insights: any;
    }>('/ai/learning-status'),

  getSceneAnalysis: (cameraId?: string) =>
    request<{
      camera_online: boolean;
      fps: number;
      people_count: number;
      verified_identities: string[];
      tracks: Array<{ track_id: string; verified_name?: string; dwell_seconds: number }>;
      posture: string;
      head_orientation?: string;
      lighting_condition: string;
      attention_score: number;
      samples_learned: number;
      model_confidence: number;
      background_color?: string;
      background_scene?: string;
    }>(`/ai/scene-analysis${cameraId ? `?camera_id=${cameraId}` : ''}`),

  interactCameraAI: (
    query: string,
    cameraId?: string,
    voiceEnabled = false,
    conversationHistory?: Array<{ role: string; content: string }>,
    imageBase64?: string,
    conversationId?: string
  ) =>
    request<{
      status: string;
      conversation_id: string;
      query: string;
      answer: string;
      speech_text: string;
      action?: string;
      action_payload?: any;
      telemetry: {
        fps: number;
        people_count: number;
        verified_identities: string[];
        samples_learned: number;
        posture: string;
        lighting: string;
      };
    }>('/ai/camera-interact', {
      method: 'POST',
      body: JSON.stringify({
        query,
        camera_id: cameraId,
        voice_enabled: voiceEnabled,
        conversation_history: conversationHistory,
        image_base64: imageBase64,
        frame_timestamp: imageBase64 ? Date.now() / 1000 : undefined,
        conversation_id: conversationId,
      }),
    }),

  listConversations: () =>
    request<Array<{
      id: string;
      title?: string;
      summary?: string;
      is_active: boolean;
      created_at: string;
      updated_at: string;
      message_count: number;
    }>>('/ai/conversations'),

  createConversation: (title?: string) =>
    request<{
      id: string;
      title?: string;
      summary?: string;
      is_active: boolean;
      created_at: string;
      updated_at: string;
      message_count: number;
    }>('/ai/conversations', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),

  getConversationMessages: (conversationId: string) =>
    request<Array<{
      id: string;
      conversation_id: string;
      role: string;
      content: string;
      speech_text?: string;
      action_executed?: string;
      created_at: string;
    }>>(`/ai/conversations/${conversationId}/messages`),

  deleteConversation: (conversationId: string) =>
    request<{ status: string; message: string }>(`/ai/conversations/${conversationId}`, {
      method: 'DELETE',
    }),

  importConversation: (conversationId: string, messages: Array<{ role: string; content: string; speech_text?: string }>, title?: string) =>
    request<{ status: string; imported_count: number; conversation_id: string }>(`/ai/conversations/${conversationId}/import`, {
      method: 'POST',
      body: JSON.stringify({ messages, title }),
    }),

  getCamerasHealth: () =>
    request<Array<{
      camera_id: string;
      name: string;
      source_type: string;
      status: string;
      fps: number;
      resolution: string;
      is_stale: boolean;
      last_frame_timestamp: number;
    }>>('/cameras/health'),

  extractOCR: (cameraId?: string, imageBase64?: string) =>
    request<{
      camera_id: string;
      timestamp: number;
      full_text: string;
      sanitized_data_payload: string;
      line_count: number;
      mean_confidence: number;
      has_uncertain_sections: boolean;
      detected_signs: string[];
      regions: Array<{ text: string; confidence: number; bbox: [number, number, number, number]; is_uncertain: boolean }>;
    }>('/ai/ocr', {
      method: 'POST',
      body: JSON.stringify({ camera_id: cameraId, image_base64: imageBase64 }),
    }),

  detectObjects: (cameraId?: string, imageBase64?: string) =>
    request<{
      camera_id: string;
      timestamp: number;
      total_count: number;
      counts: Record<string, number>;
      objects: Array<{ label: string; confidence: number; certainty: string; bbox: [number, number, number, number] }>;
    }>('/ai/detect-objects', {
      method: 'POST',
      body: JSON.stringify({ camera_id: cameraId, image_base64: imageBase64 }),
    }),

  searchHistoricalEvents: (query: string, cameraId?: string) =>
    request<{
      query: string;
      total_results: number;
      summary: string;
      is_historical: boolean;
      events: Array<any>;
    }>(`/events/historical-search?q=${encodeURIComponent(query)}${cameraId ? `&camera_id=${cameraId}` : ''}`),
};


