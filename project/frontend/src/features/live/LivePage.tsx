import { useEffect, useMemo, useRef, useState } from 'react';
import { apiClient } from '../../api/client';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import type { LiveResultDto } from '../../types/domain';

const LIVE_QUERY_STORAGE_KEY = 'mf.live.query';
const LIVE_CAMERA_STORAGE_KEY = 'mf.live.cameraIndex';

function confidenceMeta(score: number): { label: string; tone: 'high' | 'medium' | 'low' } {
  if (score >= 0.8) return { label: 'High', tone: 'high' };
  if (score >= 0.55) return { label: 'Medium', tone: 'medium' };
  return { label: 'Low', tone: 'low' };
}

export function LivePage() {
  const [query, setQuery] = useState(() => {
    try {
      return window.localStorage.getItem(LIVE_QUERY_STORAGE_KEY) ?? '';
    } catch {
      return '';
    }
  });
  const [result, setResult] = useState<LiveResultDto | null>(null);
  const [cameraIndex, setCameraIndex] = useState(() => {
    try {
      return window.localStorage.getItem(LIVE_CAMERA_STORAGE_KEY) ?? '0';
    } catch {
      return '0';
    }
  });
  const [registeredItems, setRegisteredItems] = useState<string[]>([]);
  const [sourceMode, setSourceMode] = useState<'desktop' | 'mobile'>('desktop');
  const [tracking, setTracking] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewTick, setPreviewTick] = useState(Date.now());
  const [previewError, setPreviewError] = useState(false);
  const [liveFrameSrc, setLiveFrameSrc] = useState('');
  const [mobileReady, setMobileReady] = useState(false);
  const mobileVideoRef = useRef<HTMLVideoElement | null>(null);
  const mobileStreamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    const t = window.setInterval(() => {
      if (sourceMode === 'desktop') setPreviewTick(Date.now());
    }, 850);
    return () => window.clearInterval(t);
  }, [sourceMode]);

  useEffect(() => {
    let mounted = true;
    async function loadRegistered() {
      try {
        const items = await apiClient.listRegistered();
        if (!mounted) return;
        setRegisteredItems(items.map((x) => x.name));
      } catch {
        if (!mounted) return;
        setRegisteredItems([]);
      }
    }
    loadRegistered();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    try {
      if (query.trim()) {
        window.localStorage.setItem(LIVE_QUERY_STORAGE_KEY, query);
      } else {
        window.localStorage.removeItem(LIVE_QUERY_STORAGE_KEY);
      }
    } catch {
      // ignore storage errors
    }
  }, [query]);

  useEffect(() => {
    try {
      window.localStorage.setItem(LIVE_CAMERA_STORAGE_KEY, cameraIndex || '0');
    } catch {
      // ignore storage errors
    }
  }, [cameraIndex]);

  function resetLiveControls() {
    setQuery('');
    setCameraIndex('0');
    setResult(null);
    try {
      window.localStorage.removeItem(LIVE_QUERY_STORAGE_KEY);
      window.localStorage.removeItem(LIVE_CAMERA_STORAGE_KEY);
    } catch {
      // ignore storage errors
    }
  }

  const cameraIndexNum = useMemo(() => Number.parseInt(cameraIndex, 10) || 0, [cameraIndex]);
  const matchedRegistered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return registeredItems.slice(0, 8);
    return registeredItems
      .filter((name) => name.toLowerCase().includes(q))
      .slice(0, 8);
  }, [query, registeredItems]);
  const exactRegistered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return null;
    return registeredItems.find((name) => name.toLowerCase() === q) ?? null;
  }, [query, registeredItems]);
  const liveFrameUrl = useMemo(
    () => apiClient.liveFrameUrl(cameraIndexNum, previewTick),
    [cameraIndexNum, previewTick],
  );

  useEffect(() => {
    if (sourceMode !== 'desktop') return;
    if (!liveFrameUrl) return;
    let cancelled = false;
    const probe = new Image();
    probe.onload = () => {
      if (cancelled) return;
      setLiveFrameSrc(liveFrameUrl);
      setPreviewError(false);
    };
    probe.onerror = () => {
      if (cancelled) return;
      setPreviewError(true);
    };
    probe.src = liveFrameUrl;
    return () => {
      cancelled = true;
    };
  }, [liveFrameUrl, sourceMode]);

  function stopMobileCamera() {
    if (mobileVideoRef.current) {
      mobileVideoRef.current.srcObject = null;
    }
    if (mobileStreamRef.current) {
      mobileStreamRef.current.getTracks().forEach((t) => t.stop());
      mobileStreamRef.current = null;
    }
    setMobileReady(false);
  }

  async function ensureMobileCamera() {
    if (mobileStreamRef.current && mobileReady) return;
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' } },
      audio: false,
    });
    mobileStreamRef.current = stream;
    if (mobileVideoRef.current) {
      mobileVideoRef.current.srcObject = stream;
      await mobileVideoRef.current.play();
    }
    setMobileReady(true);
  }

  async function captureMobileFrameBlob(): Promise<Blob | null> {
    const video = mobileVideoRef.current;
    if (!video || video.videoWidth <= 0 || video.videoHeight <= 0) return null;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return new Promise<Blob | null>((resolve) => {
      canvas.toBlob((b) => resolve(b), 'image/jpeg', 0.88);
    });
  }

  async function onRunSearch() {
    setLoading(true);
    setError(null);
    try {
      let res: LiveResultDto;
      if (sourceMode === 'mobile') {
        await ensureMobileCamera();
        const blob = await captureMobileFrameBlob();
        if (!blob) throw new Error('모바일 카메라 프레임 캡처 실패');
        res = await apiClient.liveSearchImage(query, blob, 'iphone-frame.jpg');
      } else {
        res = await apiClient.liveSearch(query, cameraIndexNum);
        setPreviewTick(Date.now());
      }
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!tracking) return;
    if (!query.trim()) return;
    let busy = false;
    const timer = window.setInterval(async () => {
      if (busy) return;
      busy = true;
      try {
        if (sourceMode === 'mobile') {
          await ensureMobileCamera();
          const blob = await captureMobileFrameBlob();
          if (!blob) {
            busy = false;
            return;
          }
          const res = await apiClient.liveSearchImage(query, blob, 'iphone-frame.jpg');
          setResult(res);
        } else {
          const res = await apiClient.liveSearch(query, cameraIndexNum);
          setResult(res);
          setPreviewTick(Date.now());
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error');
      } finally {
        busy = false;
      }
    }, 650);
    return () => window.clearInterval(timer);
  }, [tracking, query, sourceMode, cameraIndexNum]);

  useEffect(() => {
    return () => {
      stopMobileCamera();
    };
  }, []);

  async function onStartTracking() {
    setError(null);
    if (!query.trim()) {
      setError('검색어를 먼저 입력해 주세요.');
      return;
    }
    if (sourceMode === 'mobile') {
      try {
        await ensureMobileCamera();
      } catch (e) {
        setError(e instanceof Error ? e.message : '모바일 카메라 시작 실패');
        return;
      }
    }
    setTracking(true);
  }

  function onStopTracking() {
    setTracking(false);
  }

  return (
    <section className="page-shell">
      <h2 className="section-title">Live Search</h2>

      <div className="two-pane">
        <div className="feature-card panel">
          <h3 className="panel-title">Search Control</h3>
          <p className="panel-subtitle">Step 1 only. Step 2 is available in Quick Search.</p>

          <div className="field-row">
            <Label htmlFor="live-source-mode">Source</Label>
            <select
              id="live-source-mode"
              className="ui-select"
              value={sourceMode}
              onChange={(e) => {
                const v = (e.target.value as 'desktop' | 'mobile') || 'desktop';
                setSourceMode(v);
                setTracking(false);
                setError(null);
                if (v !== 'mobile') stopMobileCamera();
              }}
            >
              <option value="desktop">Desktop camera</option>
              <option value="mobile">iPhone camera (Safari)</option>
            </select>
          </div>

          {sourceMode === 'desktop' && (
            <div className="field-row">
              <Label htmlFor="live-camera-index">Camera index</Label>
              <Input
                id="live-camera-index"
                value={cameraIndex}
                onChange={(e) => setCameraIndex(e.target.value)}
                inputMode="numeric"
              />
            </div>
          )}

          <div className="field-row">
            <Label htmlFor="live-query">Query</Label>
            <Input
              id="live-query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. black wallet"
            />
            {exactRegistered && (
              <p style={{ marginTop: 6, opacity: 0.8 }}>
                Registered match: <strong>{exactRegistered}</strong>
              </p>
            )}
            {matchedRegistered.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <p style={{ marginBottom: 6, opacity: 0.8 }}>Registered items</p>
                <div className="file-chip-list">
                  {matchedRegistered.map((name) => (
                    <button
                      key={name}
                      type="button"
                      className="file-chip"
                      onClick={() => setQuery(name)}
                    >
                      <span>{name}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="btn-row">
            <Button
              className="w-full btn-intent-search"
              onClick={onRunSearch}
              disabled={loading || tracking || !query.trim()}
            >
              {loading ? 'Searching...' : 'Search Now'}
            </Button>
            <Button
              className="w-full btn-intent-preview"
              variant="outline"
              onClick={tracking ? onStopTracking : () => void onStartTracking()}
              disabled={loading || !query.trim()}
            >
              {tracking ? 'Stop Tracking' : 'Start Tracking'}
            </Button>
            <Button className="w-full btn-intent-cancel" variant="outline" onClick={resetLiveControls}>
              Reset Controls
            </Button>
          </div>

          {error && <p className="error">{error}</p>}
        </div>

        <div className="feature-card panel">
          <h3 className="panel-title">Current Frame</h3>

          <div className="preview-shell live-preview-shell">
            {sourceMode === 'desktop' && liveFrameSrc && (
              <img
                src={liveFrameSrc}
                alt="live-frame"
                className="preview-image"
              />
            )}
            {sourceMode === 'mobile' && (
              <video
                ref={mobileVideoRef}
                className="preview-image"
                playsInline
                muted
                autoPlay
              />
            )}
            {result?.found && result.bboxNorm && result.bboxNorm.length === 4 && (
              <div
                className="bbox-overlay"
                style={{
                  left: `${result.bboxNorm[0] * 100}%`,
                  top: `${result.bboxNorm[1] * 100}%`,
                  width: `${result.bboxNorm[2] * 100}%`,
                  height: `${result.bboxNorm[3] * 100}%`,
                }}
              />
            )}
          </div>
          {sourceMode === 'desktop' && previewError && <p className="empty-state" style={{ marginBottom: 8 }}>Live frame is unstable. Reconnecting...</p>}
          {sourceMode === 'mobile' && <p className="empty-state" style={{ marginBottom: 8 }}>iPhone에서 이 페이지를 열면 모바일 카메라 추적이 동작합니다.</p>}

          {!result && <p className="empty-state">Run a search to see results.</p>}

          {result && (
            <div className="result-box" style={{ marginTop: 10 }}>
              <div className="result-head">
                <p><strong>Live Result</strong></p>
                <span className={`status-badge ${result.found ? 'status-badge--found' : 'status-badge--notfound'}`}>
                  {result.found ? 'FOUND' : 'NOT FOUND'}
                </span>
              </div>
              <div className="result-head" style={{ marginBottom: 4 }}>
                <p><strong>Confidence</strong></p>
                <span className={`score-badge score-badge--${confidenceMeta(result.score).tone}`}>
                  {confidenceMeta(result.score).label}
                </span>
              </div>
              <p><strong>Found</strong>: {result.found ? 'yes' : 'no'}</p>
              <p><strong>Score</strong>: {result.score.toFixed(3)}</p>
              <p><strong>Detail</strong>: {result.detail}</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
