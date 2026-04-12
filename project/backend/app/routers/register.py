import numpy as np
import cv2
import re
from datetime import datetime
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas import RegisteredItem
from app.store import store
from app.utils import now_iso, read_json, write_json

router = APIRouter()


def _meta_load() -> dict[str, dict[str, str]]:
    data = read_json(store.paths.registered_meta_file, {})
    if not isinstance(data, dict):
        return {}

    out: dict[str, dict[str, str]] = {}
    for k, v in data.items():
        name = str(k)
        if isinstance(v, str):
            out[name] = {'thumbFile': v, 'createdAt': ''}
            continue
        if isinstance(v, dict):
            out[name] = {
                'thumbFile': str(v.get('thumbFile', '') or ''),
                'createdAt': str(v.get('createdAt', '') or ''),
            }
            continue
        out[name] = {'thumbFile': '', 'createdAt': ''}
    return out


def _meta_save(meta: dict[str, dict[str, str]]) -> None:
    write_json(store.paths.registered_meta_file, meta)


@router.get('/items', response_model=list[RegisteredItem])
def list_items() -> list[RegisteredItem]:
    meta = _meta_load()
    out: list[RegisteredItem] = []
    for n in store.registered_names():
        rec = meta.get(n, {})
        out.append(
            RegisteredItem(
                name=n,
                thumbFile=str(rec.get('thumbFile', '')),
                createdAt=str(rec.get('createdAt', '')),
            )
        )
    return out


@router.post('/items', response_model=RegisteredItem)
async def add_item(
    name: str = Form(...),
    images: list[UploadFile] = File(default_factory=list),
) -> RegisteredItem:
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail='name required')

    imgs = []
    for f in images:
        raw = await f.read()
        arr = np.frombuffer(raw, dtype=np.uint8)
        im = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if im is not None:
            imgs.append(im)

    if not imgs:
        raise HTTPException(status_code=400, detail='at least one valid image is required')

    # 캡처가 동작 중이면 등록 중에 잠시 중지 후, 완료 시 자동 재시작
    running_states = []
    try:
        running_states = [s for s in store.capture.list_states() if s.running]
    except Exception:
        running_states = []

    for st in running_states:
        try:
            store.capture.stop(camera_id=st.camera_id)
        except Exception:
            pass

    try:
        store.search.register_from_images(name, imgs)

        meta = _meta_load()
        prev_thumb = str(meta.get(name, {}).get('thumbFile', '')).strip()
        if prev_thumb:
            old = store.paths.registered / prev_thumb
            if old.exists():
                try:
                    old.unlink()
                except Exception:
                    pass

        safe_name = re.sub(r'[^A-Za-z0-9_-]+', '_', name).strip('_') or 'item'
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        thumb_name = f'{safe_name}_{stamp}.jpg'
        thumb_path = store.paths.registered / thumb_name
        cv2.imwrite(str(thumb_path), imgs[0])
        meta[name] = {'thumbFile': thumb_name, 'createdAt': now_iso()}
        _meta_save(meta)

        return RegisteredItem(name=name, thumbFile=thumb_name, createdAt=meta[name]['createdAt'])
    finally:
        for st in running_states:
            try:
                store.capture.start(
                    camera_index=st.camera_index,
                    camera_id=st.camera_id,
                    camera_source=st.camera_source,
                )
            except Exception:
                pass


@router.delete('/items/{name}', response_model=RegisteredItem)
def remove_item(name: str) -> RegisteredItem:
    if name not in store.registered_names():
        raise HTTPException(status_code=404, detail='not found')

    meta = _meta_load()
    thumb_name = str(meta.get(name, {}).get('thumbFile', '')).strip()
    if thumb_name:
        thumb_path = store.paths.registered / thumb_name
        if thumb_path.exists():
            try:
                thumb_path.unlink()
            except Exception:
                pass
    if name in meta:
        del meta[name]
        _meta_save(meta)

    store.search.remove_registered(name)
    return RegisteredItem(name=name, thumbFile='', createdAt='')
