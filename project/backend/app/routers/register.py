import numpy as np
import cv2
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas import RegisteredItem
from app.store import store

router = APIRouter()


@router.get('/items', response_model=list[RegisteredItem])
def list_items() -> list[RegisteredItem]:
    return [RegisteredItem(name=n) for n in store.registered_names()]


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

    store.search.register_from_images(name, imgs)
    return RegisteredItem(name=name)


@router.delete('/items/{name}', response_model=RegisteredItem)
def remove_item(name: str) -> RegisteredItem:
    if name not in store.registered_names():
        raise HTTPException(status_code=404, detail='not found')
    store.search.remove_registered(name)
    return RegisteredItem(name=name)
