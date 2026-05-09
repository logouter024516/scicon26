from __future__ import annotations

import cv2
import numpy as np
import socket
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.store import store

router = APIRouter()


def _placeholder_jpeg(text: str = 'NO PHONE FRAME') -> bytes:
    canvas = np.zeros((360, 640, 3), dtype=np.uint8)
    canvas[:] = (30, 32, 38)
    cv2.rectangle(canvas, (8, 8), (632, 352), (66, 71, 84), 2)
    cv2.putText(canvas, text, (24, 190), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (210, 214, 225), 2, cv2.LINE_AA)
    ok, buf = cv2.imencode('.jpg', canvas)
    return buf.tobytes() if ok else b''


@router.post('/sessions')
def create_phone_session():
    sid = store.phone.create_session()
    return {'sessionId': sid}


@router.get('/network')
def phone_network_info():
    hosts: list[str] = []
    try:
        hostname = socket.gethostname()
        _, _, ips = socket.gethostbyname_ex(hostname)
        for ip in ips:
            if ip and not ip.startswith('127.') and ip not in hosts:
                hosts.append(ip)
    except Exception:
        pass
    return {'hosts': hosts}


@router.post('/tunnel/start')
def start_phone_tunnel(targetUrl: str = Form(default='http://127.0.0.1:5174')):
    st = store.tunnel.start(targetUrl)
    return {'running': st.running, 'publicUrl': st.public_url, 'detail': st.detail}


@router.get('/tunnel/status')
def phone_tunnel_status():
    st = store.tunnel.status()
    return {'running': st.running, 'publicUrl': st.public_url, 'detail': st.detail}


@router.post('/tunnel/stop')
def stop_phone_tunnel():
    st = store.tunnel.stop()
    return {'running': st.running, 'publicUrl': st.public_url, 'detail': st.detail}


@router.post('/sessions/{session_id}/frame')
async def upload_phone_frame(session_id: str, image: UploadFile = File(...), ts: str | None = Form(default=None)):
    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=400, detail='image required')
    ok = store.phone.push_frame(session_id, raw)
    if not ok:
        raise HTTPException(status_code=404, detail='session not found')
    return {'ok': True, 'sessionId': session_id, 'ts': ts or ''}


@router.get('/sessions/{session_id}/exists')
def phone_session_exists(session_id: str):
    return {'ok': store.phone.has_session(session_id), 'sessionId': session_id}


@router.get('/sessions/{session_id}/frame')
def get_phone_frame(session_id: str):
    raw = store.phone.get_frame_jpeg(session_id)
    if not raw:
        return Response(content=_placeholder_jpeg(), media_type='image/jpeg', headers={'X-Placeholder': '1', 'Cache-Control': 'no-store, max-age=0'})
    return Response(content=raw, media_type='image/jpeg', headers={'Cache-Control': 'no-store, max-age=0'})
