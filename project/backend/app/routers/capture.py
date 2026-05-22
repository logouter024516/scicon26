from fastapi import APIRouter, Response
from pydantic import BaseModel
import cv2
import numpy as np
import platform

from app.schemas import CaptureProbeItem, CaptureStateResponse
from app.store import store

router = APIRouter()


def _placeholder_jpeg(text: str = 'NO PREVIEW') -> bytes:
    canvas = np.zeros((360, 640, 3), dtype=np.uint8)
    canvas[:] = (28, 30, 36)
    cv2.rectangle(canvas, (8, 8), (632, 352), (63, 68, 80), 2)
    cv2.putText(canvas, text, (24, 190), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (206, 212, 223), 2, cv2.LINE_AA)
    ok, buf = cv2.imencode('.jpg', canvas)
    return buf.tobytes() if ok else b''


def _probe_camera(index: int) -> CaptureProbeItem:
    if platform.system() == 'Windows':
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(index, cv2.CAP_MSMF)
    else:
        cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        cap.release()
        return CaptureProbeItem(index=index, ok=False)
    ok = False
    frame = None
    for _ in range(3):
        ok, frame = cap.read()
        if ok and frame is not None:
            break
    cap.release()
    if not ok or frame is None:
        return CaptureProbeItem(index=index, ok=False)

    h, w = frame.shape[:2]
    file_name = f'probe_cam_{index}.jpg'
    out = store.paths.previews / file_name
    try:
        cv2.imwrite(str(out), frame)
    except Exception:
        return CaptureProbeItem(index=index, ok=True, width=w, height=h)
    return CaptureProbeItem(index=index, ok=True, width=w, height=h, previewFile=file_name)


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


@router.get('/probe', response_model=list[CaptureProbeItem])
def capture_probe(maxIndex: int = 4) -> list[CaptureProbeItem]:
    max_idx = max(0, min(12, maxIndex))
    return [_probe_camera(i) for i in range(max_idx + 1)]


@router.get('/probe-preview')
def capture_probe_preview(cameraIndex: int) -> Response:
    file_name = f'probe_cam_{cameraIndex}.jpg'
    preview = store.paths.previews / file_name
    if not preview.exists():
        return Response(
            content=_placeholder_jpeg('NO PROBE FRAME'),
            media_type='image/jpeg',
            headers={'X-Placeholder': '1', 'Cache-Control': 'no-store, max-age=0'},
        )

    frame = cv2.imread(str(preview))
    if frame is None:
        return Response(
            content=_placeholder_jpeg('PROBE BUSY'),
            media_type='image/jpeg',
            headers={'X-Placeholder': '1', 'Cache-Control': 'no-store, max-age=0'},
        )

    ok, buf = cv2.imencode('.jpg', frame)
    if not ok:
        return Response(
            content=_placeholder_jpeg('PROBE ENCODE FAIL'),
            media_type='image/jpeg',
            headers={'X-Placeholder': '1', 'Cache-Control': 'no-store, max-age=0'},
        )

    return Response(content=buf.tobytes(), media_type='image/jpeg', headers={'Cache-Control': 'no-store, max-age=0'})
