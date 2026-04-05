import { useEffect, useState } from 'react';
import { apiClient } from '../../api/client';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import type { CaptureStateDto } from '../../types/domain';

export function CapturePage() {
  const [cameraIndex, setCameraIndex] = useState('0');
  const [state, setState] = useState<CaptureStateDto | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewTick, setPreviewTick] = useState(Date.now());
  const [previewError, setPreviewError] = useState(false);

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

  useEffect(() => {
    refreshState();
  }, []);

  useEffect(() => {
    const t = window.setInterval(() => setPreviewTick(Date.now()), 700);
    return () => window.clearInterval(t);
  }, []);

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
            {apiClient.capturePreviewUrl(previewTick) && (
              <img
                src={apiClient.capturePreviewUrl(previewTick)}
                alt="camera-preview"
                className="preview-image"
                onError={() => setPreviewError(true)}
                onLoad={() => setPreviewError(false)}
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
