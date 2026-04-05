from fastapi import APIRouter, Query, Response
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


@router.post('/search', response_model=LiveSearchResponse)
def live_search(req: LiveSearchRequest) -> LiveSearchResponse:
    q = req.query.strip()
    if not q:
        return LiveSearchResponse(found=False, score=0.0, detail='query is empty')

    try:
        result = store.search.live_search(q, camera_index=req.cameraIndex)
        bbox = list(result.bbox_norm) if result.bbox_norm is not None else None
        return LiveSearchResponse(found=result.found, score=result.score, detail=result.detail, bboxNorm=bbox)
    except Exception as e:
        return LiveSearchResponse(found=False, score=0.0, detail=f'live search failed: {e}')


@router.get('/frame')
def live_frame(cameraIndex: int = Query(default=0)) -> Response:
    try:
        frame = store.search.capture_frame(camera_index=cameraIndex)
    except Exception:
        return Response(content=_placeholder_jpeg(), media_type='image/jpeg', headers={'X-Placeholder': '1'})

    ok, buf = cv2.imencode('.jpg', frame)
    if not ok:
        return Response(content=_placeholder_jpeg('ENCODE FAILED'), media_type='image/jpeg', headers={'X-Placeholder': '1'})
    return Response(content=buf.tobytes(), media_type='image/jpeg')
