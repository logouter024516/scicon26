import { SummaryCard } from '../../components/cards/SummaryCard';
import { apiClient } from '../../api/client';
import { Button } from '../../components/ui/button';
import { Modal } from '../../components/ui/modal';
import { useDashboardData } from '../../hooks/useDashboardData';
import { useState } from 'react';

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 18) return 'Good afternoon';
  return 'Good evening';
}

export function HomePage() {
  const { summary, clips, loading, error, refresh } = useDashboardData();
  const [previewClipId, setPreviewClipId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const running = summary?.captureStatus === 'Running';

  const statusTone = running ? 'high' : 'low';
  const clipsTone = (summary?.totalClips ?? 0) > 10 ? 'high' : (summary?.totalClips ?? 0) > 0 ? 'medium' : 'low';
  const itemsTone = (summary?.addedItems ?? 0) > 5 ? 'high' : (summary?.addedItems ?? 0) > 0 ? 'medium' : 'low';

  function formatKoreanDateTime(value: string): string {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return new Intl.DateTimeFormat('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).format(d);
  }

  function goQuickTab(clipId: string, cameraId: string) {
    window.dispatchEvent(
      new CustomEvent('mf:quick-preset', {
        detail: { clipId, cameraId },
      }),
    );
    window.dispatchEvent(new CustomEvent('mf:navigate-tab', { detail: 'quick' }));
    window.dispatchEvent(new CustomEvent('mf:toast', { detail: { message: 'Quick Search preset applied', tone: 'info' } }));
  }

  async function onDeleteClip() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await apiClient.deleteClipById(deleteTarget);
      setDeleteTarget(null);
      await refresh();
      window.dispatchEvent(new CustomEvent('mf:toast', { detail: { message: 'Clip deleted', tone: 'success' } }));
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to delete clip';
      const detailMatch = msg.match(/"detail"\s*:\s*"([^"]+)"/);
      const detail = detailMatch?.[1] ?? 'Failed to delete clip';
      window.dispatchEvent(new CustomEvent('mf:toast', { detail: { message: detail, tone: 'error' } }));
    } finally {
      setDeleting(false);
    }
  }

  return (
    <section className="page-shell">
      <h1 className="hero-title">
        {greeting()},
        <br />
        How can I assist you?
      </h1>

      <h2 className="section-title">Summary</h2>
      <div className="section-divider" />

      <div className="summary-toolbar">
        <p className="muted">Dashboard refreshes automatically every 5 seconds.</p>
        <Button className="btn-intent-refresh" variant="outline" onClick={refresh} disabled={loading}>Refresh now</Button>
      </div>

      {loading && <p>Loading dashboard...</p>}
      {error && <p className="error">{error}</p>}

      <div className="summary-grid">
        <SummaryCard
          title="Capture Status"
          value={summary?.captureStatus ?? '-'}
          badgeLabel={running ? 'LIVE' : 'STOPPED'}
          badgeTone={statusTone}
        />
        <SummaryCard
          title="Total video clips"
          value={String(summary?.totalClips ?? 0)}
          badgeLabel={(summary?.totalClips ?? 0) > 0 ? 'RECORDED' : 'EMPTY'}
          badgeTone={clipsTone}
        />
        <SummaryCard
          title="Added items"
          value={String(summary?.addedItems ?? 0)}
          badgeLabel={(summary?.addedItems ?? 0) > 0 ? 'READY' : 'NONE'}
          badgeTone={itemsTone}
        />
      </div>

      <h2 className="section-title" style={{ marginTop: 24 }}>Recent Clips</h2>
      <div className="recent-list">
        {clips.length === 0 ? (
          <p>No clips yet.</p>
        ) : (
          clips.map((c) => (
            <div key={c.clipId} className="recent-item">
              <img
                src={apiClient.thumbUrl(c.thumbFile || `${c.clipId}.jpg`)}
                alt="clip-thumbnail"
                className="recent-thumb"
                loading="lazy"
              />

              <div>
                <p className="recent-label">Clip ID</p>
                <p className="recent-value">{c.clipId}</p>
              </div>
              <div>
                <p className="recent-label">Event Time</p>
                <p className="recent-value">{formatKoreanDateTime(c.eventAt)}</p>
              </div>
              <div>
                <p className="recent-label">Camera</p>
                <p className="recent-value">{c.cameraId}</p>
              </div>
              <div className="recent-actions">
                <Button className="btn-intent-preview" variant="outline" onClick={() => setPreviewClipId(c.clipId)}>
                  Preview
                </Button>
                <Button className="btn-intent-quick" variant="ghost" onClick={() => goQuickTab(c.clipId, c.cameraId)}>
                  Quick
                </Button>
                <Button className="btn-intent-delete" variant="outline" onClick={() => setDeleteTarget(c.clipId)}>
                  Delete
                </Button>
              </div>
            </div>
          ))
        )}
      </div>

      <Modal open={previewClipId !== null} onClose={() => setPreviewClipId(null)} title="Clip Preview">
        {previewClipId ? (
          <video
            className="result-video"
            src={apiClient.clipUrl(clips.find((x) => x.clipId === previewClipId)?.clipFile || `${previewClipId}.mp4`)}
            controls
            autoPlay
            preload="metadata"
          />
        ) : null}
      </Modal>

      <Modal open={deleteTarget !== null} onClose={() => setDeleteTarget(null)} title="Delete Clip">
        <p className="muted" style={{ marginBottom: 12 }}>
          Delete <strong>{deleteTarget ?? ''}</strong>? Clip and thumbnail will be removed.
        </p>
        <div className="btn-row">
          <Button className="w-full btn-intent-delete" variant="outline" onClick={onDeleteClip} disabled={deleting || !deleteTarget}>
            {deleting ? 'Deleting...' : 'Delete'}
          </Button>
          <Button className="w-full btn-intent-cancel" type="button" variant="ghost" onClick={() => setDeleteTarget(null)}>
            Cancel
          </Button>
        </div>
      </Modal>
    </section>
  );
}
