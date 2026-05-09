from __future__ import annotations

from dataclasses import dataclass
import re
import shutil
import subprocess
import threading
import time


@dataclass(slots=True)
class TunnelState:
    running: bool
    public_url: str = ''
    detail: str = ''


class PhoneTunnelService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proc: subprocess.Popen[str] | None = None
        self._public_url = ''
        self._detail = ''

    def _read_until_url(self, proc: subprocess.Popen[str], timeout_sec: float = 12.0) -> str:
        end = time.time() + timeout_sec
        pattern = re.compile(r'https://[a-zA-Z0-9.-]*trycloudflare\.com')
        lines: list[str] = []
        while time.time() < end:
            if proc.poll() is not None:
                break
            line = proc.stdout.readline() if proc.stdout is not None else ''
            if not line:
                time.sleep(0.15)
                continue
            lines.append(line.strip())
            m = pattern.search(line)
            if m:
                return m.group(0)
        self._detail = '\n'.join(lines[-8:])
        return ''

    def start(self, target_url: str) -> TunnelState:
        with self._lock:
            if self._proc is not None and self._proc.poll() is None and self._public_url:
                return TunnelState(running=True, public_url=self._public_url, detail='already running')

            exe = shutil.which('cloudflared')
            if not exe:
                return TunnelState(running=False, public_url='', detail='cloudflared not installed')

            self.stop()
            self._detail = ''
            self._public_url = ''
            self._proc = subprocess.Popen(
                [exe, 'tunnel', '--url', target_url],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='ignore',
            )

            url = self._read_until_url(self._proc)
            if not url:
                self.stop()
                return TunnelState(running=False, public_url='', detail=self._detail or 'failed to open tunnel')

            self._public_url = url
            return TunnelState(running=True, public_url=url, detail='ok')

    def status(self) -> TunnelState:
        with self._lock:
            running = self._proc is not None and self._proc.poll() is None
            return TunnelState(running=bool(running), public_url=self._public_url if running else '', detail=self._detail)

    def stop(self) -> TunnelState:
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                try:
                    self._proc.terminate()
                    self._proc.wait(timeout=3)
                except Exception:
                    try:
                        self._proc.kill()
                    except Exception:
                        pass
            self._proc = None
            self._public_url = ''
            return TunnelState(running=False, public_url='', detail='stopped')
