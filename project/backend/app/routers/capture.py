from fastapi import APIRouter, Response
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
    cameraId: str | None = None
    cameraSource: str | None = None


@router.post('/start', response_model=CaptureStateResponse)
def capture_start(req: CaptureStartRequest) -> CaptureStateResponse:
    st = store.capture.start(camera_index=req.cameraIndex, camera_id=req.cameraId, camera_source=req.cameraSource)
    return CaptureStateResponse(
        running=st.running,
        cameraIndex=st.camera_index,
        cameraId=st.camera_id,
        cameraSource=st.camera_source,
    )


@router.post('/stop', response_model=CaptureStateResponse)
def capture_stop(cameraId: str = 'ambient_cam_0') -> CaptureStateResponse:
    st = store.capture.stop(camera_id=cameraId)
    return CaptureStateResponse(
        running=st.running,
        cameraIndex=st.camera_index,
        cameraId=st.camera_id,
        cameraSource=st.camera_source,
    )


@router.get('/state', response_model=CaptureStateResponse)
def capture_state(cameraId: str = 'ambient_cam_0') -> CaptureStateResponse:
    st = store.capture.get_state(camera_id=cameraId)
    return CaptureStateResponse(
        running=st.running,
        cameraIndex=st.camera_index,
        cameraId=st.camera_id,
        cameraSource=st.camera_source,
    )


@router.get('/states', response_model=list[CaptureStateResponse])
def capture_states() -> list[CaptureStateResponse]:
    states = store.capture.list_states()
    return [
        CaptureStateResponse(
            running=s.running,
            cameraIndex=s.camera_index,
            cameraId=s.camera_id,
            cameraSource=s.camera_source,
        )
        for s in states
    ]


@router.get('/preview')
def capture_preview(cameraId: str = 'ambient_cam_0') -> Response:
    preview = store.capture.get_preview_path(cameraId)
    if not preview.exists() and cameraId == 'ambient_cam_0':
        preview = store.paths.preview
    if not preview.exists():
        return Response(
            content=_placeholder_jpeg(),
            media_type='image/jpeg',
            headers={'X-Placeholder': '1', 'Cache-Control': 'no-store, max-age=0'},
        )

    frame = cv2.imread(str(preview))
    if frame is None:
        return Response(
            content=_placeholder_jpeg('PREVIEW BUSY'),
            media_type='image/jpeg',
            headers={'X-Placeholder': '1', 'Cache-Control': 'no-store, max-age=0'},
        )

    ok, buf = cv2.imencode('.jpg', frame)
    if not ok:
        return Response(
            content=_placeholder_jpeg('PREVIEW ENCODE FAIL'),
            media_type='image/jpeg',
            headers={'X-Placeholder': '1', 'Cache-Control': 'no-store, max-age=0'},
        )

    return Response(content=buf.tobytes(), media_type='image/jpeg', headers={'Cache-Control': 'no-store, max-age=0'})
