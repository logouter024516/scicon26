import { useEffect, useMemo, useRef, useState } from 'react';
import { apiClient } from '../../api/client';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Modal } from '../../components/ui/modal';
import type { RegisteredItemDto } from '../../types/domain';

const REGISTER_DRAFT_NAME_KEY = 'mf.register.draftName';
const REGISTER_SEARCH_KEY = 'mf.register.searchText';
const REGISTER_SORT_KEY = 'mf.register.sortMode';
const REGISTER_AUTO_EXCLUDE_WARN_KEY = 'mf.register.autoExcludeWarnings';
const REGISTER_DARK_THRESHOLD_KEY = 'mf.register.quality.darkThreshold';
const REGISTER_BRIGHT_THRESHOLD_KEY = 'mf.register.quality.brightThreshold';
const REGISTER_BLUR_THRESHOLD_KEY = 'mf.register.quality.blurThreshold';

const BLUR_THRESHOLD_MIN = 1;
const BLUR_THRESHOLD_MAX = 8;

type FileQuality = {
  tone: 'ok' | 'warn';
  labels: string[];
};

type QualityPreset = 'strict' | 'normal' | 'relaxed' | 'custom';

const QUALITY_PRESETS: Record<Exclude<QualityPreset, 'custom'>, { dark: number; bright: number; blur: number }> = {
  strict: { dark: 85, bright: 195, blur: 5 },
  normal: { dark: 70, bright: 210, blur: 3.5 },
  relaxed: { dark: 55, bright: 225, blur: 2.5 },
};

function normalizeBlurThreshold(value: number): number {
  if (!Number.isFinite(value)) return QUALITY_PRESETS.normal.blur;
  if (value > BLUR_THRESHOLD_MAX) {
    const scaled = value / 3;
    return Math.max(BLUR_THRESHOLD_MIN, Math.min(BLUR_THRESHOLD_MAX, scaled));
  }
  return Math.max(BLUR_THRESHOLD_MIN, Math.min(BLUR_THRESHOLD_MAX, value));
}

export function RegisterPage() {
  const [name, setName] = useState(() => {
    try {
      return window.localStorage.getItem(REGISTER_DRAFT_NAME_KEY) ?? '';
    } catch {
      return '';
    }
  });
  const [files, setFiles] = useState<File[]>([]);
  const [primaryIndex, setPrimaryIndex] = useState(0);
  const [items, setItems] = useState<RegisteredItemDto[]>([]);
  const [searchText, setSearchText] = useState(() => {
    try {
      return window.localStorage.getItem(REGISTER_SEARCH_KEY) ?? '';
    } catch {
      return '';
    }
  });
  const [sortMode, setSortMode] = useState<'latest' | 'name'>(() => {
    try {
      const saved = window.localStorage.getItem(REGISTER_SORT_KEY);
      return saved === 'name' ? 'name' : 'latest';
    } catch {
      return 'latest';
    }
  });
  const [modalOpen, setModalOpen] = useState(false);
  const [cameraModalOpen, setCameraModalOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [cameraLoading, setCameraLoading] = useState(false);
  const [burstLoading, setBurstLoading] = useState(false);
  const [burstCount, setBurstCount] = useState<3 | 5>(3);
  const [dragOverUpload, setDragOverUpload] = useState(false);
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null);
  const [previewIndex, setPreviewIndex] = useState<number | null>(null);
  const [croppingIndex, setCroppingIndex] = useState<number | null>(null);
  const [fileQualities, setFileQualities] = useState<FileQuality[]>([]);
  const [qualityFilterMode, setQualityFilterMode] = useState<'all' | 'warn'>('all');
  const [darkThreshold, setDarkThreshold] = useState(() => {
    try {
      return Number.parseFloat(window.localStorage.getItem(REGISTER_DARK_THRESHOLD_KEY) ?? '70') || 70;
    } catch {
      return 70;
    }
  });
  const [brightThreshold, setBrightThreshold] = useState(() => {
    try {
      return Number.parseFloat(window.localStorage.getItem(REGISTER_BRIGHT_THRESHOLD_KEY) ?? '210') || 210;
    } catch {
      return 210;
    }
  });
  const [blurThreshold, setBlurThreshold] = useState(() => {
    try {
      const saved = Number.parseFloat(window.localStorage.getItem(REGISTER_BLUR_THRESHOLD_KEY) ?? '');
      const initial = Number.isFinite(saved) ? saved : QUALITY_PRESETS.normal.blur;
      return normalizeBlurThreshold(initial);
    } catch {
      return QUALITY_PRESETS.normal.blur;
    }
  });
  const [autoExcludeWarnings, setAutoExcludeWarnings] = useState(() => {
    try {
      return (window.localStorage.getItem(REGISTER_AUTO_EXCLUDE_WARN_KEY) ?? 'false') === 'true';
    } catch {
      return false;
    }
  });
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const cameraVideoRef = useRef<HTMLVideoElement | null>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const pausedCaptureRef = useRef<{ paused: boolean; cameraIndex: number }>({ paused: false, cameraIndex: 0 });

  const previewUrls = useMemo(
    () => files.map((f) => ({ name: f.name, url: URL.createObjectURL(f) })),
    [files],
  );

  useEffect(() => {
    return () => {
      previewUrls.forEach((x) => URL.revokeObjectURL(x.url));
    };
  }, [previewUrls]);

  useEffect(() => {
    if (files.length === 0) {
      setPrimaryIndex(0);
      return;
    }
    if (primaryIndex >= files.length) {
      setPrimaryIndex(0);
    }
  }, [files, primaryIndex]);

  useEffect(() => {
    let cancelled = false;

    async function analyzeOne(file: File): Promise<FileQuality> {
      const objectUrl = URL.createObjectURL(file);
      try {
        const img = await new Promise<HTMLImageElement>((resolve, reject) => {
          const el = new Image();
          el.onload = () => resolve(el);
          el.onerror = () => reject(new Error('image load failed'));
          el.src = objectUrl;
        });

        const targetW = 180;
        const ratio = img.naturalWidth > 0 ? targetW / img.naturalWidth : 1;
        const w = Math.max(60, Math.round(img.naturalWidth * ratio));
        const h = Math.max(60, Math.round(img.naturalHeight * ratio));
        const canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          return { tone: 'warn', labels: ['analysis error'] };
        }

        ctx.drawImage(img, 0, 0, w, h);
        const data = ctx.getImageData(0, 0, w, h).data;

        let sumLum = 0;
        let edgeSum = 0;
        let edgeCount = 0;
        const lumas = new Float32Array(w * h);

        for (let y = 0; y < h; y += 1) {
          for (let x = 0; x < w; x += 1) {
            const i = (y * w + x) * 4;
            const r = data[i];
            const g = data[i + 1];
            const b = data[i + 2];
            const lum = 0.299 * r + 0.587 * g + 0.114 * b;
            lumas[y * w + x] = lum;
            sumLum += lum;
          }
        }

        for (let y = 1; y < h; y += 1) {
          for (let x = 1; x < w; x += 1) {
            const c = lumas[y * w + x];
            const lx = lumas[y * w + (x - 1)];
            const uy = lumas[(y - 1) * w + x];
            const gx = Math.abs(c - lx);
            const gy = Math.abs(c - uy);
            edgeSum += gx + gy;
            edgeCount += 2;
          }
        }

        const meanLum = sumLum / (w * h);
        const meanEdge = edgeCount > 0 ? edgeSum / edgeCount : 0;

        const labels: string[] = [];
        if (Math.min(img.naturalWidth, img.naturalHeight) < 420) labels.push('low resolution');
        if (meanLum < darkThreshold) labels.push('too dark');
        if (meanLum > brightThreshold) labels.push('too bright');
        if (meanEdge < blurThreshold) labels.push('blurry');

        return {
          tone: labels.length > 0 ? 'warn' : 'ok',
          labels: labels.length > 0 ? labels : ['good quality'],
        };
      } catch {
        return { tone: 'warn', labels: ['analysis error'] };
      } finally {
        URL.revokeObjectURL(objectUrl);
      }
    }

    async function analyzeAll() {
      if (files.length === 0) {
        setFileQualities([]);
        return;
      }
      const results = await Promise.all(files.map((f) => analyzeOne(f)));
      if (!cancelled) {
        setFileQualities(results);
      }
    }

    void analyzeAll();
    return () => {
      cancelled = true;
    };
  }, [files, darkThreshold, brightThreshold, blurThreshold]);

  const visibleFileIndexes = useMemo(() => {
    if (qualityFilterMode === 'all') {
      return files.map((_, idx) => idx);
    }
    return files
      .map((_, idx) => idx)
      .filter((idx) => (fileQualities[idx]?.tone ?? 'ok') === 'warn');
  }, [files, fileQualities, qualityFilterMode]);

  const warningIndexes = useMemo(
    () => files
      .map((_, idx) => idx)
      .filter((idx) => (fileQualities[idx]?.tone ?? 'ok') === 'warn'),
    [files, fileQualities],
  );

  const savableIndexes = useMemo(() => {
    if (!autoExcludeWarnings) return files.map((_, idx) => idx);
    const warn = new Set(warningIndexes);
    return files.map((_, idx) => idx).filter((idx) => !warn.has(idx));
  }, [autoExcludeWarnings, files, warningIndexes]);

  const saveSummary = useMemo(() => {
    const total = files.length;
    const warnings = warningIndexes.length;
    const savable = savableIndexes.length;
    const excluded = total - savable;

    const sourceIndexes = autoExcludeWarnings ? savableIndexes : files.map((_, idx) => idx);
    const mappedPrimary = sourceIndexes.indexOf(primaryIndex);
    const finalPrimaryIndex = sourceIndexes.length === 0 ? null : (mappedPrimary >= 0 ? mappedPrimary : 0);
    const primaryFileName = finalPrimaryIndex === null
      ? '-'
      : (files[sourceIndexes[finalPrimaryIndex]]?.name ?? '-');

    return {
      total,
      warnings,
      savable,
      excluded,
      primaryFileName,
    };
  }, [autoExcludeWarnings, files, primaryIndex, savableIndexes, warningIndexes]);

  const currentPreset = useMemo<QualityPreset>(() => {
    const close = (a: number, b: number, eps = 0.26) => Math.abs(a - b) <= eps;
    if (
      close(darkThreshold, QUALITY_PRESETS.strict.dark)
      && close(brightThreshold, QUALITY_PRESETS.strict.bright)
      && close(blurThreshold, QUALITY_PRESETS.strict.blur)
    ) {
      return 'strict';
    }
    if (
      close(darkThreshold, QUALITY_PRESETS.normal.dark)
      && close(brightThreshold, QUALITY_PRESETS.normal.bright)
      && close(blurThreshold, QUALITY_PRESETS.normal.blur)
    ) {
      return 'normal';
    }
    if (
      close(darkThreshold, QUALITY_PRESETS.relaxed.dark)
      && close(brightThreshold, QUALITY_PRESETS.relaxed.bright)
      && close(blurThreshold, QUALITY_PRESETS.relaxed.blur)
    ) {
      return 'relaxed';
    }
    return 'custom';
  }, [darkThreshold, brightThreshold, blurThreshold]);

  useEffect(() => {
    try {
      window.localStorage.setItem(REGISTER_AUTO_EXCLUDE_WARN_KEY, autoExcludeWarnings ? 'true' : 'false');
    } catch {
      // ignore storage errors
    }
  }, [autoExcludeWarnings]);

  useEffect(() => {
    try {
      window.localStorage.setItem(REGISTER_DARK_THRESHOLD_KEY, String(darkThreshold));
      window.localStorage.setItem(REGISTER_BRIGHT_THRESHOLD_KEY, String(brightThreshold));
      window.localStorage.setItem(REGISTER_BLUR_THRESHOLD_KEY, String(blurThreshold));
    } catch {
      // ignore storage errors
    }
  }, [darkThreshold, brightThreshold, blurThreshold]);

  function removeWarningFiles() {
    if (warningIndexes.length === 0) return;

    const warningSet = new Set(warningIndexes);
    const keptIndexes = files
      .map((_, idx) => idx)
      .filter((idx) => !warningSet.has(idx));

    setFiles(files.filter((_, idx) => !warningSet.has(idx)));
    setPrimaryIndex(() => {
      if (keptIndexes.length === 0) return 0;
      const mapped = keptIndexes.indexOf(primaryIndex);
      return mapped >= 0 ? mapped : 0;
    });
    setPreviewIndex((prev) => {
      if (prev === null) return null;
      const mapped = keptIndexes.indexOf(prev);
      return mapped >= 0 ? mapped : null;
    });
    setDraggingIndex(null);
    if (qualityFilterMode === 'warn' && keptIndexes.length === 0) {
      setQualityFilterMode('all');
    }

    window.dispatchEvent(
      new CustomEvent('mf:toast', {
        detail: { message: `Removed ${warningIndexes.length} warning image(s)`, tone: 'success' },
      }),
    );
  }

  function applyQualityPreset(preset: Exclude<QualityPreset, 'custom'>) {
    const t = QUALITY_PRESETS[preset];
    setDarkThreshold(t.dark);
    setBrightThreshold(t.bright);
    setBlurThreshold(t.blur);
  }

  useEffect(() => {
    try {
      if (name.trim()) {
        window.localStorage.setItem(REGISTER_DRAFT_NAME_KEY, name);
      } else {
        window.localStorage.removeItem(REGISTER_DRAFT_NAME_KEY);
      }
    } catch {
      // ignore storage errors
    }
  }, [name]);

  useEffect(() => {
    try {
      if (searchText.trim()) {
        window.localStorage.setItem(REGISTER_SEARCH_KEY, searchText);
      } else {
        window.localStorage.removeItem(REGISTER_SEARCH_KEY);
      }
    } catch {
      // ignore storage errors
    }
  }, [searchText]);

  useEffect(() => {
    try {
      window.localStorage.setItem(REGISTER_SORT_KEY, sortMode);
    } catch {
      // ignore storage errors
    }
  }, [sortMode]);

  function hasUnsavedDraft(): boolean {
    return Boolean(name.trim()) || files.length > 0;
  }

  function closeAddModal(force = false) {
    if (!force && hasUnsavedDraft()) {
      const ok = window.confirm('Discard current draft? (selected images and item name will be kept only if you stay)');
      if (!ok) return;
    }
    setModalOpen(false);
  }

  function clearDraft() {
    setName('');
    setFiles([]);
    setPrimaryIndex(0);
    setPreviewIndex(null);
  }

  function stopCameraStream() {
    if (!cameraStreamRef.current) return;
    cameraStreamRef.current.getTracks().forEach((t) => t.stop());
    cameraStreamRef.current = null;
  }

  async function pauseBackendCaptureForRegisterCamera() {
    try {
      const st = await apiClient.captureState();
      if (!st.running) {
        pausedCaptureRef.current = { paused: false, cameraIndex: st.cameraIndex ?? 0 };
        return;
      }

      pausedCaptureRef.current = { paused: true, cameraIndex: st.cameraIndex ?? 0 };
      await apiClient.stopCapture();

      for (let i = 0; i < 12; i += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 100));
        const cur = await apiClient.captureState();
        if (!cur.running) break;
      }

      window.dispatchEvent(
        new CustomEvent('mf:toast', {
          detail: { message: '카메라 등록을 위해 캡처를 일시 중지했습니다.', tone: 'success' },
        }),
      );
    } catch {
      pausedCaptureRef.current = { paused: false, cameraIndex: 0 };
    }
  }

  async function resumeBackendCaptureAfterRegisterCamera() {
    const info = pausedCaptureRef.current;
    if (!info.paused) return;
    pausedCaptureRef.current = { paused: false, cameraIndex: info.cameraIndex };
    try {
      await apiClient.startCapture(info.cameraIndex);
      window.dispatchEvent(
        new CustomEvent('mf:toast', {
          detail: { message: '등록 카메라 종료 후 캡처를 자동 재시작했습니다.', tone: 'success' },
        }),
      );
    } catch {
      window.dispatchEvent(
        new CustomEvent('mf:toast', {
          detail: { message: '캡처 자동 재시작에 실패했습니다. Capture 탭에서 다시 시작해 주세요.', tone: 'error' },
        }),
      );
    }
  }

  async function openCameraModal() {
    setCameraLoading(true);
    setError(null);
    try {
      await pauseBackendCaptureForRegisterCamera();
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      cameraStreamRef.current = stream;
      setCameraModalOpen(true);
      requestAnimationFrame(() => {
        if (cameraVideoRef.current) {
          cameraVideoRef.current.srcObject = stream;
          void cameraVideoRef.current.play().catch(() => undefined);
        }
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'camera open failed');
      await resumeBackendCaptureAfterRegisterCamera();
    } finally {
      setCameraLoading(false);
    }
  }

  function closeCameraModal() {
    setCameraModalOpen(false);
    if (cameraVideoRef.current) {
      cameraVideoRef.current.srcObject = null;
    }
    stopCameraStream();
    void resumeBackendCaptureAfterRegisterCamera();
  }

  function appendImageFiles(incoming: File[]) {
    setFiles((prev) => {
      const imageFiles = incoming.filter((f) => f.type.startsWith('image/'));
      if (imageFiles.length === 0) return prev;

      const merged = [...prev, ...imageFiles];
      const seen = new Set<string>();
      const deduped: File[] = [];
      for (const f of merged) {
        const key = `${f.name}:${f.size}:${f.lastModified}`;
        if (seen.has(key)) continue;
        seen.add(key);
        deduped.push(f);
      }
      return deduped;
    });

    setPrimaryIndex((prev) => prev);
  }

  function moveFile(from: number, to: number) {
    if (from === to) return;
    setFiles((prev) => {
      if (from < 0 || to < 0 || from >= prev.length || to >= prev.length) return prev;
      const next = [...prev];
      const [picked] = next.splice(from, 1);
      next.splice(to, 0, picked);
      return next;
    });
    setPrimaryIndex((prev) => {
      if (prev === from) return to;
      if (from < prev && to >= prev) return prev - 1;
      if (from > prev && to <= prev) return prev + 1;
      return prev;
    });
  }

  async function cropCenterSquare(index: number) {
    const srcFile = files[index];
    if (!srcFile) return;

    setCroppingIndex(index);
    try {
      const objectUrl = URL.createObjectURL(srcFile);
      const img = await new Promise<HTMLImageElement>((resolve, reject) => {
        const el = new Image();
        el.onload = () => resolve(el);
        el.onerror = () => reject(new Error('failed to load image'));
        el.src = objectUrl;
      });

      const srcW = img.naturalWidth;
      const srcH = img.naturalHeight;
      if (srcW <= 0 || srcH <= 0) {
        URL.revokeObjectURL(objectUrl);
        throw new Error('invalid image size');
      }

      const side = Math.min(srcW, srcH);
      const sx = Math.floor((srcW - side) / 2);
      const sy = Math.floor((srcH - side) / 2);
      const canvas = document.createElement('canvas');
      canvas.width = side;
      canvas.height = side;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        URL.revokeObjectURL(objectUrl);
        throw new Error('canvas context unavailable');
      }

      ctx.drawImage(img, sx, sy, side, side, 0, 0, side, side);

      const blob = await new Promise<Blob | null>((resolve) => {
        canvas.toBlob((b) => resolve(b), 'image/jpeg', 0.93);
      });
      URL.revokeObjectURL(objectUrl);
      if (!blob) throw new Error('crop failed');

      const ext = '.jpg';
      const base = srcFile.name.replace(/\.[^.]+$/, '') || 'image';
      const cropped = new File([blob], `${base}_crop${ext}`, { type: 'image/jpeg' });
      setFiles((prev) => prev.map((f, i) => (i === index ? cropped : f)));
      window.dispatchEvent(new CustomEvent('mf:toast', { detail: { message: 'Center crop applied', tone: 'success' } }));
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'crop failed';
      window.dispatchEvent(new CustomEvent('mf:toast', { detail: { message: msg, tone: 'error' } }));
    } finally {
      setCroppingIndex(null);
    }
  }

  async function captureFromCamera(silent = false): Promise<boolean> {
    const video = cameraVideoRef.current;
    if (!video || video.videoWidth <= 0 || video.videoHeight <= 0) return false;

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return false;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob((b) => resolve(b), 'image/jpeg', 0.92);
    });
    if (!blob) return false;

    const file = new File([blob], `camera_${Date.now()}.jpg`, { type: 'image/jpeg' });
    setFiles((prev) => {
      const next = [...prev, file];
      if (prev.length === 0) {
        setPrimaryIndex(0);
      }
      return next;
    });
    if (!silent) {
      window.dispatchEvent(new CustomEvent('mf:toast', { detail: { message: 'Photo captured', tone: 'success' } }));
    }
    return true;
  }

  async function burstCapture() {
    setBurstLoading(true);
    let okCount = 0;
    try {
      for (let i = 0; i < burstCount; i += 1) {
        const ok = await captureFromCamera(true);
        if (ok) okCount += 1;
        if (i < burstCount - 1) {
          await new Promise((resolve) => window.setTimeout(resolve, 350));
        }
      }
      const tone = okCount > 0 ? 'success' : 'error';
      const msg = okCount > 0 ? `Burst captured ${okCount} photo(s)` : 'Burst capture failed';
      window.dispatchEvent(new CustomEvent('mf:toast', { detail: { message: msg, tone } }));
    } finally {
      setBurstLoading(false);
    }
  }

  async function load() {
    setError(null);
    try {
      setItems(await apiClient.listRegistered());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    }
  }

  useEffect(() => {
    load();
    return () => {
      stopCameraStream();
      void resumeBackendCaptureAfterRegisterCamera();
    };
  }, []);

  useEffect(() => {
    if (!modalOpen) return;
    function onKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'enter') {
        e.preventDefault();
        if (!loading && name.trim() && files.length > 0) {
          void onAdd();
        }
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'o') {
        e.preventDefault();
        fileRef.current?.click();
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'c') {
        e.preventDefault();
        if (!cameraLoading) {
          void openCameraModal();
        }
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [modalOpen, loading, name, files.length, cameraLoading]);

  const filteredItems = useMemo(() => {
    const q = searchText.trim().toLowerCase();
    const base = q
      ? items.filter((x) => x.name.toLowerCase().includes(q))
      : items;

    const out = [...base];
    if (sortMode === 'name') {
      out.sort((a, b) => a.name.localeCompare(b.name));
      return out;
    }

    out.sort((a, b) => {
      const ta = Date.parse(a.createdAt ?? '');
      const tb = Date.parse(b.createdAt ?? '');
      const va = Number.isFinite(ta) ? ta : 0;
      const vb = Number.isFinite(tb) ? tb : 0;
      return vb - va;
    });
    return out;
  }, [items, searchText, sortMode]);

  function formatKoreanDateTime(value?: string): string {
    if (!value) return '-';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return '-';
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

  async function onAdd() {
    setLoading(true);
    setError(null);
    try {
      const saveTargets = autoExcludeWarnings
        ? files.filter((_, idx) => savableIndexes.includes(idx))
        : files;

      if (saveTargets.length === 0) {
        throw new Error('No savable images. Disable auto-exclude or add better quality images.');
      }

      let orderedFiles = saveTargets;
      if (saveTargets.length > 1) {
        const sourceIndexes = autoExcludeWarnings ? savableIndexes : files.map((_, idx) => idx);
        const mappedPrimary = sourceIndexes.indexOf(primaryIndex);
        const p = mappedPrimary >= 0 ? mappedPrimary : 0;
        orderedFiles = [saveTargets[p], ...saveTargets.filter((_, idx) => idx !== p)];
      }
      await apiClient.addRegistered(name.trim(), orderedFiles);
      clearDraft();
      setModalOpen(false);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  async function onDelete(itemName: string) {
    setLoading(true);
    setError(null);
    try {
      await apiClient.removeRegistered(itemName);
      setDeleteTarget(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page-shell">
      <h2 className="section-title">Register</h2>

      <div className="two-pane">
        <div className="feature-card panel">
          <h3 className="panel-title">Reference Management</h3>
          <p className="panel-subtitle">Use custom modal flow to keep interaction consistent.</p>

          <div className="result-box">
            <p><strong>Total items</strong>: {items.length}</p>
            <p><strong>Status</strong>: {loading ? 'processing...' : 'ready'}</p>
          </div>

          <div className="btn-row" style={{ marginTop: 12 }}>
            <Button className="w-full btn-intent-search" onClick={() => setModalOpen(true)} disabled={loading}>
              Open Add Item Modal
            </Button>
          </div>

          {error && <p className="error">{error}</p>}
        </div>

        <div className="feature-card panel">
          <h3 className="panel-title">Registered Items</h3>
          <div className="filter-grid" style={{ marginBottom: 10 }}>
            <div className="field-row" style={{ marginBottom: 0 }}>
              <Label htmlFor="register-search">Search</Label>
              <Input
                id="register-search"
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                placeholder="Search by name"
              />
            </div>
            <div className="field-row" style={{ marginBottom: 0 }}>
              <Label htmlFor="register-sort">Sort</Label>
              <select
                id="register-sort"
                className="ui-select"
                value={sortMode}
                onChange={(e) => setSortMode(e.target.value === 'name' ? 'name' : 'latest')}
              >
                <option value="latest">Latest first</option>
                <option value="name">Name (A-Z)</option>
              </select>
            </div>
          </div>
          <div className="result-list list-scroll">
            {filteredItems.length === 0 ? (
              <p className="empty-state">No registered items.</p>
            ) : (
              filteredItems.map((x) => (
                <div className="result-box result-inline" key={x.name}>
                  <div className="registered-item-head">
                    {x.thumbFile ? (
                      <img
                        src={apiClient.registeredImageUrl(x.thumbFile)}
                        alt={`${x.name}-thumb`}
                        className="registered-item-thumb"
                        loading="lazy"
                      />
                    ) : (
                      <div className="registered-item-thumb registered-item-thumb--placeholder" />
                    )}
                    <div className="registered-item-meta">
                      <span>{x.name}</span>
                      <small>{formatKoreanDateTime(x.createdAt)}</small>
                    </div>
                  </div>
                  <Button className="btn-intent-delete" variant="outline" onClick={() => setDeleteTarget(x.name)} disabled={loading}>
                    Delete
                  </Button>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <Modal
        open={modalOpen}
        onClose={() => closeAddModal()}
        title="Add Reference Item"
        className="register-modal-shell"
      >
        <div className="register-modal-layout">
          <p className="register-modal-sub">
            Choose clean reference photos. Set one as primary for stable matching.
          </p>
          <p className="register-modal-shortcuts">
            Shortcuts: Ctrl/⌘+O (select files), Ctrl/⌘+Shift+C (camera), Ctrl/⌘+Enter (save)
          </p>

          <div className="register-modal-section">
            <div className="field-row" style={{ marginBottom: 0 }}>
              <Label htmlFor="register-name-modal">Item name</Label>
              <Input
                id="register-name-modal"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. my key"
              />
            </div>
          </div>

          <div className="register-modal-section">
            <div className="register-modal-media-head">
              <Label>Item images</Label>
              <span className="register-selected-pill">{files.length} selected</span>
            </div>

            <label className="auto-exclude-toggle">
              <input
                type="checkbox"
                checked={autoExcludeWarnings}
                onChange={(e) => setAutoExcludeWarnings(e.target.checked)}
              />
              <span>Auto-exclude warning images on save</span>
            </label>

            <div className="quality-preset-row">
              <button
                type="button"
                className={`quality-preset-btn ${currentPreset === 'strict' ? 'is-active' : ''}`}
                onClick={() => applyQualityPreset('strict')}
              >
                Strict
              </button>
              <button
                type="button"
                className={`quality-preset-btn ${currentPreset === 'normal' ? 'is-active' : ''}`}
                onClick={() => applyQualityPreset('normal')}
              >
                Normal
              </button>
              <button
                type="button"
                className={`quality-preset-btn ${currentPreset === 'relaxed' ? 'is-active' : ''}`}
                onClick={() => applyQualityPreset('relaxed')}
              >
                Relaxed
              </button>
              <button
                type="button"
                className="quality-preset-btn"
                onClick={() => applyQualityPreset('normal')}
              >
                Reset
              </button>
              <span className="quality-preset-state">Preset: {currentPreset}</span>
            </div>

            <div className="quality-threshold-grid">
              <label className="quality-threshold-item">
                <span>Dark &lt; {darkThreshold.toFixed(0)}</span>
                <input
                  type="range"
                  min={30}
                  max={120}
                  step={1}
                  value={darkThreshold}
                  onChange={(e) => setDarkThreshold(Number(e.target.value))}
                />
              </label>
              <label className="quality-threshold-item">
                <span>Bright &gt; {brightThreshold.toFixed(0)}</span>
                <input
                  type="range"
                  min={160}
                  max={245}
                  step={1}
                  value={brightThreshold}
                  onChange={(e) => setBrightThreshold(Number(e.target.value))}
                />
              </label>
              <label className="quality-threshold-item">
                <span>Blur &lt; {blurThreshold.toFixed(2)}</span>
                <input
                  type="range"
                  min={BLUR_THRESHOLD_MIN}
                  max={BLUR_THRESHOLD_MAX}
                  step={0.25}
                  value={blurThreshold}
                  onChange={(e) => setBlurThreshold(normalizeBlurThreshold(Number(e.target.value)))}
                />
              </label>
            </div>

            <input
              ref={fileRef}
              type="file"
              multiple
              accept="image/*"
              className="hidden-file"
              onChange={(e) => {
                const next = Array.from(e.currentTarget.files ?? []);
                appendImageFiles(next);
              }}
            />

            <div
              className={`register-dropzone ${dragOverUpload ? 'is-over' : ''}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOverUpload(true);
              }}
              onDragLeave={() => setDragOverUpload(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOverUpload(false);
                const dropped = Array.from(e.dataTransfer.files ?? []);
                appendImageFiles(dropped);
              }}
            >
              <p className="register-dropzone-text">Drag image files here, or choose one of the actions below.</p>

              <div className="register-modal-tool-row">
                <Button className="btn-intent-preview" type="button" variant="outline" onClick={() => fileRef.current?.click()}>
                  Select Images
                </Button>
                <Button className="btn-intent-search" type="button" variant="outline" onClick={openCameraModal} disabled={cameraLoading}>
                  {cameraLoading ? 'Opening camera...' : 'Take Photo'}
                </Button>
              </div>
            </div>

            {files.length > 0 ? (
              <>
                <div className="quality-filter-row">
                  <button
                    type="button"
                    className={`quality-filter-btn ${qualityFilterMode === 'all' ? 'is-active' : ''}`}
                    onClick={() => setQualityFilterMode('all')}
                  >
                    All ({files.length})
                  </button>
                  <button
                    type="button"
                    className={`quality-filter-btn ${qualityFilterMode === 'warn' ? 'is-active' : ''}`}
                    onClick={() => setQualityFilterMode('warn')}
                  >
                    Warnings ({warningIndexes.length})
                  </button>
                  <Button
                    type="button"
                    variant="outline"
                    className="quality-remove-btn btn-intent-delete"
                    onClick={removeWarningFiles}
                    disabled={warningIndexes.length === 0}
                  >
                    Remove Warnings
                  </Button>
                </div>

                {autoExcludeWarnings && (
                  <p className="register-save-hint">
                    Save target: {savableIndexes.length} / {files.length} images (warnings auto-excluded)
                  </p>
                )}

                <div className="result-box register-save-summary">
                  <p><strong>Total</strong>: {saveSummary.total}</p>
                  <p><strong>Warnings</strong>: {saveSummary.warnings}</p>
                  <p><strong>Excluded on save</strong>: {saveSummary.excluded}</p>
                  <p><strong>Final save count</strong>: {saveSummary.savable}</p>
                  <p><strong>Primary on save</strong>: {saveSummary.primaryFileName}</p>
                </div>

                {visibleFileIndexes.length === 0 ? (
                  <div className="register-empty-media">No warning images.</div>
                ) : (
                  <div className="file-preview-grid">
                    {visibleFileIndexes.map((i) => {
                      const f = previewUrls[i];
                      if (!f) return null;
                      return (
                  <div
                    key={`${f.name}-${i}`}
                    className={`file-preview-card ${i === primaryIndex ? 'is-primary' : ''} ${draggingIndex === i ? 'is-dragging' : ''}`}
                    draggable
                    onDragStart={() => setDraggingIndex(i)}
                    onDragEnd={() => setDraggingIndex(null)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      if (draggingIndex === null) return;
                      moveFile(draggingIndex, i);
                      setDraggingIndex(null);
                    }}
                  >
                    <img src={f.url} alt={f.name} className="file-preview-image" />
                    <div className="file-quality-row">
                      {(fileQualities[i]?.labels ?? []).map((label) => (
                        <span
                          key={`${f.name}-${label}`}
                          className={`file-quality-chip ${fileQualities[i]?.tone === 'warn' ? 'is-warn' : 'is-ok'}`}
                        >
                          {label}
                        </span>
                      ))}
                    </div>
                    <div className="file-preview-meta">
                      <span>{f.name}</span>
                      <div className="file-preview-actions">
                        <button
                          type="button"
                          className="file-open-btn"
                          onClick={() => setPreviewIndex(i)}
                          aria-label="preview-file"
                        >
                          View
                        </button>
                        <button
                          type="button"
                          className="file-crop-btn"
                          onClick={() => void cropCenterSquare(i)}
                          disabled={croppingIndex === i}
                          aria-label="crop-center-file"
                        >
                          {croppingIndex === i ? 'Cropping...' : 'Crop'}
                        </button>
                        <button
                          type="button"
                          className="file-order-btn"
                          onClick={() => moveFile(i, Math.max(0, i - 1))}
                          disabled={i === 0}
                          aria-label="move-file-left"
                        >
                          ←
                        </button>
                        <button
                          type="button"
                          className="file-order-btn"
                          onClick={() => moveFile(i, Math.min(files.length - 1, i + 1))}
                          disabled={i === files.length - 1}
                          aria-label="move-file-right"
                        >
                          →
                        </button>
                        <button
                          type="button"
                          className={`file-primary-btn ${i === primaryIndex ? 'is-active' : ''}`}
                          onClick={() => setPrimaryIndex(i)}
                          aria-label="set-primary-file"
                        >
                          {i === primaryIndex ? 'Primary' : 'Set Primary'}
                        </button>
                        <button
                          type="button"
                          className="file-chip-remove"
                          onClick={() => {
                            setFiles((prev) => prev.filter((_, idx) => idx !== i));
                            setPrimaryIndex((prev) => {
                              if (i === prev) return 0;
                              if (i < prev) return prev - 1;
                              return prev;
                            });
                            setPreviewIndex((prev) => {
                              if (prev === null) return prev;
                              if (i === prev) return null;
                              if (i < prev) return prev - 1;
                              return prev;
                            });
                          }}
                          aria-label="remove-file"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  </div>
                      );
                    })}
                  </div>
                )}
              </>
            ) : (
              <div className="register-empty-media">No images selected yet.</div>
            )}
          </div>

          <div className="register-modal-actions">
            <Button
              className="btn-intent-start"
              onClick={onAdd}
              disabled={loading || !name.trim() || files.length === 0 || (autoExcludeWarnings && savableIndexes.length === 0)}
            >
              {loading ? 'Saving...' : 'Save Item'}
            </Button>
            <Button className="btn-intent-refresh" type="button" variant="outline" onClick={clearDraft}>
              Clear Draft
            </Button>
            <Button className="btn-intent-cancel" type="button" variant="ghost" onClick={() => closeAddModal()}>
              Cancel
            </Button>
          </div>
        </div>
      </Modal>

      <Modal open={cameraModalOpen} onClose={closeCameraModal} title="Take Photo" className="register-camera-modal-shell">
        <div className="camera-capture-wrap">
          <video ref={cameraVideoRef} className="camera-capture-video" playsInline muted />
        </div>
        <div className="capture-settings">
          <Label htmlFor="burst-count">Burst count</Label>
          <select
            id="burst-count"
            className="ui-select"
            value={burstCount}
            onChange={(e) => setBurstCount((Number(e.target.value) === 5 ? 5 : 3) as 3 | 5)}
          >
            <option value={3}>x3</option>
            <option value={5}>x5</option>
          </select>
        </div>
        <div className="btn-row" style={{ marginTop: 12 }}>
          <Button className="w-full btn-intent-start" type="button" onClick={() => void captureFromCamera()}>
            Capture Photo
          </Button>
          <Button
            className="w-full btn-intent-search"
            type="button"
            variant="outline"
            onClick={burstCapture}
            disabled={burstLoading}
          >
            {burstLoading ? 'Capturing...' : `Burst x${burstCount}`}
          </Button>
          <Button className="w-full btn-intent-cancel" type="button" variant="ghost" onClick={closeCameraModal}>
            Close Camera
          </Button>
        </div>
      </Modal>

      <Modal
        open={previewIndex !== null && !!previewUrls[previewIndex]}
        onClose={() => setPreviewIndex(null)}
        title="Image Preview"
        className="register-preview-modal-shell"
      >
        {previewIndex !== null && previewUrls[previewIndex] ? (
          <div className="register-preview-wrap">
            <img
              src={previewUrls[previewIndex].url}
              alt={previewUrls[previewIndex].name}
              className="register-preview-image"
            />
            <div className="register-preview-meta-row">
              <p className="register-preview-name">{previewUrls[previewIndex].name}</p>
              <span className="register-preview-badge">
                {previewIndex === primaryIndex ? 'Primary' : 'Secondary'}
              </span>
            </div>
            <div className="register-preview-actions">
              <Button className="btn-intent-start" onClick={() => setPrimaryIndex(previewIndex)}>
                Set as Primary
              </Button>
              <Button className="btn-intent-preview" variant="outline" onClick={() => void cropCenterSquare(previewIndex)}>
                {croppingIndex === previewIndex ? 'Cropping...' : 'Center Crop'}
              </Button>
              <Button className="btn-intent-cancel" variant="ghost" onClick={() => setPreviewIndex(null)}>
                Close
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      <Modal
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Delete Registered Item"
      >
        <p className="muted" style={{ marginBottom: 12 }}>
          Delete <strong>{deleteTarget ?? ''}</strong>? This action cannot be undone.
        </p>
        <div className="btn-row">
          <Button
            className="w-full btn-intent-delete"
            variant="outline"
            onClick={() => (deleteTarget ? onDelete(deleteTarget) : undefined)}
            disabled={loading || !deleteTarget}
          >
            {loading ? 'Deleting...' : 'Delete'}
          </Button>
          <Button className="w-full btn-intent-cancel" type="button" variant="ghost" onClick={() => setDeleteTarget(null)}>
            Cancel
          </Button>
        </div>
      </Modal>
    </section>
  );
}
