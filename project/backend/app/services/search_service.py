from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.config import Paths
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
    def __init__(self, paths: Paths) -> None:
        self.paths = paths

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

    def _capture_frame(self, camera_index: int = 0) -> np.ndarray:
        # 우선 캡처 프리뷰 공유 프레임 사용
        if self.paths.preview.exists():
            fr = cv2.imread(str(self.paths.preview))
            if fr is not None:
                return fr

        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            raise RuntimeError('camera open failed')
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            raise RuntimeError('camera read failed')
        return frame

    def capture_frame(self, camera_index: int = 0) -> np.ndarray:
        return self._capture_frame(camera_index)

    def live_search(self, query: str, camera_index: int = 0) -> LiveResult:
        frame = self._capture_frame(camera_index)
        reg = self._load_registry()
        q = query.strip()

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

        out: list[dict] = []
        for rec in clips:
            clip_path = Path(str(rec.get('clip_path', '')))
            if not clip_path.exists():
                continue

            cap = cv2.VideoCapture(str(clip_path))
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 24.0
            step = max(1, int(round(fps)))

            idx = 0
            best = 0.0
            while True:
                ok, fr = cap.read()
                if not ok:
                    break
                if idx % step == 0:
                    if use_reg and target is not None:
                        score = _hist_score(_calc_hist(fr), target)
                    else:
                        score = _query_color_score(fr, query)
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
