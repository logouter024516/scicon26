from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import os

import cv2
import numpy as np

from app.config import Paths
from app.settings import AppSettings
from app.utils import now_iso, read_json, write_json


@dataclass(slots=True)
class CaptureState:
    running: bool
    camera_index: int
    camera_id: str
    camera_source: str


@dataclass(slots=True)
class _Worker:
    thread: threading.Thread
    stop_event: threading.Event
    camera_id: str
    camera_source: str


class CaptureService:
    def __init__(self, paths: Paths, settings: AppSettings) -> None:
        self.paths = paths
        self.settings = settings
        self._state = CaptureState(running=False, camera_index=0, camera_id='ambient_cam_0', camera_source='0')
        self._lock = threading.Lock()
        self._workers: dict[str, _Worker] = {}

    def _safe_camera_id(self, camera_id: str) -> str:
        return re.sub(r'[^a-zA-Z0-9_-]+', '_', camera_id).strip('_') or 'ambient_cam_0'

    def _preview_path(self, camera_id: str) -> Path:
        safe = self._safe_camera_id(camera_id)
        return self.paths.previews / f'{safe}.jpg'

    def _to_camera_index(self, source: str) -> int:
        s = str(source).strip()
        if s.isdigit() or (s.startswith('-') and s[1:].isdigit()):
            return int(s)
        return -1

    def _resolve_camera(self, camera_index: int | None = None, camera_id: str | None = None, camera_source: str | None = None) -> tuple[str, str, int]:
        default_source = str(self.settings.camera.source)
        default_idx = self._to_camera_index(default_source)
        idx = default_idx if camera_index is None else int(camera_index)
        resolved_id = (camera_id or f'ambient_cam_{idx}').strip() or f'ambient_cam_{idx}'
        resolved_source = (camera_source or (default_source if camera_index is None else str(idx))).strip() or str(idx)
        return resolved_id, resolved_source, self._to_camera_index(resolved_source)

    def get_preview_path(self, camera_id: str = 'ambient_cam_0') -> Path:
        return self._preview_path(camera_id)

    def get_state(self, camera_id: str = 'ambient_cam_0') -> CaptureState:
        with self._lock:
            wk = self._workers.get(camera_id)
            if wk:
                return CaptureState(
                    running=True,
                    camera_index=self._to_camera_index(wk.camera_source),
                    camera_id=wk.camera_id,
                    camera_source=wk.camera_source,
                )
            return CaptureState(running=False, camera_index=0, camera_id=camera_id, camera_source='0')

    def list_states(self) -> list[CaptureState]:
        with self._lock:
            out = [
                CaptureState(
                    running=True,
                    camera_index=self._to_camera_index(w.camera_source),
                    camera_id=w.camera_id,
                    camera_source=w.camera_source,
                )
                for w in self._workers.values()
            ]
        out.sort(key=lambda s: s.camera_id)
        return out

    def _open_capture(self, camera_source: str) -> cv2.VideoCapture:
        src = str(camera_source).strip()
        if src.isdigit() or (src.startswith('-') and src[1:].isdigit()):
            idx = int(src)
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
        return cv2.VideoCapture(src)

    def start(self, camera_index: int = 0, camera_id: str | None = None, camera_source: str | None = None) -> CaptureState:
        cid, csrc, cidx = self._resolve_camera(camera_index=camera_index, camera_id=camera_id, camera_source=camera_source)
        with self._lock:
            if cid in self._workers:
                return CaptureState(running=True, camera_index=cidx, camera_id=cid, camera_source=csrc)

            stop_event = threading.Event()
            thread = threading.Thread(target=self._run, args=(cid, csrc, stop_event), daemon=True)
            self._workers[cid] = _Worker(thread=thread, stop_event=stop_event, camera_id=cid, camera_source=csrc)
            thread.start()
            self._state = CaptureState(running=True, camera_index=cidx, camera_id=cid, camera_source=csrc)
            return CaptureState(running=True, camera_index=cidx, camera_id=cid, camera_source=csrc)

    def stop(self, camera_id: str = 'ambient_cam_0') -> CaptureState:
        with self._lock:
            wk = self._workers.get(camera_id)
            if wk:
                wk.stop_event.set()
                idx = self._to_camera_index(wk.camera_source)
                src = wk.camera_source
            else:
                idx = 0
                src = '0'
        return CaptureState(running=False, camera_index=idx, camera_id=camera_id, camera_source=src)

    def _append_index(self, record: dict) -> None:
        data = read_json(self.paths.index_file, {'clips': []})
        clips = data.get('clips') if isinstance(data, dict) else []
        if not isinstance(clips, list):
            clips = []
        clips.append(record)
        write_json(self.paths.index_file, {'clips': clips})

    def _create_video_writer(self, out: Path, fps: int, size: tuple[int, int]) -> tuple[cv2.VideoWriter, str]:
        # 브라우저 호환성을 위해 H264 계열을 우선 시도하고, 불가 시 mp4v로 fallback
        fourcc_candidates = ['avc1', 'H264', 'X264', 'mp4v']
        for codec in fourcc_candidates:
            writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*codec), fps, size)
            if writer.isOpened():
                return writer, codec
            writer.release()
        raise RuntimeError('video writer open failed for all codecs')

    def _save_clip(self, camera_id: str, frames: list[np.ndarray], fps: int = 15) -> Path | None:
        if not frames:
            return None
        clip_id = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        out = self.paths.clips / f'{clip_id}.mp4'
        h, w = frames[0].shape[:2]
        try:
            writer, codec = self._create_video_writer(out, fps, (w, h))
        except Exception:
            return None
        for fr in frames:
            writer.write(fr)
        writer.release()

        thumb = self.paths.thumbs / f'{clip_id}.jpg'
        cv2.imwrite(str(thumb), frames[len(frames) // 2])

        self._append_index(
            {
                'clip_id': clip_id,
                'event_at': now_iso(),
                'camera_id': camera_id,
                'clip_path': str(out.as_posix()),
                'thumbnail_path': str(thumb.as_posix()),
                'codec': codec,
            }
        )
        return out

    def _run(self, camera_id: str, camera_source: str, stop_event: threading.Event) -> None:
        cap = self._open_capture(camera_source)
        if not cap.isOpened():
            with self._lock:
                self._workers.pop(camera_id, None)
            return

        fps = max(1, int(self.settings.camera.fps))
        pre_buffer = deque(maxlen=fps * int(self.settings.capture.pre_buffer_sec))
        post_frames: list[np.ndarray] = []
        back_sub = cv2.createBackgroundSubtractorMOG2(history=400, varThreshold=28, detectShadows=True)
        event_active = False
        last_motion = 0.0
        cooldown_until = 0.0

        while not stop_event.is_set():
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.04)
                continue

            pre_buffer.append(frame.copy())
            cv2.imwrite(str(self._preview_path(camera_id)), frame)
            cv2.imwrite(str(self.paths.preview), frame)

            fg = back_sub.apply(frame)
            _, fg = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)
            fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            cnts, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            moving = any(cv2.contourArea(c) > float(self.settings.capture.motion_threshold) for c in cnts)

            now = time.time()
            if moving:
                last_motion = now
                if now >= cooldown_until:
                    event_active = True

            if event_active:
                post_frames.append(frame.copy())

            stable_for = now - last_motion
            min_post = max(1, int(fps * float(self.settings.capture.stillness_sec)))
            post_keep = max(1, int(fps * int(self.settings.capture.post_buffer_sec)))
            if event_active and stable_for >= float(self.settings.capture.stillness_sec) and len(post_frames) >= min_post:
                clip_frames = list(pre_buffer) + post_frames[:post_keep]
                self._save_clip(camera_id, clip_frames, fps=fps)
                post_frames = []
                event_active = False
                cooldown_until = now + 4.0

            time.sleep(max(0.0, 1.0 / fps - 0.003))

        cap.release()
        with self._lock:
            self._workers.pop(camera_id, None)
            if not self._workers:
                self._state = CaptureState(running=False, camera_index=0, camera_id='ambient_cam_0', camera_source='0')
