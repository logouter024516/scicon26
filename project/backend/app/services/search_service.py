from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import re
import time

import cv2
import numpy as np
from PIL import Image
import platform

try:
    import torch
except Exception:  # pragma: no cover
    torch = None  # type: ignore[assignment]

try:
    from ultralytics import YOLOWorld
except Exception:  # pragma: no cover
    YOLOWorld = None  # type: ignore[assignment]

try:
    from transformers import CLIPModel, CLIPProcessor
except Exception:  # pragma: no cover
    CLIPModel = None  # type: ignore[assignment]
    CLIPProcessor = None  # type: ignore[assignment]

try:
    import clip as openai_clip
except Exception:  # pragma: no cover
    openai_clip = None  # type: ignore[assignment]

from app.config import Paths
from app.settings import AppSettings
from app.utils import read_json, translate_ko_to_en, write_json


@dataclass(slots=True)
class LiveResult:
    found: bool
    score: float
    detail: str
    bbox_norm: tuple[float, float, float, float] | None = None


def _calc_hist(img_bgr: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256])
    hist = cv2.normalize(hist, hist).flatten().astype(np.float32)
    return hist


def _hist_score(a: np.ndarray, b: np.ndarray) -> float:
    corr = float(cv2.compareHist(a, b, cv2.HISTCMP_CORREL))
    return max(0.0, min(1.0, (corr + 1.0) * 0.5))


def _bbox_from_mask(mask: np.ndarray) -> tuple[float, float, float, float] | None:
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    best = max(cnts, key=cv2.contourArea)
    area = cv2.contourArea(best)
    if area < 400:
        return None
    x, y, w, h = cv2.boundingRect(best)
    hh, ww = mask.shape[:2]
    if ww <= 0 or hh <= 0:
        return None
    return (
        float(x) / float(ww),
        float(y) / float(hh),
        float(w) / float(ww),
        float(h) / float(hh),
    )


def _query_color_score(img_bgr: np.ndarray, query: str) -> tuple[float, tuple[float, float, float, float] | None]:
    q = query.lower()
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    ranges = {
        'black': [((0, 0, 0), (180, 255, 55))],
        'white': [((0, 0, 190), (180, 40, 255))],
        'red': [((0, 90, 40), (10, 255, 255)), ((165, 90, 40), (180, 255, 255))],
        'blue': [((90, 80, 40), (130, 255, 255))],
        'green': [((35, 60, 40), (85, 255, 255))],
        'yellow': [((20, 80, 60), (34, 255, 255))],
    }

    best = 0.35
    best_bbox: tuple[float, float, float, float] | None = None
    for name, spans in ranges.items():
        if name in q:
            mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
            for lo, hi in spans:
                mask = cv2.bitwise_or(mask, cv2.inRange(hsv, np.array(lo), np.array(hi)))
            ratio = float(np.count_nonzero(mask)) / float(mask.size)
            score = min(1.0, ratio * 4.0)
            if score >= best:
                best = max(best, score)
                best_bbox = _bbox_from_mask(mask)
    return best, best_bbox


class SearchService:
    def __init__(self, paths: Paths, settings: AppSettings) -> None:
        self.paths = paths
        self.settings = settings
        self._yolo_model: Any | None = None
        self._yolo_ready = False
        self._clip_model: Any | None = None
        self._clip_processor: Any | None = None
        self._clip_ready = False
        self._clip_backend = 'none'
        self._device = 'cuda' if (torch is not None and torch.cuda.is_available()) else 'cpu'
        self._last_yolo_at = 0.0
        self._last_yolo_query = ''
        self._last_yolo_score = 0.0
        self._last_yolo_bbox: tuple[float, float, float, float] | None = None

    def _safe_camera_id(self, camera_id: str) -> str:
        return re.sub(r'[^a-zA-Z0-9_-]+', '_', camera_id).strip('_') or 'ambient_cam_0'

    def _preview_path(self, camera_id: str) -> Path:
        return self.paths.previews / f'{self._safe_camera_id(camera_id)}.jpg'

    def _open_capture(self, source: str) -> cv2.VideoCapture:
        s = str(source).strip()
        if s.isdigit() or (s.startswith('-') and s[1:].isdigit()):
            idx = int(s)
            if platform.system() == 'Windows':
                cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                if cap.isOpened():
                    return cap
                cap.release()
                return cv2.VideoCapture(idx, cv2.CAP_MSMF)
            return cv2.VideoCapture(idx)
        if platform.system() == 'Windows':
            cap = cv2.VideoCapture(s, cv2.CAP_DSHOW)
            if cap.isOpened():
                return cap
            cap.release()
            return cv2.VideoCapture(s, cv2.CAP_MSMF)
        return cv2.VideoCapture(s)

    def _resolve_index_media_path(self, raw_path: str, media_dir: Path) -> tuple[Path, bool]:
        p = Path(str(raw_path or ''))
        if p.exists():
            return p, False

        name = p.name
        if not name:
            return p, False

        fallback = media_dir / name
        if fallback.exists():
            return fallback, True
        return p, False

    def _first_non_empty(self, rec: dict[str, Any], keys: list[str]) -> str:
        for k in keys:
            v = rec.get(k)
            if v is None:
                continue
            s = str(v).strip()
            if s:
                return s
        return ''

    def _iso_from_file_time(self, p: Path) -> str:
        try:
            ts = p.stat().st_mtime
            return datetime.fromtimestamp(ts).isoformat(timespec='seconds')
        except Exception:
            return ''

    def _guess_thumb_path(self, clip_path: Path, clip_id: str) -> Path:
        candidates = [
            self.paths.thumbs / f'{clip_id}.jpg',
            self.paths.thumbs / f'{clip_id}.jpeg',
            self.paths.thumbs / f'{clip_id}.png',
            clip_path.with_suffix('.jpg'),
            clip_path.with_suffix('.jpeg'),
            clip_path.with_suffix('.png'),
        ]
        for c in candidates:
            if c.exists():
                return c
        return self.paths.thumbs / f'{clip_id}.jpg'

    def _normalize_clip_record(self, rec: Any) -> tuple[dict[str, str] | None, bool]:
        if not isinstance(rec, dict):
            return None, False

        changed = False
        clip_raw = self._first_non_empty(rec, ['clip_path', 'clipPath', 'clip_file', 'clipFile'])
        clip_id_raw = self._first_non_empty(rec, ['clip_id', 'clipId'])

        if not clip_raw and clip_id_raw:
            clip_raw = f'{clip_id_raw}.mp4'
            changed = True

        clip_path, migrated = self._resolve_index_media_path(clip_raw, self.paths.clips)
        changed = changed or migrated
        if not clip_path.exists():
            return None, changed

        clip_id = clip_id_raw.strip() or clip_path.stem
        if clip_id != clip_id_raw:
            changed = True

        thumb_raw = self._first_non_empty(
            rec,
            ['thumbnail_path', 'thumbnailPath', 'thumb_path', 'thumbPath', 'thumbnail_file', 'thumbFile'],
        )
        if not thumb_raw:
            thumb_path = self._guess_thumb_path(clip_path, clip_id)
            changed = True
        else:
            thumb_path, thumb_migrated = self._resolve_index_media_path(thumb_raw, self.paths.thumbs)
            changed = changed or thumb_migrated
            if not thumb_path.exists():
                thumb_path = self._guess_thumb_path(clip_path, clip_id)
                changed = True

        event_at = self._first_non_empty(rec, ['event_at', 'eventAt', 'timestamp'])
        if not event_at:
            event_at = self._iso_from_file_time(clip_path)
            changed = True

        camera_id = self._first_non_empty(rec, ['camera_id', 'cameraId', 'camera']) or 'ambient_cam_0'
        if camera_id == 'ambient_cam_0' and self._first_non_empty(rec, ['camera_id', 'cameraId', 'camera']) != camera_id:
            changed = True

        normalized = {
            'clip_id': clip_id,
            'event_at': event_at,
            'camera_id': camera_id,
            'clip_path': str(clip_path.as_posix()),
            'thumbnail_path': str(thumb_path.as_posix()),
        }
        return normalized, changed

    def _load_quick_index_records(self) -> list[dict[str, str]]:
        data = read_json(self.paths.index_file, {'clips': []})
        clips_raw = data.get('clips') if isinstance(data, dict) else []
        if not isinstance(clips_raw, list):
            clips_raw = []

        normalized: list[dict[str, str]] = []
        seen_clip_ids: set[str] = set()
        index_updated = False

        for rec in clips_raw:
            norm, changed = self._normalize_clip_record(rec)
            index_updated = index_updated or changed
            if norm is None:
                continue
            if norm['clip_id'] in seen_clip_ids:
                index_updated = True
                continue
            seen_clip_ids.add(norm['clip_id'])
            normalized.append(norm)

        for p in sorted(self.paths.clips.glob('*')):
            if not p.is_file() or p.suffix.lower() not in {'.mp4', '.avi', '.mov', '.mkv', '.webm'}:
                continue
            clip_id = p.stem
            if clip_id in seen_clip_ids:
                continue
            thumb_path = self._guess_thumb_path(p, clip_id)
            normalized.append(
                {
                    'clip_id': clip_id,
                    'event_at': self._iso_from_file_time(p),
                    'camera_id': 'ambient_cam_0',
                    'clip_path': str(p.as_posix()),
                    'thumbnail_path': str(thumb_path.as_posix()),
                }
            )
            seen_clip_ids.add(clip_id)
            index_updated = True

        if index_updated:
            write_json(self.paths.index_file, {'clips': normalized})

        return normalized

    def _score_single_image(self, img_bgr: np.ndarray, query: str, use_reg: bool, target: np.ndarray | None, clip_text_emb: Any) -> float:
        if use_reg and target is not None:
            return _hist_score(_calc_hist(img_bgr), target)
        if clip_text_emb is not None:
            return self._clip_image_score(img_bgr, clip_text_emb)
        score, _ = _query_color_score(img_bgr, query)
        return score

    def _ensure_yolo(self) -> bool:
        if not bool(self.settings.live_search.enabled):
            self._yolo_ready = True
            self._yolo_model = None
            return False
        if self._yolo_ready:
            return self._yolo_model is not None
        self._yolo_ready = True
        if YOLOWorld is None:
            return False
        try:
            cfg_model = str(self.settings.live_search.model).strip()
            if Path(cfg_model).exists():
                model_path = cfg_model
            else:
                local = Path(__file__).resolve().parents[3] / cfg_model
                model_path = str(local.as_posix()) if local.exists() else cfg_model
            self._yolo_model = YOLOWorld(model_path)
            return True
        except Exception:
            self._yolo_model = None
            return False

    def _ensure_clip(self) -> bool:
        if not bool(self.settings.quick_search.use_clip):
            self._clip_ready = True
            self._clip_model = None
            self._clip_processor = None
            self._clip_backend = 'none'
            return False
        if self._clip_ready:
            return self._clip_model is not None and self._clip_processor is not None
        self._clip_ready = True
        if torch is not None and openai_clip is not None:
            try:
                self._clip_model, self._clip_processor = openai_clip.load('ViT-B/32', device=self._device)
                self._clip_model.eval()
                self._clip_backend = 'openai-clip'
                return True
            except Exception:
                self._clip_model = None
                self._clip_processor = None
        if torch is None or CLIPModel is None or CLIPProcessor is None:
            return False
        try:
            model_name = 'openai/clip-vit-base-patch32'
            self._clip_processor = CLIPProcessor.from_pretrained(model_name)
            self._clip_model = CLIPModel.from_pretrained(model_name).to(self._device)
            self._clip_model.eval()
            self._clip_backend = 'transformers-clip'
            return True
        except Exception:
            self._clip_model = None
            self._clip_processor = None
            return False

    def _yolo_query_score(self, img_bgr: np.ndarray, query: str) -> tuple[float, tuple[float, float, float, float] | None]:
        if not self._ensure_yolo() or self._yolo_model is None:
            return 0.0, None
        try:
            q = query.strip().lower()
            now = time.time()
            interval = max(0.0, float(self.settings.live_search.infer_interval_sec))
            if interval > 0.0 and q == self._last_yolo_query and (now - self._last_yolo_at) < interval:
                return self._last_yolo_score, self._last_yolo_bbox

            max_side = max(128, int(self.settings.live_search.input_max_side))
            h0, w0 = img_bgr.shape[:2]
            frame = img_bgr
            if max(h0, w0) > max_side:
                scale = float(max_side) / float(max(h0, w0))
                nw = max(64, int(round(w0 * scale)))
                nh = max(64, int(round(h0 * scale)))
                frame = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_AREA)

            self._yolo_model.set_classes([query])
            results = self._yolo_model.predict(frame, imgsz=max_side, verbose=False)
            if not results:
                self._last_yolo_at = now
                self._last_yolo_query = q
                self._last_yolo_score = 0.0
                self._last_yolo_bbox = None
                return 0.0, None
            r = results[0]
            boxes = getattr(r, 'boxes', None)
            if boxes is None or len(boxes) == 0:
                self._last_yolo_at = now
                self._last_yolo_query = q
                self._last_yolo_score = 0.0
                self._last_yolo_bbox = None
                return 0.0, None

            confs = boxes.conf.detach().cpu().numpy()
            xyxy = boxes.xyxy.detach().cpu().numpy()
            i = int(np.argmax(confs))
            conf = float(confs[i])
            if conf < float(self.settings.live_search.confidence):
                self._last_yolo_at = now
                self._last_yolo_query = q
                self._last_yolo_score = 0.0
                self._last_yolo_bbox = None
                return 0.0, None
            x1, y1, x2, y2 = xyxy[i].tolist()
            h, w = frame.shape[:2]
            if w <= 0 or h <= 0:
                self._last_yolo_at = now
                self._last_yolo_query = q
                self._last_yolo_score = conf
                self._last_yolo_bbox = None
                return conf, None
            bbox = (
                max(0.0, min(1.0, x1 / w)),
                max(0.0, min(1.0, y1 / h)),
                max(0.0, min(1.0, (x2 - x1) / w)),
                max(0.0, min(1.0, (y2 - y1) / h)),
            )
            self._last_yolo_at = now
            self._last_yolo_query = q
            self._last_yolo_score = conf
            self._last_yolo_bbox = bbox
            return conf, bbox
        except Exception:
            return 0.0, None

    def _clip_text_emb(self, text: str) -> Any | None:
        if not self._ensure_clip() or self._clip_model is None or self._clip_processor is None:
            return None
        if torch is None:
            return None
        if self._clip_backend == 'openai-clip' and openai_clip is not None:
            with torch.no_grad():
                toks = openai_clip.tokenize([text]).to(self._device)
                emb = self._clip_model.encode_text(toks)
                emb = emb / emb.norm(dim=-1, keepdim=True)
                return emb
        with torch.no_grad():
            inputs = self._clip_processor(text=[text], return_tensors='pt', padding=True).to(self._device)
            emb = self._clip_model.get_text_features(**inputs)
            emb = emb / emb.norm(dim=-1, keepdim=True)
            return emb

    def _clip_image_score(self, image_bgr: np.ndarray, text_emb: Any) -> float:
        if self._clip_model is None or self._clip_processor is None:
            return 0.0
        if torch is None:
            return 0.0
        if self._clip_backend == 'openai-clip':
            rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)
            with torch.no_grad():
                x = self._clip_processor(pil).unsqueeze(0).to(self._device)
                img_emb = self._clip_model.encode_image(x)
                img_emb = img_emb / img_emb.norm(dim=-1, keepdim=True)
                sim = float(torch.matmul(img_emb, text_emb.T).squeeze().item())
                return max(0.0, min(1.0, (sim + 1.0) * 0.5))
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        with torch.no_grad():
            inputs = self._clip_processor(images=pil, return_tensors='pt').to(self._device)
            img_emb = self._clip_model.get_image_features(**inputs)
            img_emb = img_emb / img_emb.norm(dim=-1, keepdim=True)
            sim = float(torch.matmul(img_emb, text_emb.T).squeeze().item())
            return max(0.0, min(1.0, (sim + 1.0) * 0.5))

    def _clip_image_scores_batch(self, images_bgr: list[np.ndarray], text_emb: Any) -> list[float]:
        if not images_bgr or self._clip_model is None or self._clip_processor is None or torch is None:
            return [0.0 for _ in images_bgr]

        if self._clip_backend == 'openai-clip':
            pil_images = [Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)) for img in images_bgr]
            with torch.no_grad():
                x = torch.stack([self._clip_processor(pil) for pil in pil_images]).to(self._device)
                img_emb = self._clip_model.encode_image(x)
                img_emb = img_emb / img_emb.norm(dim=-1, keepdim=True)
                sims = torch.matmul(img_emb, text_emb.T).squeeze(-1).detach().cpu().numpy().reshape(-1)
            return [max(0.0, min(1.0, (float(s) + 1.0) * 0.5)) for s in sims.tolist()]

        pil_images = [Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)) for img in images_bgr]
        with torch.no_grad():
            inputs = self._clip_processor(images=pil_images, return_tensors='pt', padding=True).to(self._device)
            img_emb = self._clip_model.get_image_features(**inputs)
            img_emb = img_emb / img_emb.norm(dim=-1, keepdim=True)
            sims = torch.matmul(img_emb, text_emb.T).squeeze(-1).detach().cpu().numpy().reshape(-1)
        return [max(0.0, min(1.0, (float(s) + 1.0) * 0.5)) for s in sims.tolist()]

    def _load_registry(self) -> dict[str, list[float]]:
        data = read_json(self.paths.registry_file, {})
        return data if isinstance(data, dict) else {}

    def _save_registry(self, reg: dict[str, list[float]]) -> None:
        write_json(self.paths.registry_file, reg)

    def list_registered(self) -> list[str]:
        return sorted(self._load_registry().keys())

    def register_from_images(self, name: str, images_bgr: list[np.ndarray]) -> None:
        if not images_bgr:
            raise ValueError('at least one image required')

        hists = [_calc_hist(img) for img in images_bgr]
        mean = np.mean(np.stack(hists), axis=0)
        norm = np.linalg.norm(mean) + 1e-8
        vec = (mean / norm).astype(np.float32)

        reg = self._load_registry()
        reg[name] = vec.tolist()
        self._save_registry(reg)

    def remove_registered(self, name: str) -> None:
        reg = self._load_registry()
        if name in reg:
            del reg[name]
            self._save_registry(reg)

    def _capture_frame(
        self,
        camera_index: int = 0,
        camera_id: str | None = None,
        camera_source: str | None = None,
    ) -> np.ndarray:
        if camera_id:
            p = self._preview_path(camera_id)
            if p.exists():
                fr = cv2.imread(str(p))
                if fr is not None:
                    return fr

        if self.paths.preview.exists():
            fr = cv2.imread(str(self.paths.preview))
            if fr is not None:
                return fr

        source = (camera_source or str(camera_index)).strip()
        cap = self._open_capture(source)
        if not cap.isOpened():
            raise RuntimeError('camera open failed')
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            raise RuntimeError('camera read failed')
        return frame

    def capture_frame(
        self,
        camera_index: int = 0,
        camera_id: str | None = None,
        camera_source: str | None = None,
    ) -> np.ndarray:
        return self._capture_frame(camera_index, camera_id, camera_source)

    def live_search(
        self,
        query: str,
        camera_index: int = 0,
        camera_id: str | None = None,
        camera_source: str | None = None,
    ) -> LiveResult:
        frame = self._capture_frame(camera_index, camera_id, camera_source)
        reg = self._load_registry()
        q = query.strip()
        if q and q not in reg:
            q = translate_ko_to_en(q)

        yolo_score, yolo_bbox = self._yolo_query_score(frame, q)
        if yolo_score >= 0.35:
            return LiveResult(
                found=True,
                score=float(yolo_score),
                detail=f'YOLO-World live detection for "{q}"',
                bbox_norm=yolo_bbox,
            )

        if q in reg:
            target = np.array(reg[q], dtype=np.float32)
            score = _hist_score(_calc_hist(frame), target)
            found = score >= 0.65
            bbox = (0.26, 0.18, 0.48, 0.62) if found else None
            return LiveResult(found=found, score=score, detail=f'registered matching for {q}', bbox_norm=bbox)

        score, bbox = _query_color_score(frame, q)
        found = score >= 0.55
        return LiveResult(found=found, score=score, detail=f'zero-shot heuristic for "{q}"', bbox_norm=bbox if found else None)

    def live_search_on_frame(self, query: str, frame: np.ndarray) -> LiveResult:
        reg = self._load_registry()
        q = query.strip()
        if q and q not in reg:
            q = translate_ko_to_en(q)

        yolo_score, yolo_bbox = self._yolo_query_score(frame, q)
        if yolo_score >= 0.35:
            return LiveResult(
                found=True,
                score=float(yolo_score),
                detail=f'YOLO-World live detection for "{q}" (external frame)',
                bbox_norm=yolo_bbox,
            )

        if q in reg:
            target = np.array(reg[q], dtype=np.float32)
            score = _hist_score(_calc_hist(frame), target)
            found = score >= 0.65
            bbox = (0.26, 0.18, 0.48, 0.62) if found else None
            return LiveResult(found=found, score=score, detail=f'registered matching for {q}', bbox_norm=bbox)

        score, bbox = _query_color_score(frame, q)
        found = score >= 0.55
        return LiveResult(found=found, score=score, detail=f'zero-shot heuristic for "{q}"', bbox_norm=bbox if found else None)

    def quick_search(self, query: str, top_k: int = 5) -> list[dict]:
        clips = self._load_quick_index_records()

        reg = self._load_registry()
        q = query.strip()
        if q and q not in reg:
            q = translate_ko_to_en(q)
        use_reg = q in reg
        target = np.array(reg[q], dtype=np.float32) if use_reg else None
        clip_text_emb = None if (use_reg or not bool(self.settings.quick_search.use_clip)) else self._clip_text_emb(q)
        max_samples_per_clip = max(1, int(self.settings.quick_search.batch_size))
        early_accept_score = 0.86
        thumbnail_only = bool(self.settings.quick_search.thumbnail_only)

        prepared: list[dict[str, Any]] = []
        for rec in clips:
            clip_path_raw = str(rec.get('clip_path', ''))
            clip_path, _ = self._resolve_index_media_path(clip_path_raw, self.paths.clips)
            if not clip_path.exists():
                continue

            thumb_raw = str(rec.get('thumbnail_path', ''))
            thumb_path, _ = self._resolve_index_media_path(thumb_raw, self.paths.thumbs)
            if not thumb_path.exists():
                thumb_path = self._guess_thumb_path(clip_path, str(rec.get('clip_id', '')))

            prepared.append({'rec': rec, 'clip_path': clip_path, 'thumb_path': thumb_path})

        if not prepared:
            return []

        best_scores = [0.0 for _ in prepared]
        scan_indices: set[int] = set(range(len(prepared)))

        if clip_text_emb is not None:
            thumb_images: list[np.ndarray] = []
            thumb_owner_indices: list[int] = []
            for i, p in enumerate(prepared):
                thumb_path = p['thumb_path']
                if isinstance(thumb_path, Path) and thumb_path.exists():
                    thumb = cv2.imread(str(thumb_path))
                    if thumb is not None:
                        thumb_images.append(thumb)
                        thumb_owner_indices.append(i)

            if thumb_images:
                thumb_scores = self._clip_image_scores_batch(thumb_images, clip_text_emb)
                for owner_idx, score in zip(thumb_owner_indices, thumb_scores):
                    if score > best_scores[owner_idx]:
                        best_scores[owner_idx] = float(score)

            refine_count = max(top_k * 2, 4)
            order = sorted(range(len(prepared)), key=lambda i: best_scores[i], reverse=True)
            scan_indices = set(order[: min(len(order), refine_count)])

            if thumbnail_only:
                scan_indices = set()

        out: list[dict] = []
        for i, p in enumerate(prepared):
            rec = p['rec']
            clip_path = p['clip_path']
            thumb_path = p['thumb_path']

            best = float(best_scores[i])
            if clip_text_emb is None and isinstance(thumb_path, Path) and thumb_path.exists():
                thumb = cv2.imread(str(thumb_path))
                if thumb is not None:
                    best = max(best, self._score_single_image(thumb, q, use_reg, target, clip_text_emb))

            cap = cv2.VideoCapture(str(clip_path))
            if cap.isOpened() and best < early_accept_score and i in scan_indices:
                fps = cap.get(cv2.CAP_PROP_FPS)
                if fps <= 0:
                    fps = 24.0
                sample_fps = max(1, int(self.settings.quick_search.sample_fps))
                step = max(1, int(round(float(fps) / float(sample_fps))))

                idx = 0
                sampled = 0
                while True:
                    ok, fr = cap.read()
                    if not ok:
                        break
                    if idx % step == 0:
                        score = self._score_single_image(fr, q, use_reg, target, clip_text_emb)
                        if score > best:
                            best = score
                        sampled += 1
                        if sampled >= max_samples_per_clip:
                            break
                        if best >= 0.96:
                            break
                    idx += 1
            cap.release()

            out.append(
                {
                    'clipId': str(rec.get('clip_id', '')),
                    'score': float(best),
                    'detail': f'clip search score for {query}',
                    'eventAt': str(rec.get('event_at', '')),
                    'cameraId': str(rec.get('camera_id', 'ambient_cam_0')),
                    'clipFile': clip_path.name,
                    'thumbFile': thumb_path.name,
                }
            )

        out.sort(key=lambda x: x['score'], reverse=True)
        return out[: max(1, top_k)]
