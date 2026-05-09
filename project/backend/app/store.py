from dataclasses import dataclass

from app.config import Paths, ensure_dirs
from app.settings import AppSettings, load_settings
from app.services.capture_service import CaptureService
from app.services.phone_stream_service import PhoneStreamService
from app.services.phone_tunnel_service import PhoneTunnelService
from app.services.search_service import SearchService
from app.utils import read_json


@dataclass(slots=True)
class AppStore:
    paths: Paths
    settings: AppSettings
    capture: CaptureService
    search: SearchService
    phone: PhoneStreamService
    tunnel: PhoneTunnelService

    def total_clips(self) -> int:
        data = read_json(self.paths.index_file, {'clips': []})
        clips = data.get('clips') if isinstance(data, dict) else []
        return len(clips) if isinstance(clips, list) else 0

    def registered_names(self) -> list[str]:
        return self.search.list_registered()


_paths = Paths()
ensure_dirs(_paths)
_settings = load_settings()

store = AppStore(
    paths=_paths,
    settings=_settings,
    capture=CaptureService(_paths, _settings),
    search=SearchService(_paths, _settings),
    phone=PhoneStreamService(),
    tunnel=PhoneTunnelService(),
)
