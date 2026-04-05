from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from app.config import Paths
from app.utils import now_iso, read_json, write_json


@dataclass(slots=True)
class CaptureState:
    running: bool
    camera_index: int


class CaptureService:
    def __init__(self, paths: Paths) -> None:
        self.paths = paths
        self._state = CaptureState(running=False, camera_index=0)
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def get_state(self) -> CaptureState:
        with self._lock:
            return CaptureState(self._state.running, self._state.camera_index)

    def start(self, camera_index: int) -> CaptureState:
        with self._lock:
            if self._state.running:
                return CaptureState(True, self._state.camera_index)
            self._state.running = True
            self._state.camera_index = camera_index
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, args=(camera_index,), daemon=True)
            self._thread.start()
            return CaptureState(True, camera_index)

    def stop(self) -> CaptureState:
        with self._lock:
            self._stop_event.set()
            self._state.running = False
            idx = self._state.camera_index
        return CaptureState(False, idx)

    def _append_index(self, record: dict) -> None:
        data = read_json(self.paths.index_file, {'clips': []})
        clips = data.get('clips') if isinstance(data, dict) else []
        if not isinstance(clips, list):
            clips = []
        clips.append(record)
        write_json(self.paths.index_file, {'clips': clips})

    def _save_clip(self, frames: list[np.ndarray], fps: int = 15) -> Path | None:
        if not frames:
            return None
        clip_id = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        out = self.paths.clips / f'{clip_id}.mp4'
        h, w = frames[0].shape[:2]
        writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
        for fr in frames:
            writer.write(fr)
        writer.release()

        thumb = self.paths.thumbs / f'{clip_id}.jpg'
        cv2.imwrite(str(thumb), frames[len(frames) // 2])

        self._append_index(
            {
                'clip_id': clip_id,
                'event_at': now_iso(),
                'camera_id': f'ambient_cam_{self._state.camera_index}',
                'clip_path': str(out.as_posix()),
                'thumbnail_path': str(thumb.as_posix()),
            }
        )
        return out

    def _run(self, camera_index: int) -> None:
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            with self._lock:
                self._state.running = False
            return

        fps = 15
        pre_buffer = deque(maxlen=fps * 4)
        post_frames: list[np.ndarray] = []
        back_sub = cv2.createBackgroundSubtractorMOG2(history=400, varThreshold=28, detectShadows=True)
        event_active = False
        last_motion = 0.0
        cooldown_until = 0.0

        while not self._stop_event.is_set():
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.04)
                continue

            pre_buffer.append(frame.copy())
            cv2.imwrite(str(self.paths.preview), frame)

            fg = back_sub.apply(frame)
            _, fg = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)
            fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            cnts, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            moving = any(cv2.contourArea(c) > 1200 for c in cnts)

            now = time.time()
            if moving:
                last_motion = now
                if now >= cooldown_until:
                    event_active = True

            if event_active:
                post_frames.append(frame.copy())

            stable_for = now - last_motion
            if event_active and stable_for >= 2.0 and len(post_frames) >= fps * 2:
                clip_frames = list(pre_buffer) + post_frames[: fps * 3]
                self._save_clip(clip_frames, fps=fps)
                post_frames = []
                event_active = False
                cooldown_until = now + 4.0

            time.sleep(max(0.0, 1.0 / fps - 0.003))

        cap.release()
        with self._lock:
            self._state.running = False
