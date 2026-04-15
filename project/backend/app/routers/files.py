from pathlib import Path
import time

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse

from app.store import store
from app.utils import read_json, write_json

router = APIRouter()


def _safe_name(name: str) -> str:
    p = Path(name)
    if p.name != name or name in ('', '.', '..'):
        raise HTTPException(status_code=400, detail='invalid filename')
    return name


def _resolve_index_media_path(raw_path: str, media_dir: Path) -> tuple[Path, bool]:
    p = Path(str(raw_path or ''))
    if p.exists():
        return p, False

    name = p.name
    if not name:
        return p, False

    fallback = media_dir / name
    if fallback.exists():
        return fallback, True
    return p, False


def _try_rebuild_thumb(name: str) -> bool:
    data = read_json(store.paths.index_file, {'clips': []})
    clips = data.get('clips') if isinstance(data, dict) else []
    if not isinstance(clips, list):
        return False

    target = None
    for rec in clips:
        thumb_path = Path(str(rec.get('thumbnail_path', '')))
        if thumb_path.name == name:
            target = rec
            break

    if target is None:
        return False

    clip_path, clip_migrated = _resolve_index_media_path(str(target.get('clip_path', '')), store.paths.clips)
    thumb_path, thumb_migrated = _resolve_index_media_path(str(target.get('thumbnail_path', '')), store.paths.thumbs)
    if clip_migrated:
        target['clip_path'] = str(clip_path.as_posix())
    if thumb_migrated:
        target['thumbnail_path'] = str(thumb_path.as_posix())
    if (clip_migrated or thumb_migrated) and isinstance(data, dict):
        write_json(store.paths.index_file, data)

    if not clip_path.exists():
        return False

    cap = cv2.VideoCapture(str(clip_path))
    if not cap.isOpened():
        return False

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count // 2)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        return False

    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    return bool(cv2.imwrite(str(thumb_path), frame))


def _placeholder_jpeg(text: str = 'NO THUMBNAIL') -> bytes:
    canvas = np.zeros((360, 640, 3), dtype=np.uint8)
    canvas[:] = (30, 32, 38)
    cv2.rectangle(canvas, (8, 8), (632, 352), (66, 71, 84), 2)
    cv2.putText(canvas, text, (24, 190), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (210, 214, 225), 2, cv2.LINE_AA)
    ok, buf = cv2.imencode('.jpg', canvas)
    return buf.tobytes() if ok else b''


@router.get('/clips/{name}')
def get_clip(name: str):
    safe = _safe_name(name)
    path = store.paths.clips / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail='clip not found')
    return FileResponse(
        str(path),
        media_type='video/mp4',
        filename=safe,
        headers={
            'Content-Disposition': f'inline; filename="{safe}"',
            'Accept-Ranges': 'bytes',
        },
    )


@router.get('/clips-mjpeg/{name}')
def get_clip_mjpeg(name: str, fps: int = 12):
    safe = _safe_name(name)
    path = store.paths.clips / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail='clip not found')

    fps = max(1, min(int(fps), 30))

    def gen():
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return
        delay = 1.0 / float(fps)
        try:
            while True:
                ok, frame = cap.read()
                if not ok or frame is None:
                    break
                ok_jpg, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                if not ok_jpg:
                    continue
                yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n'
                time.sleep(delay)
        finally:
            cap.release()

    return StreamingResponse(
        gen(),
        media_type='multipart/x-mixed-replace; boundary=frame',
        headers={'Cache-Control': 'no-store, max-age=0'},
    )


@router.get('/thumbs/{name}')
def get_thumb(name: str):
    safe = _safe_name(name)
    path = store.paths.thumbs / safe
    if not path.exists():
        rebuilt = _try_rebuild_thumb(safe)
        if not rebuilt or not path.exists():
            return Response(content=_placeholder_jpeg(), media_type='image/jpeg', headers={'X-Placeholder': '1'})
    return FileResponse(str(path), media_type='image/jpeg')


@router.get('/registered/{name}')
def get_registered_image(name: str):
    safe = _safe_name(name)
    path = store.paths.registered / safe
    if not path.exists():
        return Response(content=_placeholder_jpeg('NO IMAGE'), media_type='image/jpeg', headers={'X-Placeholder': '1'})
    return FileResponse(str(path), media_type='image/jpeg')


@router.delete('/clips/by-id/{clip_id}')
def delete_clip_by_id(clip_id: str):
    clip_id = clip_id.strip()
    if not clip_id:
        raise HTTPException(status_code=400, detail='clip id required')

    data = read_json(store.paths.index_file, {'clips': []})
    clips = data.get('clips') if isinstance(data, dict) else []
    if not isinstance(clips, list):
        clips = []

    target = None
    remain = []
    for rec in clips:
        if str(rec.get('clip_id', '')) == clip_id and target is None:
            target = rec
            continue
        remain.append(rec)

    if target is None:
        raise HTTPException(status_code=404, detail='clip not found')

    clip_path, clip_migrated = _resolve_index_media_path(str(target.get('clip_path', '')), store.paths.clips)
    thumb_path, thumb_migrated = _resolve_index_media_path(str(target.get('thumbnail_path', '')), store.paths.thumbs)
    if clip_migrated:
        target['clip_path'] = str(clip_path.as_posix())
    if thumb_migrated:
        target['thumbnail_path'] = str(thumb_path.as_posix())

    for p in (clip_path, thumb_path):
        try:
            if p.exists():
                p.unlink()
        except Exception:
            raise HTTPException(status_code=409, detail='file is in use; stop capture and retry')

    write_json(store.paths.index_file, {'clips': remain})
    return {'ok': True, 'clipId': clip_id}
