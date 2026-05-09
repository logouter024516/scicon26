import { useEffect, useMemo, useRef, useState } from 'react';
import { apiClient } from '../../api/client';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import type { CameraDeviceDto, LiveResultDto } from '../../types/domain';

const LIVE_QUERY_STORAGE_KEY = 'mf.live.query';
const LIVE_CAMERA_STORAGE_KEY = 'mf.live.cameraIndex';
const LIVE_CAMERA_SOURCE_STORAGE_KEY = 'mf.live.cameraSource';

function confidenceMeta(score: number): { label: string; tone: 'high' | 'medium' | 'low' } {
  if (score >= 0.8) return { label: 'High', tone: 'high' };
  if (score >= 0.55) return { label: 'Medium', tone: 'medium' };
  return { label: 'Low', tone: 'low' };
}

export function LivePage() {
  const publicPhoneBaseUrl = (import.meta.env.VITE_PHONE_PUBLIC_URL as string | undefined)?.trim() || '';
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
  const [cameraSource, setCameraSource] = useState(() => {
    try {
      return window.localStorage.getItem(LIVE_CAMERA_SOURCE_STORAGE_KEY) ?? '';
    } catch {
      return '';
    }
  });
  const [registeredItems, setRegisteredItems] = useState<string[]>([]);
  const [sourceMode, setSourceMode] = useState<'auto' | 'desktop' | 'mobile'>(() => {
    const ua = navigator.userAgent || '';
    const mobile = /iPhone|iPad|Android|Mobile/i.test(ua);
    return mobile ? 'mobile' : 'auto';
  });
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [phoneSessionId, setPhoneSessionId] = useState('');
  const [phoneLink, setPhoneLink] = useState('');
  const [phoneSessionValid, setPhoneSessionValid] = useState<boolean | null>(null);
  const [devices, setDevices] = useState<CameraDeviceDto[]>([]);
  const [tracking, setTracking] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewTick, setPreviewTick] = useState(Date.now());
  const [previewError, setPreviewError] = useState(false);
  const [liveFrameSrc, setLiveFrameSrc] = useState('');
  const [mobileReady, setMobileReady] = useState(false);
  const mobileVideoRef = useRef<HTMLVideoElement | null>(null);
  const mobileStreamRef = useRef<MediaStream | null>(null);
  const isMobileClient = useMemo(() => /iPhone|iPad|Android|Mobile/i.test(navigator.userAgent || ''), []);
  const useMobileSource = sourceMode === 'mobile' || (sourceMode === 'auto' && isMobileClient);
  const usePhoneBridge = sourceMode === 'mobile' && !isMobileClient;
  const showPhoneConnector = !isMobileClient;
  const phoneQrUrl = useMemo(() => {
    if (!phoneLink) return '';
    const encoded = encodeURIComponent(phoneLink);
    return `https://api.qrserver.com/v1/create-qr-code/?size=220x220&margin=0&data=${encoded}`;
  }, [phoneLink]);

  useEffect(() => {
    const t = window.setInterval(() => {
      if (!useMobileSource) setPreviewTick(Date.now());
    }, 850);
    return () => window.clearInterval(t);
  }, [useMobileSource]);

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
    let mounted = true;
    async function loadDevices() {
      try {
        const ds = await apiClient.captureDevices(12);
        if (!mounted) return;
        setDevices(ds);
        if (ds.length > 0 && !ds.some((d) => String(d.index) === cameraIndex)) {
          setCameraIndex(String(ds[0].index));
        }
      } catch {
        if (!mounted) return;
        setDevices([]);
      }
    }
    void loadDevices();
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

  useEffect(() => {
    try {
      if (cameraSource.trim()) {
        window.localStorage.setItem(LIVE_CAMERA_SOURCE_STORAGE_KEY, cameraSource);
      } else {
        window.localStorage.removeItem(LIVE_CAMERA_SOURCE_STORAGE_KEY);
      }
    } catch {
      // ignore storage errors
    }
  }, [cameraSource]);

  function resetLiveControls() {
    setQuery('');
    setCameraIndex('0');
    setCameraSource('');
    setResult(null);
    setTracking(false);
    stopMobileCamera();
    try {
      window.localStorage.removeItem(LIVE_QUERY_STORAGE_KEY);
      window.localStorage.removeItem(LIVE_CAMERA_STORAGE_KEY);
      window.localStorage.removeItem(LIVE_CAMERA_SOURCE_STORAGE_KEY);
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
    () => apiClient.liveFrameUrl(cameraIndexNum, previewTick, cameraSource),
    [cameraIndexNum, previewTick, cameraSource],
  );

  useEffect(() => {
    if (useMobileSource) return;
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
  }, [liveFrameUrl, useMobileSource]);

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
      const useMobile = useMobileSource;
      let imageBlob: Blob | null = null;
      if (usePhoneBridge) {
        const res = await apiClient.liveSearchUnified({
          query,
          phoneSessionId,
          cameraIndex: cameraIndexNum,
          cameraSource,
        });
        setResult(res);
        setPreviewTick(Date.now());
        setLoading(false);
        return;
      }
      if (useMobile) {
        await ensureMobileCamera();
        imageBlob = await captureMobileFrameBlob();
        if (!imageBlob) throw new Error('모바일 카메라 프레임 캡처 실패');
      }

      const res = await apiClient.liveSearchUnified({
        query,
        imageBlob,
        fileName: 'phone-frame.jpg',
        cameraIndex: cameraIndexNum,
        cameraSource,
      });

      setResult(res);
      if (!useMobile) setPreviewTick(Date.now());
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
        const useMobile = sourceMode === 'mobile';
        let imageBlob: Blob | null = null;
        if (usePhoneBridge) {
          const res = await apiClient.liveSearchUnified({
            query,
            phoneSessionId,
            cameraIndex: cameraIndexNum,
            cameraSource,
          });
          setResult(res);
          setPreviewTick(Date.now());
          busy = false;
          return;
        }
        if (useMobile) {
          await ensureMobileCamera();
          imageBlob = await captureMobileFrameBlob();
          if (!imageBlob) {
            busy = false;
            return;
          }
        }

        const res = await apiClient.liveSearchUnified({
          query,
          imageBlob,
          fileName: 'phone-frame.jpg',
          cameraIndex: cameraIndexNum,
          cameraSource,
        });
        setResult(res);
        if (!useMobile) setPreviewTick(Date.now());
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error');
      } finally {
        busy = false;
      }
    }, 650);
    return () => window.clearInterval(timer);
  }, [tracking, query, useMobileSource, usePhoneBridge, phoneSessionId, cameraIndexNum, cameraSource]);

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
    if (usePhoneBridge && !phoneSessionId.trim()) {
      setError('먼저 폰 연결 세션을 생성해 주세요.');
      return;
    }
    if (useMobileSource && !usePhoneBridge) {
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

  async function onCreatePhoneSession() {
    setError(null);
    try {
      const s = await apiClient.createPhoneSession();
      setPhoneSessionId(s.sessionId);
      setPhoneSessionValid(true);
      let baseUrl = publicPhoneBaseUrl;

      if (!baseUrl) {
        try {
          const ts = await apiClient.startPhoneTunnel(window.location.origin);
          if (ts.running && ts.publicUrl) {
            baseUrl = ts.publicUrl;
            window.dispatchEvent(new CustomEvent('mf:toast', { detail: { message: '터널 자동 연결 성공', tone: 'success' } }));
          } else if (ts.detail) {
            window.dispatchEvent(new CustomEvent('mf:toast', { detail: { message: `터널 자동 연결 실패: ${ts.detail}`, tone: 'error' } }));
          }
        } catch {
          // ignore and fallback to LAN URL
        }
      }

      const u = baseUrl ? new URL(baseUrl) : new URL(window.location.href);
      if (!baseUrl && (u.hostname === 'localhost' || u.hostname === '127.0.0.1')) {
        try {
          const net = await apiClient.phoneNetworkInfo();
          const host = (net.hosts || [])[0];
          if (host) {
            u.hostname = host;
          }
        } catch {
          // fallback to current hostname
        }
      }
      u.searchParams.set('phone', '1');
      u.searchParams.set('session', s.sessionId);
      setPhoneLink(u.toString());
      window.dispatchEvent(new CustomEvent('mf:toast', { detail: { message: '폰 연결 세션 생성 완료', tone: 'success' } }));
    } catch (e) {
      setError(e instanceof Error ? e.message : '세션 생성 실패');
    }
  }

  async function onCopyPhoneLink() {
    if (!phoneLink) return;
    try {
      await navigator.clipboard.writeText(phoneLink);
      window.dispatchEvent(new CustomEvent('mf:toast', { detail: { message: '폰 연결 링크 복사 완료', tone: 'success' } }));
    } catch {
      window.dispatchEvent(new CustomEvent('mf:toast', { detail: { message: '링크 복사 실패', tone: 'error' } }));
    }
  }

  async function onValidatePhoneSession() {
    const sid = phoneSessionId.trim();
    if (!sid) {
      setPhoneSessionValid(null);
      return;
    }
    setError(null);
    try {
      const r = await apiClient.phoneSessionExists(sid);
      setPhoneSessionValid(Boolean(r.ok));
      if (!r.ok) {
        setError('세션이 유효하지 않습니다. PC에서 새 세션을 생성해 주세요.');
      }
    } catch (e) {
      setPhoneSessionValid(false);
      setError(e instanceof Error ? e.message : '세션 확인 실패');
    }
  }

  function onOpenPhonePage() {
    const sid = phoneSessionId.trim();
    const url = new URL(window.location.href);
    url.searchParams.set('phone', '1');
    if (sid) url.searchParams.set('session', sid);
    window.open(url.toString(), '_blank', 'noopener,noreferrer');
  }

  return (
    <section className="page-shell">
      <h2 className="section-title">Live Search</h2>

      <div className="two-pane">
        <div className="feature-card panel">
          <h3 className="panel-title">Search Control</h3>
          <p className="panel-subtitle">검색어 + 시작/정지만 입력하면 백엔드가 나머지 처리를 자동 수행합니다.</p>

          <div className="field-row">
            <Label htmlFor="live-source-mode">Source</Label>
            <select
              id="live-source-mode"
              className="ui-select"
              value={sourceMode}
              onChange={(e) => {
                const v = (e.target.value as 'auto' | 'desktop' | 'mobile') || 'auto';
                setSourceMode(v as 'auto' | 'desktop' | 'mobile');
                setTracking(false);
                setError(null);
                if (v !== 'mobile') stopMobileCamera();
              }}
            >
              <option value="auto">Auto (권장)</option>
              <option value="desktop">Desktop camera</option>
              <option value="mobile">Phone camera (Android/iPhone)</option>
            </select>
          </div>

          {showPhoneConnector && (
            <div className="result-box" style={{ marginBottom: 10 }}>
              <p><strong>Phone Session</strong>: {phoneSessionId || 'not created'}</p>
              <div className="field-row" style={{ marginTop: 8 }}>
                <Label htmlFor="phone-session-manual">Session ID (manual)</Label>
                <Input
                  id="phone-session-manual"
                  value={phoneSessionId}
                  onChange={(e) => {
                    setPhoneSessionId(e.target.value);
                    setPhoneSessionValid(null);
                  }}
                  placeholder="세션 ID 붙여넣기"
                />
                <p className="muted" style={{ marginTop: 6 }}>
                  상태: {phoneSessionValid == null ? '확인 전' : phoneSessionValid ? '유효한 세션' : '유효하지 않은 세션'}
                </p>
              </div>
              {phoneSessionId && (
                <p className="muted">링크가 안 되면 폰에서 <strong>/ ?phone=1</strong> 페이지를 열고 Session ID를 수동 입력하세요.</p>
              )}
              <div className="btn-row">
                <Button className="w-full btn-intent-refresh" variant="outline" onClick={() => void onCreatePhoneSession()}>
                  Create Phone Session
                </Button>
                <Button className="w-full btn-intent-preview" variant="outline" onClick={() => void onValidatePhoneSession()} disabled={!phoneSessionId.trim()}>
                  Validate Session
                </Button>
                <Button className="w-full btn-intent-preview" variant="outline" onClick={() => void onCopyPhoneLink()} disabled={!phoneLink}>
                  Copy Phone Link
                </Button>
                <Button className="w-full" variant="outline" onClick={onOpenPhonePage}>
                  Open Phone Page
                </Button>
              </div>
              <p className="muted" style={{ marginTop: 8 }}>
                Manual phone page: {window.location.origin}/?phone=1
              </p>
              {phoneLink && <p className="muted" style={{ marginTop: 8, wordBreak: 'break-all' }}>{phoneLink}</p>}
              {phoneQrUrl && (
                <div style={{ marginTop: 10, display: 'grid', placeItems: 'center' }}>
                  <img
                    src={phoneQrUrl}
                    alt="phone-connection-qr"
                    style={{ width: 180, height: 180, borderRadius: 10, border: '1px solid var(--border)' }}
                  />
                  <p className="muted" style={{ marginTop: 8 }}>
                    스마트폰 카메라로 QR을 스캔해 연결 페이지를 여세요.
                  </p>
                </div>
              )}
            </div>
          )}

          <div className="field-row" style={{ marginTop: -4 }}>
            <button
              type="button"
              className="quick-group-toggle"
              onClick={() => setAdvancedOpen((v) => !v)}
            >
              {advancedOpen ? '고급 설정 닫기' : '고급 설정 열기'}
            </button>
          </div>

          {advancedOpen && !useMobileSource && (
            <>
              <div className="field-row">
                <Label htmlFor="live-camera-index">Camera index (고급)</Label>
                <Input
                  id="live-camera-index"
                  value={cameraIndex}
                  onChange={(e) => setCameraIndex(e.target.value)}
                  inputMode="numeric"
                />
              </div>
              {devices.length > 0 && (
                <div className="field-row">
                  <Label htmlFor="live-camera-device">Detected camera (USB iPhone 포함)</Label>
                  <select
                    id="live-camera-device"
                    className="ui-select"
                    value={cameraIndex}
                    onChange={(e) => setCameraIndex(e.target.value)}
                  >
                    {devices.map((d) => (
                      <option key={d.index} value={String(d.index)}>
                        {d.label} ({d.width ?? 0}x{d.height ?? 0})
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div className="field-row">
                <Label htmlFor="live-camera-source">External camera URL (완전 대체 방식)</Label>
                <Input
                  id="live-camera-source"
                  value={cameraSource}
                  onChange={(e) => setCameraSource(e.target.value)}
                  placeholder="예: http://192.168.x.x:8080/video 또는 rtsp://..."
                />
                <p className="muted" style={{ marginTop: 6 }}>
                  링크/QR 없이도 동작: 폰 카메라 앱(예: IP Camera)을 켜고 URL만 넣으면 서버가 직접 프레임을 읽습니다.
                </p>
              </div>
            </>
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
            {!useMobileSource && liveFrameSrc && (
              <img
                src={liveFrameSrc}
                alt="live-frame"
                className="preview-image"
              />
            )}
            {usePhoneBridge && phoneSessionId && (
              <img
                src={apiClient.phoneFrameUrl(phoneSessionId, previewTick)}
                alt="phone-bridge-frame"
                className="preview-image"
              />
            )}
            {useMobileSource && !usePhoneBridge && (
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
          {!useMobileSource && previewError && <p className="empty-state" style={{ marginBottom: 8 }}>Live frame is unstable. Reconnecting...</p>}
          {useMobileSource && !usePhoneBridge && <p className="empty-state" style={{ marginBottom: 8 }}>안드로이드/아이폰 브라우저에서 모두 동작합니다.</p>}
          {usePhoneBridge && <p className="empty-state" style={{ marginBottom: 8 }}>폰 링크를 열어 스트리밍을 시작하면 여기에서 자동 반영됩니다.</p>}

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
