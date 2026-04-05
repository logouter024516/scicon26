from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_ROOT / 'data'


@dataclass(slots=True)
class Paths:
    base: Path = DATA_DIR

    @property
    def clips(self) -> Path:
        return self.base / 'clips'

    @property
    def thumbs(self) -> Path:
        return self.base / 'thumbs'

    @property
    def preview(self) -> Path:
        return self.base / 'preview.jpg'

    @property
    def index_file(self) -> Path:
        return self.base / 'index.json'

    @property
    def registry_file(self) -> Path:
        return self.base / 'registry.json'


def ensure_dirs(paths: Paths) -> None:
    paths.base.mkdir(parents=True, exist_ok=True)
    paths.clips.mkdir(parents=True, exist_ok=True)
    paths.thumbs.mkdir(parents=True, exist_ok=True)
