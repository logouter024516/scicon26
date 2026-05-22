import { useEffect, useMemo, useState } from 'react';
import { apiClient } from '../../api/client';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import type { CaptureProbeItemDto, CaptureStateDto } from '../../types/domain';

export function CapturePage() {
  const [cameraIndex, setCameraIndex] = useState('0');
  const [cameraId, setCameraId] = useState('ambient_cam_0');
  const [probeItems, setProbeItems] = useState<CaptureProbeItemDto[]>([]);
  const [probeLoading, setProbeLoading] = useState(false);
  const [probeError, setProbeError] = useState<string | null>(null);
  const [state, setState] = useState<CaptureStateDto | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewTick, setPreviewTick] = useState(Date.now());
  const [previewError, setPreviewError] = useState(false);
  const [previewSrc, setPreviewSrc] = useState('');
  const [probeTick, setProbeTick] = useState(Date.now());

  async function refreshState() {
    setError(null);
    try {
      const s = await apiClient.captureState(cameraId);
      setState(s);
      setCameraIndex(String(s.cameraIndex));
      if (s.cameraId) setCameraId(s.cameraId);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    }
  }

  useEffect(() => {
    refreshState();
  }, []);

  async function probeCameras() {
    setProbeLoading(true);
    setProbeError(null);
    try {
      const res = await apiClient.captureProbe(6);
      setProbeItems(res);
      const okFirst = res.find((x) => x.ok);
      if (okFirst && (cameraIndex.trim() === '' || Number.isNaN(Number(cameraIndex)))) {
        setCameraIndex(String(okFirst.index));
      }
      setProbeTick(Date.now());
    } catch (e) {
      setProbeError(e instanceof Error ? e.message : 'Camera probe failed');
    } finally {
      setProbeLoading(false);
    }
  }

  useEffect(() => {
    void probeCameras();
  }, []);

  const activeIndex = useMemo(() => {
    const parsed = Number.parseInt(cameraIndex, 10);
    return Number.isFinite(parsed) ? parsed : 0;
  }, [cameraIndex]);

  useEffect(() => {
    const t = window.setInterval(() => setPreviewTick(Date.now()), 850);
    return () => window.clearInterval(t);
  }, []);

  useEffect(() => {
    const nextUrl = apiClient.capturePreviewUrl(previewTick, cameraId);
    if (!nextUrl) return;

    let cancelled = false;
    const probe = new Image();
    probe.onload = () => {
      if (cancelled) return;
      setPreviewSrc(nextUrl);
      setPreviewError(false);
    };
    probe.onerror = () => {
      if (cancelled) return;
      setPreviewError(true);
    };
    probe.src = nextUrl;

    return () => {
      cancelled = true;
    };
  }, [previewTick]);

  async function onStart() {
    setLoading(true);
    setError(null);
    try {
      const idx = Number.parseInt(cameraIndex, 10) || 0;
      const cid = cameraId || `ambient_cam_${idx}`;
      const next = await apiClient.startCapture(idx, cid);
      setState(next);
      if (next.cameraId) setCameraId(next.cameraId);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  async function onStop() {
    setLoading(true);
    setError(null);
    try {
      setState(await apiClient.stopCapture(cameraId));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page-shell">
      <h2 className="section-title">Capture</h2>

      <div className="two-pane">
        <div className="feature-card panel">
          <h3 className="panel-title">Capture Control</h3>
          <p className="panel-subtitle">Motion events are recorded into local clip storage.</p>

          <div className="field-row">
            <Label>Camera selection</Label>
            <div style={{ display: 'grid', gap: 12 }}>
              <div className="btn-row" style={{ marginTop: 0 }}>
                <Button
                  className="btn-intent-refresh"
                  type="button"
                  variant="ghost"
                  onClick={probeCameras}
                  disabled={probeLoading}
                >
                  {probeLoading ? 'Scanning cameras...' : 'Scan Cameras'}
                </Button>
              </div>
              {probeError && <p className="error">{probeError}</p>}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                  gap: 12,
                }}
              >
                {probeItems.length === 0 ? (
                  <div className="result-box">
                    <p>No cameras detected. Try “Scan Cameras”.</p>
                  </div>
                ) : (
                  probeItems.map((cam) => {
                    const isActive = cam.index === activeIndex;
                    const previewUrl = cam.ok
                      ? apiClient.captureProbePreviewUrl(cam.index, probeTick)
                      : '';
                    return (
                      <button
                        key={cam.index}
                        type="button"
                        onClick={() => {
                          setCameraIndex(String(cam.index));
                          setCameraId(`ambient_cam_${cam.index}`);
                        }}
                        className="result-box"
                        style={{
                          textAlign: 'left',
                          cursor: cam.ok ? 'pointer' : 'not-allowed',
                          opacity: cam.ok ? 1 : 0.5,
                          border: isActive ? '2px solid #4f8cff' : undefined,
                        }}
                        disabled={!cam.ok}
                      >
                        <div style={{ marginBottom: 8 }}>
                          <strong>Camera {cam.index}</strong>
                          {cam.ok && cam.width && cam.height && (
                            <span style={{ marginLeft: 6, opacity: 0.7 }}>
                              {cam.width}x{cam.height}
                            </span>
                          )}
                        </div>
                        {cam.ok && previewUrl ? (
                          <img
                            src={previewUrl}
                            alt={`probe-${cam.index}`}
                            style={{ width: '100%', borderRadius: 8 }}
                          />
                        ) : (
                          <p className="muted" style={{ margin: 0 }}>
                            Not available
                          </p>
                        )}
                      </button>
                    );
                  })
                )}
              </div>
              <p className="muted" style={{ marginTop: 4 }}>
                Choose the camera that shows the correct preview. The index matches backend capture.
              </p>
            </div>
          </div>

          <div className="field-row">
            <Label htmlFor="camera-index">Camera index (advanced)</Label>
            <Input
              id="camera-index"
              value={cameraIndex}
              onChange={(e) => {
                const next = e.target.value;
                setCameraIndex(next);
                const parsed = Number.parseInt(next, 10);
                if (Number.isFinite(parsed)) {
                  setCameraId(`ambient_cam_${parsed}`);
                }
              }}
              inputMode="numeric"
            />
          </div>

          <div className="btn-row">
            <Button className="w-full btn-intent-start" onClick={onStart} disabled={loading || state?.running}>Start Capture</Button>
            <Button className="w-full btn-intent-stop" onClick={onStop} variant="outline" disabled={loading}>Stop Capture</Button>
            <Button className="w-full btn-intent-refresh" onClick={refreshState} variant="ghost" disabled={loading}>Refresh State</Button>
          </div>

          {error && <p className="error">{error}</p>}
        </div>

        <div className="feature-card panel">
          <h3 className="panel-title">Runtime Status & Preview</h3>

          <div className="preview-shell">
            {previewSrc && (
              <img
                src={previewSrc}
                alt="camera-preview"
                className="preview-image"
              />
            )}
            {previewError && <p className="empty-state">No preview frame yet. Start capture first.</p>}
          </div>

          <div className="stat-grid">
            <div className="result-box">
              <p><strong>Running</strong></p>
              <p>{state?.running ? 'yes' : 'no'}</p>
            </div>
            <div className="result-box">
              <p><strong>Camera Index</strong></p>
              <p>{state?.cameraIndex ?? '-'}</p>
            </div>
          </div>
          <p className="muted">If camera is busy, stop other camera apps and refresh state.</p>
        </div>
      </div>
    </section>
  );
}
