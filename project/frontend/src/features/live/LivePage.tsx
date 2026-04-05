import { useEffect, useMemo, useState } from 'react';
import { apiClient } from '../../api/client';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import type { LiveResultDto } from '../../types/domain';

function confidenceMeta(score: number): { label: string; tone: 'high' | 'medium' | 'low' } {
  if (score >= 0.8) return { label: 'High', tone: 'high' };
  if (score >= 0.55) return { label: 'Medium', tone: 'medium' };
  return { label: 'Low', tone: 'low' };
}

export function LivePage() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<LiveResultDto | null>(null);
  const [cameraIndex, setCameraIndex] = useState('0');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewTick, setPreviewTick] = useState(Date.now());

  useEffect(() => {
    const t = window.setInterval(() => setPreviewTick(Date.now()), 700);
    return () => window.clearInterval(t);
  }, []);

  const cameraIndexNum = useMemo(() => Number.parseInt(cameraIndex, 10) || 0, [cameraIndex]);
  const liveFrameUrl = useMemo(
    () => apiClient.liveFrameUrl(cameraIndexNum, previewTick),
    [cameraIndexNum, previewTick],
  );

  async function onRunSearch() {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.liveSearch(query, cameraIndexNum);
      setResult(res);
      setPreviewTick(Date.now());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page-shell">
      <h2 className="section-title">Live Search</h2>

      <div className="two-pane">
        <div className="feature-card panel">
          <h3 className="panel-title">Search Control</h3>
          <p className="panel-subtitle">Step 1 only. Step 2 is available in Quick Search.</p>

          <div className="field-row">
            <Label htmlFor="live-camera-index">Camera index</Label>
            <Input
              id="live-camera-index"
              value={cameraIndex}
              onChange={(e) => setCameraIndex(e.target.value)}
              inputMode="numeric"
            />
          </div>

          <div className="field-row">
            <Label htmlFor="live-query">Query</Label>
            <Input
              id="live-query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. black wallet"
            />
          </div>

          <div className="btn-row">
            <Button className="w-full btn-intent-search" onClick={onRunSearch} disabled={loading || !query.trim()}>
              {loading ? 'Searching...' : 'Search Now'}
            </Button>
          </div>

          {error && <p className="error">{error}</p>}
        </div>

        <div className="feature-card panel">
          <h3 className="panel-title">Current Frame</h3>

          <div className="preview-shell live-preview-shell">
            {liveFrameUrl && (
              <img
                src={liveFrameUrl}
                alt="live-frame"
                className="preview-image"
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
