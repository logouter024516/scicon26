from dataclasses import dataclass

from app.config import Paths, ensure_dirs
from app.services.capture_service import CaptureService
from app.services.search_service import SearchService
from app.utils import read_json


@dataclass(slots=True)
class AppStore:
    paths: Paths
    capture: CaptureService
    search: SearchService

    def total_clips(self) -> int:
        data = read_json(self.paths.index_file, {'clips': []})
        clips = data.get('clips') if isinstance(data, dict) else []
        return len(clips) if isinstance(clips, list) else 0

    def registered_names(self) -> list[str]:
        return self.search.list_registered()


_paths = Paths()
ensure_dirs(_paths)

store = AppStore(
    paths=_paths,
    capture=CaptureService(_paths),
    search=SearchService(_paths),
)
