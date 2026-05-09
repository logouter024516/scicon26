from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
import uuid

import cv2
import numpy as np


@dataclass(slots=True)
class PhoneSession:
    session_id: str
    created_at: datetime
    updated_at: datetime
    frame_jpeg: bytes | None = None


class PhoneStreamService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, PhoneSession] = {}
        self._ttl = timedelta(hours=2)

    def _cleanup(self) -> None:
        now = datetime.now()
        expired = [k for k, v in self._sessions.items() if now - v.updated_at > self._ttl]
        for k in expired:
            self._sessions.pop(k, None)

    def create_session(self) -> str:
        sid = uuid.uuid4().hex[:12]
        now = datetime.now()
        with self._lock:
            self._cleanup()
            self._sessions[sid] = PhoneSession(session_id=sid, created_at=now, updated_at=now)
        return sid

    def has_session(self, session_id: str) -> bool:
        with self._lock:
            self._cleanup()
            return session_id in self._sessions

    def push_frame(self, session_id: str, frame_jpeg: bytes) -> bool:
        with self._lock:
            self._cleanup()
            rec = self._sessions.get(session_id)
            if rec is None:
                return False
            rec.frame_jpeg = frame_jpeg
            rec.updated_at = datetime.now()
            return True

    def get_frame_jpeg(self, session_id: str) -> bytes | None:
        with self._lock:
            self._cleanup()
            rec = self._sessions.get(session_id)
            if rec is None:
                return None
            rec.updated_at = datetime.now()
            return rec.frame_jpeg

    def get_frame_bgr(self, session_id: str) -> np.ndarray | None:
        buf = self.get_frame_jpeg(session_id)
        if not buf:
            return None
        arr = np.frombuffer(buf, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return frame
