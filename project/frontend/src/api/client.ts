import type {
  CameraDeviceDto,
  CaptureStateDto,
  ClipDto,
  HealthDto,
  LiveResultDto,
  PipelineResultDto,
  QuickResultDto,
  RegisteredItemDto,
  SummaryDto,
} from '../types/domain';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const USE_MOCK = (import.meta.env.VITE_USE_MOCK ?? 'false').toLowerCase() === 'true';

const mockSummary: SummaryDto = {
  captureStatus: 'Stopped',
  totalClips: 0,
  addedItems: 0,
};

const mockClips: ClipDto[] = [];
const mockCapture: CaptureStateDto = { running: false, cameraIndex: 0 };
const mockRegistered: RegisteredItemDto[] = [];

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return (await res.json()) as T;
}

export const apiClient = {
  capturePreviewUrl(cacheBust?: number): string {
    if (USE_MOCK) return '';
    const q = typeof cacheBust === 'number' ? `?t=${cacheBust}` : '';
    return `${API_BASE}/api/v1/capture/preview${q}`;
  },

  liveFrameUrl(cameraIndex = 0, cacheBust?: number, cameraSource?: string): string {
    if (USE_MOCK) return '';
    const params = new URLSearchParams();
    params.set('cameraIndex', String(cameraIndex));
    if (cameraSource?.trim()) params.set('cameraSource', cameraSource.trim());
    if (typeof cacheBust === 'number') params.set('t', String(cacheBust));
    return `${API_BASE}/api/v1/live/frame?${params.toString()}`;
  },

  clipUrl(fileName?: string): string {
    if (!fileName) return '';
    return `${API_BASE}/api/v1/files/clips/${encodeURIComponent(fileName)}`;
  },

  clipMjpegUrl(fileName?: string, fps = 12): string {
    if (!fileName) return '';
    return `${API_BASE}/api/v1/files/clips-mjpeg/${encodeURIComponent(fileName)}?fps=${fps}`;
  },

  thumbUrl(fileName?: string): string {
    if (!fileName) return '';
    return `${API_BASE}/api/v1/files/thumbs/${encodeURIComponent(fileName)}`;
  },

  registeredImageUrl(fileName?: string): string {
    if (!fileName) return '';
    return `${API_BASE}/api/v1/files/registered/${encodeURIComponent(fileName)}`;
  },

  async health(): Promise<HealthDto> {
    if (USE_MOCK) return { ok: true, message: 'mock backend ok' };
    return http<HealthDto>('/health');
  },

  async summary(): Promise<SummaryDto> {
    if (USE_MOCK) return mockSummary;
    return http<SummaryDto>('/api/v1/dashboard/summary');
  },

  async recentClips(): Promise<ClipDto[]> {
    if (USE_MOCK) return mockClips;
    return http<ClipDto[]>('/api/v1/dashboard/clips/recent');
  },

  async deleteClipById(clipId: string): Promise<{ ok: boolean; clipId: string }> {
    if (USE_MOCK) {
      const idx = mockClips.findIndex((x) => x.clipId === clipId);
      if (idx >= 0) mockClips.splice(idx, 1);
      return { ok: true, clipId };
    }
    return http<{ ok: boolean; clipId: string }>(`/api/v1/files/clips/by-id/${encodeURIComponent(clipId)}`, {
      method: 'DELETE',
    });
  },

  async captureState(): Promise<CaptureStateDto> {
    if (USE_MOCK) return mockCapture;
    return http<CaptureStateDto>('/api/v1/capture/state');
  },

  async captureDevices(maxIndex = 10): Promise<CameraDeviceDto[]> {
    if (USE_MOCK) return [{ index: 0, label: 'Camera 0', width: 640, height: 480 }];
    return http<CameraDeviceDto[]>(`/api/v1/capture/devices?maxIndex=${maxIndex}`);
  },

  async startCapture(cameraIndex: number): Promise<CaptureStateDto> {
    if (USE_MOCK) return { running: true, cameraIndex };
    return http<CaptureStateDto>('/api/v1/capture/start', {
      method: 'POST',
      body: JSON.stringify({ cameraIndex }),
    });
  },

  async stopCapture(): Promise<CaptureStateDto> {
    if (USE_MOCK) return { running: false, cameraIndex: 0 };
    return http<CaptureStateDto>('/api/v1/capture/stop', { method: 'POST' });
  },

  async liveSearch(query: string, cameraIndex = 0): Promise<LiveResultDto> {
    if (USE_MOCK) {
      const score = query.trim().length > 2 ? 0.79 : 0.41;
      return {
        found: score >= 0.5,
        score,
        detail: `mock live response for ${query}`,
      };
    }
    return http<LiveResultDto>('/api/v1/live/search', {
      method: 'POST',
      body: JSON.stringify({ query, cameraIndex }),
    });
  },

  async liveSearchImage(query: string, imageBlob: Blob, fileName = 'frame.jpg'): Promise<LiveResultDto> {
    if (USE_MOCK) {
      const score = query.trim().length > 2 ? 0.76 : 0.38;
      return {
        found: score >= 0.5,
        score,
        detail: `mock live image response for ${query}`,
      };
    }
    const form = new FormData();
    form.set('query', query);
    form.append('image', imageBlob, fileName);
    const res = await fetch(`${API_BASE}/api/v1/live/search-image`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      throw new Error(`API ${res.status}: ${await res.text()}`);
    }
    return (await res.json()) as LiveResultDto;
  },

  async liveSearchUnified(args: {
    query: string;
    imageBlob?: Blob | null;
    fileName?: string;
    phoneSessionId?: string;
    cameraIndex?: number;
    cameraId?: string;
    cameraSource?: string;
  }): Promise<LiveResultDto> {
    if (USE_MOCK) {
      const score = args.query.trim().length > 2 ? 0.81 : 0.42;
      return {
        found: score >= 0.5,
        score,
        detail: `mock live unified response for ${args.query}`,
      };
    }
    const form = new FormData();
    form.set('query', args.query);
    form.set('cameraIndex', String(args.cameraIndex ?? 0));
    if (args.phoneSessionId) form.set('phoneSessionId', args.phoneSessionId);
    if (args.cameraId) form.set('cameraId', args.cameraId);
    if (args.cameraSource) form.set('cameraSource', args.cameraSource);
    if (args.imageBlob) {
      form.append('image', args.imageBlob, args.fileName ?? 'frame.jpg');
    }
    const res = await fetch(`${API_BASE}/api/v1/live/search-unified`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      throw new Error(`API ${res.status}: ${await res.text()}`);
    }
    return (await res.json()) as LiveResultDto;
  },

  async createPhoneSession(): Promise<{ sessionId: string }> {
    if (USE_MOCK) return { sessionId: 'mock-phone-session' };
    return http<{ sessionId: string }>('/api/v1/phone/sessions', { method: 'POST' });
  },

  async phoneSessionExists(sessionId: string): Promise<{ ok: boolean; sessionId: string }> {
    if (USE_MOCK) return { ok: true, sessionId };
    return http<{ ok: boolean; sessionId: string }>(`/api/v1/phone/sessions/${encodeURIComponent(sessionId)}/exists`);
  },

  async phoneNetworkInfo(): Promise<{ hosts: string[] }> {
    if (USE_MOCK) return { hosts: [] };
    return http<{ hosts: string[] }>('/api/v1/phone/network');
  },

  async startPhoneTunnel(targetUrl = window.location.origin): Promise<{ running: boolean; publicUrl: string; detail: string }> {
    if (USE_MOCK) return { running: true, publicUrl: targetUrl, detail: 'mock tunnel' };
    const form = new FormData();
    form.set('targetUrl', targetUrl);
    const res = await fetch(`${API_BASE}/api/v1/phone/tunnel/start`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
    return (await res.json()) as { running: boolean; publicUrl: string; detail: string };
  },

  async phoneTunnelStatus(): Promise<{ running: boolean; publicUrl: string; detail: string }> {
    if (USE_MOCK) return { running: false, publicUrl: '', detail: '' };
    return http<{ running: boolean; publicUrl: string; detail: string }>('/api/v1/phone/tunnel/status');
  },

  async uploadPhoneFrame(sessionId: string, imageBlob: Blob, fileName = 'phone-frame.jpg'): Promise<{ ok: boolean; sessionId: string; ts: string }> {
    if (USE_MOCK) return { ok: true, sessionId, ts: String(Date.now()) };
    const form = new FormData();
    form.append('image', imageBlob, fileName);
    form.set('ts', String(Date.now()));
    const res = await fetch(`${API_BASE}/api/v1/phone/sessions/${encodeURIComponent(sessionId)}/frame`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      throw new Error(`API ${res.status}: ${await res.text()}`);
    }
    return (await res.json()) as { ok: boolean; sessionId: string; ts: string };
  },

  phoneFrameUrl(sessionId: string, cacheBust?: number): string {
    const q = typeof cacheBust === 'number' ? `?t=${cacheBust}` : '';
    return `${API_BASE}/api/v1/phone/sessions/${encodeURIComponent(sessionId)}/frame${q}`;
  },

  async pipelineFind(query: string, cameraIndex = 0, topK = 5): Promise<PipelineResultDto> {
    if (USE_MOCK) {
      const live = await this.liveSearch(query);
      if (live.found) {
        return {
          stage: 'live',
          found: true,
          message: 'Found in Stage 1 Live Search',
          live,
          quick: [],
        };
      }
      const quick = await this.quickSearch(query);
      return {
        stage: 'quick',
        found: quick.length > 0,
        message: 'Stage 1 failed. Stage 2 Quick Search completed.',
        live,
        quick,
      };
    }
    return http<PipelineResultDto>('/api/v1/pipeline/find', {
      method: 'POST',
      body: JSON.stringify({ query, cameraIndex, topK }),
    });
  },

  async quickSearch(query: string): Promise<QuickResultDto[]> {
    if (USE_MOCK) {
      if (!query.trim()) return [];
      return [
        { clipId: 'mock-001', score: 0.82, detail: `Best match for ${query}` },
        { clipId: 'mock-002', score: 0.65, detail: `Second match for ${query}` },
      ];
    }
    return http<QuickResultDto[]>('/api/v1/quick/search', {
      method: 'POST',
      body: JSON.stringify({ query }),
    });
  },

  async listRegistered(): Promise<RegisteredItemDto[]> {
    if (USE_MOCK) return mockRegistered;
    return http<RegisteredItemDto[]>('/api/v1/register/items');
  },

  async addRegistered(name: string, files: File[]): Promise<RegisteredItemDto> {
    if (USE_MOCK) {
      const item = { name };
      mockRegistered.push(item);
      return item;
    }
    const form = new FormData();
    form.set('name', name);
    files.forEach((f) => form.append('images', f));
    const res = await fetch(`${API_BASE}/api/v1/register/items`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      throw new Error(`API ${res.status}: ${await res.text()}`);
    }
    return (await res.json()) as RegisteredItemDto;
  },

  async removeRegistered(name: string): Promise<RegisteredItemDto> {
    if (USE_MOCK) {
      const idx = mockRegistered.findIndex((x) => x.name === name);
      if (idx >= 0) mockRegistered.splice(idx, 1);
      return { name };
    }
    return http<RegisteredItemDto>(`/api/v1/register/items/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    });
  },
};
