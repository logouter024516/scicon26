from fastapi import APIRouter, File, Form, Query, Response, UploadFile
from pydantic import BaseModel
import cv2
import numpy as np

from app.schemas import LiveSearchResponse
from app.store import store

router = APIRouter()


def _placeholder_jpeg(text: str = 'NO LIVE FRAME') -> bytes:
    canvas = np.zeros((360, 640, 3), dtype=np.uint8)
    canvas[:] = (28, 30, 36)
    cv2.rectangle(canvas, (8, 8), (632, 352), (63, 68, 80), 2)
    cv2.putText(canvas, text, (24, 190), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (206, 212, 223), 2, cv2.LINE_AA)
    ok, buf = cv2.imencode('.jpg', canvas)
    return buf.tobytes() if ok else b''


class LiveSearchRequest(BaseModel):
    query: str
    cameraIndex: int = 0
    cameraId: str | None = None
    cameraSource: str | None = None


@router.post('/search', response_model=LiveSearchResponse)
def live_search(req: LiveSearchRequest) -> LiveSearchResponse:
    q = req.query.strip()
    if not q:
        return LiveSearchResponse(found=False, score=0.0, detail='query is empty')

    try:
        result = store.search.live_search(
            q,
            camera_index=req.cameraIndex,
            camera_id=req.cameraId,
            camera_source=req.cameraSource,
        )
        bbox = list(result.bbox_norm) if result.bbox_norm is not None else None
        return LiveSearchResponse(found=result.found, score=result.score, detail=result.detail, bboxNorm=bbox)
    except Exception as e:
        return LiveSearchResponse(found=False, score=0.0, detail=f'live search failed: {e}')


@router.post('/search-image', response_model=LiveSearchResponse)
async def live_search_image(
    query: str = Form(...),
    image: UploadFile = File(...),
) -> LiveSearchResponse:
    q = query.strip()
    if not q:
        return LiveSearchResponse(found=False, score=0.0, detail='query is empty')

    try:
        raw = await image.read()
        arr = np.frombuffer(raw, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return LiveSearchResponse(found=False, score=0.0, detail='invalid image frame')

        result = store.search.live_search_on_frame(q, frame)
        bbox = list(result.bbox_norm) if result.bbox_norm is not None else None
        return LiveSearchResponse(found=result.found, score=result.score, detail=result.detail, bboxNorm=bbox)
    except Exception as e:
        return LiveSearchResponse(found=False, score=0.0, detail=f'live image search failed: {e}')


@router.post('/search-unified', response_model=LiveSearchResponse)
async def live_search_unified(
    query: str = Form(...),
    image: UploadFile | None = File(default=None),
    phoneSessionId: str | None = Form(default=None),
    cameraIndex: int = Form(default=0),
    cameraId: str | None = Form(default=None),
    cameraSource: str | None = Form(default=None),
) -> LiveSearchResponse:
    q = query.strip()
    if not q:
        return LiveSearchResponse(found=False, score=0.0, detail='query is empty')

    try:
        if image is not None:
            raw = await image.read()
            arr = np.frombuffer(raw, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                return LiveSearchResponse(found=False, score=0.0, detail='invalid image frame')
            result = store.search.live_search_on_frame(q, frame)
        elif phoneSessionId:
            frame = store.phone.get_frame_bgr(phoneSessionId)
            if frame is None:
                return LiveSearchResponse(found=False, score=0.0, detail='phone frame not ready')
            result = store.search.live_search_on_frame(q, frame)
        else:
            result = store.search.live_search(
                q,
                camera_index=cameraIndex,
                camera_id=cameraId,
                camera_source=cameraSource,
            )

        bbox = list(result.bbox_norm) if result.bbox_norm is not None else None
        return LiveSearchResponse(found=result.found, score=result.score, detail=result.detail, bboxNorm=bbox)
    except Exception as e:
        return LiveSearchResponse(found=False, score=0.0, detail=f'live unified search failed: {e}')


@router.get('/frame')
def live_frame(
    cameraIndex: int = Query(default=0),
    cameraId: str | None = Query(default=None),
    cameraSource: str | None = Query(default=None),
) -> Response:
    frame = None
    resolved_camera_id = (cameraId or f'ambient_cam_{cameraIndex}').strip() or f'ambient_cam_{cameraIndex}'

    st = store.capture.get_state(camera_id=resolved_camera_id)
    if st.running:
        p = store.capture.get_preview_path(resolved_camera_id)
        if not p.exists() and resolved_camera_id == 'ambient_cam_0':
            p = store.paths.preview
        if p.exists():
            frame = cv2.imread(str(p))

    if frame is None:
        try:
            frame = store.search.capture_frame(camera_index=cameraIndex, camera_id=cameraId, camera_source=cameraSource)
        except Exception:
            return Response(
                content=_placeholder_jpeg(),
                media_type='image/jpeg',
                headers={'X-Placeholder': '1', 'Cache-Control': 'no-store, max-age=0'},
            )

    if frame is None:
        return Response(
            content=_placeholder_jpeg(),
            media_type='image/jpeg',
            headers={'X-Placeholder': '1', 'Cache-Control': 'no-store, max-age=0'},
        )

    ok, buf = cv2.imencode('.jpg', frame)
    if not ok:
        return Response(
            content=_placeholder_jpeg('ENCODE FAILED'),
            media_type='image/jpeg',
            headers={'X-Placeholder': '1', 'Cache-Control': 'no-store, max-age=0'},
        )
    return Response(content=buf.tobytes(), media_type='image/jpeg', headers={'Cache-Control': 'no-store, max-age=0'})
