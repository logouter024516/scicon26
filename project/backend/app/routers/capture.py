from fastapi import APIRouter, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
import cv2
import numpy as np

from app.schemas import CaptureStateResponse
from app.store import store

router = APIRouter()


def _placeholder_jpeg(text: str = 'NO PREVIEW') -> bytes:
    canvas = np.zeros((360, 640, 3), dtype=np.uint8)
    canvas[:] = (28, 30, 36)
    cv2.rectangle(canvas, (8, 8), (632, 352), (63, 68, 80), 2)
    cv2.putText(canvas, text, (24, 190), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (206, 212, 223), 2, cv2.LINE_AA)
    ok, buf = cv2.imencode('.jpg', canvas)
    return buf.tobytes() if ok else b''


class CaptureStartRequest(BaseModel):
    cameraIndex: int = 0


@router.post('/start', response_model=CaptureStateResponse)
def capture_start(req: CaptureStartRequest) -> CaptureStateResponse:
    st = store.capture.start(req.cameraIndex)
    return CaptureStateResponse(running=st.running, cameraIndex=st.camera_index)


@router.post('/stop', response_model=CaptureStateResponse)
def capture_stop() -> CaptureStateResponse:
    st = store.capture.stop()
    return CaptureStateResponse(running=st.running, cameraIndex=st.camera_index)


@router.get('/state', response_model=CaptureStateResponse)
def capture_state() -> CaptureStateResponse:
    st = store.capture.get_state()
    return CaptureStateResponse(running=st.running, cameraIndex=st.camera_index)


@router.get('/preview')
def capture_preview() -> Response:
    preview = store.paths.preview
    if not preview.exists():
        return Response(content=_placeholder_jpeg(), media_type='image/jpeg', headers={'X-Placeholder': '1'})
    return FileResponse(str(preview), media_type='image/jpeg')
