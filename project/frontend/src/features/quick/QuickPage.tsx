import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent as ReactKeyboardEvent } from 'react';
import { apiClient } from '../../api/client';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import type { QuickResultDto } from '../../types/domain';

const QUICK_CAMERA_FILTER_STORAGE_KEY = 'mf.quick.cameraFilter';
const QUICK_SORT_MODE_STORAGE_KEY = 'mf.quick.sortMode';
const QUICK_GROUP_MODE_STORAGE_KEY = 'mf.quick.groupMode';
const QUICK_RESULT_FILTER_STORAGE_KEY = 'mf.quick.resultFilterText';

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
type GroupMode = 'none' | 'camera' | 'date';

function confidenceMeta(score: number): { label: string; tone: 'high' | 'medium' | 'low' } {
  if (score >= 0.8) return { label: 'High', tone: 'high' };
  if (score >= 0.55) return { label: 'Medium', tone: 'medium' };
  return { label: 'Low', tone: 'low' };
}

export function QuickPage() {
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<QuickResultDto[]>([]);
  const [registeredItems, setRegisteredItems] = useState<string[]>([]);
  const [visibleCount, setVisibleCount] = useState(6);
  const [cameraFilter, setCameraFilter] = useState(() => {
    try {
      return window.localStorage.getItem(QUICK_CAMERA_FILTER_STORAGE_KEY) ?? 'all';
    } catch {
      return 'all';
    }
  });
  const [resultFilterText, setResultFilterText] = useState(() => {
    try {
      return window.localStorage.getItem(QUICK_RESULT_FILTER_STORAGE_KEY) ?? '';
    } catch {
      return '';
    }
  });
  const [sortMode, setSortMode] = useState<SortMode>(() => {
    try {
      const v = window.localStorage.getItem(QUICK_SORT_MODE_STORAGE_KEY);
      return v === 'time' ? 'time' : 'score';
    } catch {
      return 'score';
    }
  });
  const [groupMode, setGroupMode] = useState<GroupMode>(() => {
    try {
      const v = window.localStorage.getItem(QUICK_GROUP_MODE_STORAGE_KEY);
      if (v === 'camera' || v === 'date' || v === 'none') return v;
      return 'none';
    } catch {
      return 'none';
    }
  });
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});
  const [presetClipId, setPresetClipId] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
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

  const rowRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const executeSearch = useCallback(async (searchQuery: string, notify = true) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.quickSearch(searchQuery);
      setItems(res);
      setVisibleCount(6);
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
    try {
      window.localStorage.setItem(QUICK_CAMERA_FILTER_STORAGE_KEY, cameraFilter);
    } catch {
      // ignore storage errors
    }
  }, [cameraFilter]);

  useEffect(() => {
    try {
      window.localStorage.setItem(QUICK_SORT_MODE_STORAGE_KEY, sortMode);
    } catch {
      // ignore storage errors
    }
  }, [sortMode]);

  useEffect(() => {
    try {
      window.localStorage.setItem(QUICK_GROUP_MODE_STORAGE_KEY, groupMode);
    } catch {
      // ignore storage errors
    }
  }, [groupMode]);

  useEffect(() => {
    try {
      if (resultFilterText) {
        window.localStorage.setItem(QUICK_RESULT_FILTER_STORAGE_KEY, resultFilterText);
      } else {
        window.localStorage.removeItem(QUICK_RESULT_FILTER_STORAGE_KEY);
      }
    } catch {
      // ignore storage errors
    }
  }, [resultFilterText]);

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
    .filter((x) => {
      const q = resultFilterText.trim().toLowerCase();
      if (!q) return true;
      const haystack = `${x.clipId} ${x.detail} ${x.cameraId ?? ''} ${x.eventAt ?? ''}`.toLowerCase();
      return haystack.includes(q);
    })
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

  const cameraOptions = Array.from(new Set(items.map((x) => cameraIndexFromId(x.cameraId)).filter((x) => x !== '-')));
  const visibleItems = filteredSortedItems.slice(0, visibleCount);

  useEffect(() => {
    if (cameraFilter === 'all') return;
    if (!cameraOptions.includes(cameraFilter)) {
      setCameraFilter('all');
    }
  }, [cameraFilter, cameraOptions]);

  const groupedVisibleItems = useMemo(() => {
    const keyToItems = new Map<string, QuickResultDto[]>();
    const keyToLabel = new Map<string, string>();

    function groupKey(item: QuickResultDto): { key: string; label: string } {
      if (groupMode === 'camera') {
        const cam = cameraIndexFromId(item.cameraId);
        return { key: `cam:${cam}`, label: cam === '-' ? 'Camera: Unknown' : `Camera ${cam}` };
      }
      if (groupMode === 'date') {
        const d = new Date(item.eventAt ?? '');
        if (Number.isNaN(d.getTime())) return { key: 'date:unknown', label: 'Date: Unknown' };
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return { key: `date:${y}-${m}-${day}`, label: `${y}-${m}-${day}` };
      }
      return { key: 'all', label: 'All Results' };
    }

    for (const item of visibleItems) {
      const g = groupKey(item);
      if (!keyToItems.has(g.key)) {
        keyToItems.set(g.key, []);
        keyToLabel.set(g.key, g.label);
      }
      keyToItems.get(g.key)?.push(item);
    }

    return Array.from(keyToItems.entries()).map(([key, groupItems]) => ({
      key,
      label: keyToLabel.get(key) ?? key,
      items: groupItems,
    }));
  }, [groupMode, visibleItems]);

  const navigableItems = useMemo(() => {
    if (groupMode === 'none') return visibleItems;
    const out: QuickResultDto[] = [];
    for (const group of groupedVisibleItems) {
      if (collapsedGroups[group.key]) continue;
      out.push(...group.items);
    }
    return out;
  }, [collapsedGroups, groupMode, groupedVisibleItems, visibleItems]);

  const visibleIndexByClipId = useMemo(() => {
    const map = new Map<string, number>();
    navigableItems.forEach((item, idx) => {
      map.set(item.clipId, idx);
    });
    return map;
  }, [navigableItems]);

  useEffect(() => {
    setCollapsedGroups({});
  }, [groupMode]);

  useEffect(() => {
    if (navigableItems.length === 0) {
      setSelectedIndex(0);
      return;
    }
    if (selectedIndex > navigableItems.length - 1) {
      setSelectedIndex(navigableItems.length - 1);
    }
  }, [selectedIndex, navigableItems.length]);

  useEffect(() => {
    const target = navigableItems[selectedIndex];
    if (!target) return;
    const el = rowRefs.current[target.clipId];
    el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [selectedIndex, navigableItems]);

  function onResultsKeyDown(e: ReactKeyboardEvent<HTMLDivElement>) {
    if (navigableItems.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((v) => Math.min(v + 1, navigableItems.length - 1));
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((v) => Math.max(v - 1, 0));
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      return;
    }
  }

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

          <Button
            className="w-full btn-intent-search"
            onClick={onSearch}
            disabled={loading || !query.trim()}
          >
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
              <Label htmlFor="quick-result-filter">Result text filter</Label>
              <Input
                id="quick-result-filter"
                value={resultFilterText}
                onChange={(e) => setResultFilterText(e.target.value)}
                placeholder="clip id / detail / camera"
              />
            </div>

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

            <div className="field-row" style={{ marginBottom: 0 }}>
              <Label htmlFor="quick-group-mode">Group</Label>
              <select
                id="quick-group-mode"
                className="ui-select"
                value={groupMode}
                onChange={(e) => setGroupMode((e.target.value as GroupMode) || 'none')}
              >
                <option value="none">No grouping</option>
                <option value="camera">By camera</option>
                <option value="date">By date</option>
              </select>
            </div>
          </div>

          {error && <p className="error">{error}</p>}
        </div>

        <div className="feature-card panel">
          <h3 className="panel-title">Ranked Results</h3>
          <p className="muted">Keyboard: ↑/↓ move (visible list).</p>
          <p className="muted">Showing {filteredSortedItems.length} / {items.length}</p>
          <div className="result-list list-scroll" tabIndex={0} onKeyDown={onResultsKeyDown}>
            {filteredSortedItems.length === 0 ? (
              <p className="empty-state">No results yet.</p>
            ) : (
              groupedVisibleItems.map((group) => (
                <div className="quick-group" key={group.key}>
                  {groupMode !== 'none' && (
                    <div className="quick-group-head">
                      <p className="quick-group-title">{group.label} ({group.items.length})</p>
                      <button
                        type="button"
                        className="quick-group-toggle"
                        onClick={() => setCollapsedGroups((prev) => ({
                          ...prev,
                          [group.key]: !prev[group.key],
                        }))}
                      >
                        {collapsedGroups[group.key] ? 'Expand' : 'Collapse'}
                      </button>
                    </div>
                  )}
                  {!collapsedGroups[group.key] && group.items.map((x) => {
                    const i = visibleIndexByClipId.get(x.clipId) ?? 0;
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

                        {x.thumbFile && (
                          <img className="result-thumb" src={apiClient.thumbUrl(x.thumbFile)} alt="clip-thumb" loading="lazy" />
                        )}
                      </div>
                    );
                  })}
                </div>
              ))
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
