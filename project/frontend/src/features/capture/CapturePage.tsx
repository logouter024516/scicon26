import { useEffect, useState } from 'react';
import { apiClient } from '../../api/client';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import type { CameraDeviceDto, CaptureStateDto } from '../../types/domain';

export function CapturePage() {
  const [cameraIndex, setCameraIndex] = useState('0');
  const [devices, setDevices] = useState<CameraDeviceDto[]>([]);
  const [state, setState] = useState<CaptureStateDto | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewTick, setPreviewTick] = useState(Date.now());
  const [previewError, setPreviewError] = useState(false);
  const [previewSrc, setPreviewSrc] = useState('');

  async function refreshState() {
    setError(null);
    try {
      const s = await apiClient.captureState();
      setState(s);
      setCameraIndex(String(s.cameraIndex));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    }
  }

  async function refreshDevices() {
    try {
      const ds = await apiClient.captureDevices(12);
      setDevices(ds);
      if (ds.length > 0 && !ds.some((d) => String(d.index) === cameraIndex)) {
        setCameraIndex(String(ds[0].index));
      }
    } catch {
      setDevices([]);
    }
  }

  useEffect(() => {
    void refreshState();
    void refreshDevices();
  }, []);

  useEffect(() => {
    const t = window.setInterval(() => setPreviewTick(Date.now()), 850);
    return () => window.clearInterval(t);
  }, []);

  useEffect(() => {
    const nextUrl = apiClient.capturePreviewUrl(previewTick);
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
      setState(await apiClient.startCapture(idx));
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
      setState(await apiClient.stopCapture());
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
            <Label htmlFor="camera-index">Camera index</Label>
            <Input
              id="camera-index"
              value={cameraIndex}
              onChange={(e) => setCameraIndex(e.target.value)}
              inputMode="numeric"
            />
          </div>

          {devices.length > 0 && (
            <div className="field-row">
              <Label htmlFor="camera-device-select">Detected devices</Label>
              <select
                id="camera-device-select"
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

          <div className="btn-row">
            <Button className="w-full btn-intent-start" onClick={onStart} disabled={loading || state?.running}>Start Capture</Button>
            <Button className="w-full btn-intent-stop" onClick={onStop} variant="outline" disabled={loading}>Stop Capture</Button>
            <Button className="w-full btn-intent-refresh" onClick={() => { void refreshState(); void refreshDevices(); }} variant="ghost" disabled={loading}>Refresh State</Button>
          </div>

          <div className="result-box" style={{ marginTop: 10 }}>
            <p><strong>무선 차단 환경 추천</strong></p>
            <p className="muted">iPhone/Android를 USB 웹캠 앱(예: Camo, Iriun, DroidCam)으로 연결 후, 위 목록의 카메라 인덱스를 선택해 사용하세요.</p>
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
