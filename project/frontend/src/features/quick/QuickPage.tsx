import { useCallback, useEffect, useRef, useState } from 'react';
import type { KeyboardEvent as ReactKeyboardEvent } from 'react';
import { apiClient } from '../../api/client';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import type { QuickResultDto } from '../../types/domain';

function cameraIndexFromId(cameraId?: string): string {
  if (!cameraId) return '-';
  const m = cameraId.match(/(\d+)$/);
  return m ? m[1] : cameraId;
}

function formatKoreanDateTime(value?: string): string {
  if (!value) return '-';
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

type SortMode = 'score' | 'time';

function confidenceMeta(score: number): { label: string; tone: 'high' | 'medium' | 'low' } {
  if (score >= 0.8) return { label: 'High', tone: 'high' };
  if (score >= 0.55) return { label: 'Medium', tone: 'medium' };
  return { label: 'Low', tone: 'low' };
}

export function QuickPage() {
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<QuickResultDto[]>([]);
  const [visibleCount, setVisibleCount] = useState(6);
  const [expandedClip, setExpandedClip] = useState<string | null>(null);
  const [cameraFilter, setCameraFilter] = useState('all');
  const [sortMode, setSortMode] = useState<SortMode>('score');
  const [presetClipId, setPresetClipId] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const videoRefs = useRef<Record<string, HTMLVideoElement | null>>({});
  const rowRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const executeSearch = useCallback(async (searchQuery: string, notify = true) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.quickSearch(searchQuery);
      setItems(res);
      setVisibleCount(6);
      setExpandedClip(null);
      setSelectedIndex(0);
      if (notify) {
        window.dispatchEvent(
          new CustomEvent('mf:toast', {
            detail: {
              message: `Quick Search done (${res.length} result${res.length === 1 ? '' : 's'})`,
              tone: 'success',
            },
          }),
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
      if (notify) {
        window.dispatchEvent(new CustomEvent('mf:toast', { detail: { message: 'Quick Search failed', tone: 'error' } }));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    function onQuickPreset(e: Event) {
      const custom = e as CustomEvent;
      const payload = custom.detail as { clipId?: string; cameraId?: string } | undefined;
      const clipId = payload?.clipId?.trim();
      const cameraId = payload?.cameraId;
      const cam = cameraIndexFromId(cameraId);

      if (clipId) {
        setPresetClipId(clipId);
        setQuery(clipId);
        void executeSearch(clipId, false);
      }
      if (cam && cam !== '-') {
        setCameraFilter(cam);
      }
    }

    window.addEventListener('mf:quick-preset', onQuickPreset as EventListener);
    return () => window.removeEventListener('mf:quick-preset', onQuickPreset as EventListener);
  }, [executeSearch]);

  async function onSearch() {
    await executeSearch(query);
  }

  const filteredSortedItems = items
    .filter((x) => cameraFilter === 'all' || cameraIndexFromId(x.cameraId) === cameraFilter)
    .sort((a, b) => {
      if (sortMode === 'time') {
        const ta = Date.parse(a.eventAt ?? '');
        const tb = Date.parse(b.eventAt ?? '');
        const va = Number.isFinite(ta) ? ta : -Infinity;
        const vb = Number.isFinite(tb) ? tb : -Infinity;
        return vb - va;
      }
      return b.score - a.score;
    });

  const cameraOptions = Array.from(new Set(items.map((x) => cameraIndexFromId(x.cameraId)).filter((x) => x !== '-')));
  const visibleItems = filteredSortedItems.slice(0, visibleCount);

  useEffect(() => {
    const refs = videoRefs.current;
    Object.entries(refs).forEach(([clipId, el]) => {
      if (!el) return;
      if (expandedClip !== clipId) {
        el.pause();
        el.currentTime = 0;
      }
    });

    if (expandedClip && refs[expandedClip]) {
      void refs[expandedClip]?.play().catch(() => undefined);
    }
  }, [expandedClip]);

  useEffect(() => {
    if (visibleItems.length === 0) {
      setSelectedIndex(0);
      return;
    }
    if (selectedIndex > visibleItems.length - 1) {
      setSelectedIndex(visibleItems.length - 1);
    }
  }, [selectedIndex, visibleItems.length]);

  useEffect(() => {
    const target = visibleItems[selectedIndex];
    if (!target) return;
    const el = rowRefs.current[target.clipId];
    el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [selectedIndex, visibleItems]);

  function onResultsKeyDown(e: ReactKeyboardEvent<HTMLDivElement>) {
    if (visibleItems.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((v) => Math.min(v + 1, visibleItems.length - 1));
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((v) => Math.max(v - 1, 0));
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      const selected = visibleItems[selectedIndex];
      if (!selected?.clipFile) return;
      setExpandedClip((prev) => (prev === selected.clipId ? null : selected.clipId));
    }
  }

  useEffect(() => {
    return () => {
      Object.values(videoRefs.current).forEach((el) => {
        if (!el) return;
        el.pause();
      });
    };
  }, []);

  return (
    <section className="page-shell">
      <h2 className="section-title">Quick Search</h2>

      <div className="two-pane">
        <div className="feature-card panel">
          <h3 className="panel-title">Search Control</h3>
          <p className="panel-subtitle">Search across saved clips and rank candidates by similarity score.</p>

          <div className="field-row">
            <Label htmlFor="quick-query">Query</Label>
            <Input
              id="quick-query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. key"
            />
          </div>

          <Button className="w-full btn-intent-search" onClick={onSearch} disabled={loading || !query.trim()}>
            {loading ? 'Searching...' : 'Run Quick Search'}
          </Button>

          {presetClipId && (
            <div className="result-box" style={{ marginTop: 10 }}>
              <p><strong>Preset clip</strong>: {presetClipId}</p>
              <p><strong>Camera filter</strong>: {cameraFilter === 'all' ? 'All cameras' : `Camera ${cameraFilter}`}</p>
              <div className="preview-actions">
                <Button
                  className="btn-intent-cancel"
                  variant="ghost"
                  onClick={() => {
                    setPresetClipId(null);
                    setCameraFilter('all');
                  }}
                >
                  Clear preset
                </Button>
              </div>
            </div>
          )}

          <div className="filter-grid">
            <div className="field-row" style={{ marginBottom: 0 }}>
              <Label htmlFor="quick-camera-filter">Camera filter</Label>
              <select
                id="quick-camera-filter"
                className="ui-select"
                value={cameraFilter}
                onChange={(e) => setCameraFilter(e.target.value)}
              >
                <option value="all">All cameras</option>
                {cameraOptions.map((v) => (
                  <option key={v} value={v}>
                    Camera {v}
                  </option>
                ))}
              </select>
            </div>

            <div className="field-row" style={{ marginBottom: 0 }}>
              <Label htmlFor="quick-sort-mode">Sort</Label>
              <select
                id="quick-sort-mode"
                className="ui-select"
                value={sortMode}
                onChange={(e) => setSortMode(e.target.value as SortMode)}
              >
                <option value="score">By score</option>
                <option value="time">By latest time</option>
              </select>
            </div>
          </div>

          {error && <p className="error">{error}</p>}
        </div>

        <div className="feature-card panel">
          <h3 className="panel-title">Ranked Results</h3>
          <p className="muted">Keyboard: ↑/↓ to move, Enter to play/hide.</p>
          <div className="result-list list-scroll" tabIndex={0} onKeyDown={onResultsKeyDown}>
            {filteredSortedItems.length === 0 ? (
              <p className="empty-state">No results yet.</p>
            ) : (
              visibleItems.map((x, i) => {
                const isExpanded = expandedClip === x.clipId;
                const conf = confidenceMeta(x.score);
                return (
                  <div
                    ref={(el) => {
                      rowRefs.current[x.clipId] = el;
                    }}
                    className={`result-box ${i === selectedIndex ? 'result-box--active' : ''}`}
                    key={`${x.clipId}-${x.score}`}
                  >
                    <div className="result-head">
                      <p><strong>#{i + 1}</strong> · {x.clipId}</p>
                      <span className={`score-badge score-badge--${conf.tone}`}>{conf.label}</span>
                    </div>
                    <p><strong>Score</strong>: {x.score.toFixed(3)}</p>
                    <p><strong>Detail</strong>: {x.detail}</p>
                    <p><strong>Camera index</strong>: {cameraIndexFromId(x.cameraId)}</p>
                    <p><strong>Captured at</strong>: {formatKoreanDateTime(x.eventAt)}</p>

                    {x.thumbFile && !isExpanded && (
                      <img className="result-thumb" src={apiClient.thumbUrl(x.thumbFile)} alt="clip-thumb" loading="lazy" />
                    )}

                    {x.clipFile && (
                      <div className="preview-actions">
                        <Button
                          className="btn-intent-preview"
                          variant="outline"
                          onClick={() => setExpandedClip((prev) => (prev === x.clipId ? null : x.clipId))}
                        >
                          {isExpanded ? 'Hide Clip' : 'Play Clip'}
                        </Button>
                      </div>
                    )}

                    {x.clipFile && isExpanded && (
                      <video
                        ref={(el) => {
                          videoRefs.current[x.clipId] = el;
                        }}
                        className="result-video"
                        src={apiClient.clipUrl(x.clipFile)}
                        poster={x.thumbFile ? apiClient.thumbUrl(x.thumbFile) : undefined}
                        controls
                        preload="metadata"
                      />
                    )}
                  </div>
                );
              })
            )}

            {filteredSortedItems.length > visibleCount && (
              <Button className="w-full" variant="outline" onClick={() => setVisibleCount((v) => v + 6)}>
                Load More Results
              </Button>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
