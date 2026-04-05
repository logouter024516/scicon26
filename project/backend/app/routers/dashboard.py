from fastapi import APIRouter
from pathlib import Path

from app.schemas import ClipItem, SummaryResponse
from app.store import store
from app.utils import read_json

router = APIRouter()


@router.get('/summary', response_model=SummaryResponse)
def summary() -> SummaryResponse:
    cap = store.capture.get_state()
    return SummaryResponse(
        captureStatus='Running' if cap.running else 'Stopped',
        totalClips=store.total_clips(),
        addedItems=len(store.registered_names()),
    )


@router.get('/clips/recent', response_model=list[ClipItem])
def recent_clips() -> list[ClipItem]:
    data = read_json(store.paths.index_file, {'clips': []})
    clips = data.get('clips') if isinstance(data, dict) else []
    if not isinstance(clips, list):
        return []

    recent = list(reversed(clips[-10:]))
    out: list[ClipItem] = []
    for c in recent:
        out.append(
            ClipItem(
                clipId=str(c.get('clip_id', '')),
                eventAt=str(c.get('event_at', '')),
                cameraId=str(c.get('camera_id', 'ambient_cam_0')),
                clipFile=Path(str(c.get('clip_path', ''))).name,
                thumbFile=Path(str(c.get('thumbnail_path', ''))).name,
            )
        )
    return out
