from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.config import BACKEND_ROOT


@dataclass(slots=True)
class CameraSettings:
    source: str = '0'
    fps: int = 30
    resolution: tuple[int, int] = (1280, 720)


@dataclass(slots=True)
class CaptureSettings:
    pre_buffer_sec: int = 5
    post_buffer_sec: int = 10
    motion_threshold: int = 500
    stillness_sec: float = 3.0


@dataclass(slots=True)
class LiveSearchSettings:
    model: str = 'yolov8s-worldv2.pt'
    confidence: float = 0.35
    device: str = 'auto'


@dataclass(slots=True)
class QuickSearchSettings:
    sample_fps: int = 1
    batch_size: int = 64
    top_k: int = 5
    clip_model: str = 'ViT-B/32'


@dataclass(slots=True)
class AppSettings:
    camera: CameraSettings
    capture: CaptureSettings
    live_search: LiveSearchSettings
    quick_search: QuickSearchSettings


def _to_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _to_float(v: Any, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return default


def load_settings() -> AppSettings:
    cfg_candidates = [
        BACKEND_ROOT / 'config.yaml',
        BACKEND_ROOT.parent / 'config.yaml',
    ]
    data: dict[str, Any] = {}
    for p in cfg_candidates:
        if p.exists():
            try:
                loaded = yaml.safe_load(p.read_text(encoding='utf-8'))
                if isinstance(loaded, dict):
                    data = loaded
                    break
            except Exception:
                pass

    cam = data.get('camera', {}) if isinstance(data.get('camera'), dict) else {}
    cap = data.get('capture', {}) if isinstance(data.get('capture'), dict) else {}
    live = data.get('live_search', {}) if isinstance(data.get('live_search'), dict) else {}
    quick = data.get('quick_search', {}) if isinstance(data.get('quick_search'), dict) else {}

    res = cam.get('resolution', [1280, 720])
    if not (isinstance(res, list) and len(res) == 2):
        res = [1280, 720]

    return AppSettings(
        camera=CameraSettings(
            source=str(cam.get('source', '0')),
            fps=max(1, _to_int(cam.get('fps', 30), 30)),
            resolution=(max(1, _to_int(res[0], 1280)), max(1, _to_int(res[1], 720))),
        ),
        capture=CaptureSettings(
            pre_buffer_sec=max(1, _to_int(cap.get('pre_buffer_sec', 5), 5)),
            post_buffer_sec=max(1, _to_int(cap.get('post_buffer_sec', 10), 10)),
            motion_threshold=max(50, _to_int(cap.get('motion_threshold', 500), 500)),
            stillness_sec=max(0.5, _to_float(cap.get('stillness_sec', 3.0), 3.0)),
        ),
        live_search=LiveSearchSettings(
            model=str(live.get('model', 'yolov8s-worldv2.pt')),
            confidence=max(0.05, min(0.95, _to_float(live.get('confidence', 0.35), 0.35))),
            device=str(live.get('device', 'auto')),
        ),
        quick_search=QuickSearchSettings(
            sample_fps=max(1, _to_int(quick.get('sample_fps', 1), 1)),
            batch_size=max(1, _to_int(quick.get('batch_size', 64), 64)),
            top_k=max(1, _to_int(quick.get('top_k', 5), 5)),
            clip_model=str(quick.get('clip_model', 'ViT-B/32')),
        ),
    )
