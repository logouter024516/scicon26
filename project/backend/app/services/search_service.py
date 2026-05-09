from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import re
import os

import cv2
import numpy as np
from PIL import Image

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
from app.utils import read_json, write_json


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

    def _safe_camera_id(self, camera_id: str) -> str:
        return re.sub(r'[^a-zA-Z0-9_-]+', '_', camera_id).strip('_') or 'ambient_cam_0'

    def _preview_path(self, camera_id: str) -> Path:
        return self.paths.previews / f'{self._safe_camera_id(camera_id)}.jpg'

    def _open_capture(self, source: str) -> cv2.VideoCapture:
        s = str(source).strip()
        if s.isdigit() or (s.startswith('-') and s[1:].isdigit()):
            idx = int(s)
            if os.name == 'nt':
                cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                if cap.isOpened():
                    return cap
                cap.release()
                cap = cv2.VideoCapture(idx, cv2.CAP_MSMF)
                if cap.isOpened():
                    return cap
                cap.release()
            return cv2.VideoCapture(idx)
        return cv2.VideoCapture(s)

    def _ensure_yolo(self) -> bool:
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
            self._yolo_model.set_classes([query])
            results = self._yolo_model.predict(img_bgr, verbose=False)
            if not results:
                return 0.0, None
            r = results[0]
            boxes = getattr(r, 'boxes', None)
            if boxes is None or len(boxes) == 0:
                return 0.0, None

            confs = boxes.conf.detach().cpu().numpy()
            xyxy = boxes.xyxy.detach().cpu().numpy()
            i = int(np.argmax(confs))
            conf = float(confs[i])
            if conf < float(self.settings.live_search.confidence):
                return 0.0, None
            x1, y1, x2, y2 = xyxy[i].tolist()
            h, w = img_bgr.shape[:2]
            if w <= 0 or h <= 0:
                return conf, None
            bbox = (
                max(0.0, min(1.0, x1 / w)),
                max(0.0, min(1.0, y1 / h)),
                max(0.0, min(1.0, (x2 - x1) / w)),
                max(0.0, min(1.0, (y2 - y1) / h)),
            )
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

    def _resolve_clip_path(self, rec: dict[str, Any]) -> Path | None:
        raw = Path(str(rec.get('clip_path', '')))
        if raw.exists():
            return raw

        # index.json 경로가 예전 작업 디렉터리를 가리킬 수 있으므로
        # 현재 data/clips 기준으로 파일명을 재해석한다.
        name = raw.name
        if name:
            local = self.paths.clips / name
            if local.exists():
                return local

        clip_id = str(rec.get('clip_id', '')).strip()
        if clip_id:
            local_by_id = self.paths.clips / f'{clip_id}.mp4'
            if local_by_id.exists():
                return local_by_id

        return None

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
        data = read_json(self.paths.index_file, {'clips': []})
        clips = data.get('clips') if isinstance(data, dict) else []
        if not isinstance(clips, list):
            clips = []

        reg = self._load_registry()
        use_reg = query.strip() in reg
        target = np.array(reg[query.strip()], dtype=np.float32) if use_reg else None
        clip_text_emb = None if use_reg else self._clip_text_emb(query.strip())

        out: list[dict] = []
        for rec in clips:
            clip_path = self._resolve_clip_path(rec)
            if clip_path is None:
                continue

            cap = cv2.VideoCapture(str(clip_path))
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 24.0
            sample_fps = max(1, int(self.settings.quick_search.sample_fps))
            step = max(1, int(round(float(fps) / float(sample_fps))))

            idx = 0
            best = 0.0
            while True:
                ok, fr = cap.read()
                if not ok:
                    break
                if idx % step == 0:
                    if use_reg and target is not None:
                        score = _hist_score(_calc_hist(fr), target)
                    elif clip_text_emb is not None:
                        score = self._clip_image_score(fr, clip_text_emb)
                    else:
                        score, _ = _query_color_score(fr, query)
                    if score > best:
                        best = score
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
                    'thumbFile': Path(str(rec.get('thumbnail_path', ''))).name,
                }
            )

        out.sort(key=lambda x: x['score'], reverse=True)
        return out[: max(1, top_k)]
