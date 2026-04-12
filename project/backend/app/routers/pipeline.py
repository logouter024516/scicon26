from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas import LiveSearchResponse, PipelineFindResponse, SearchResultItem
from app.store import store

router = APIRouter()


class PipelineFindRequest(BaseModel):
    query: str
    cameraIndex: int = 0
    cameraId: str | None = None
    cameraSource: str | None = None
    topK: int = 5


@router.post('/find', response_model=PipelineFindResponse)
def find_item(req: PipelineFindRequest) -> PipelineFindResponse:
    query = req.query.strip()
    if not query:
        return PipelineFindResponse(
            stage='none',
            found=False,
            message='query is empty',
            live=LiveSearchResponse(found=False, score=0.0, detail='query is empty'),
            quick=[],
        )

    try:
        live_result = store.search.live_search(
            query,
            camera_index=req.cameraIndex,
            camera_id=req.cameraId,
            camera_source=req.cameraSource,
        )
        live = LiveSearchResponse(found=live_result.found, score=live_result.score, detail=live_result.detail)
        live_found = bool(live_result.found)
    except Exception as e:
        live = LiveSearchResponse(found=False, score=0.0, detail=f'live search failed: {e}')
        live_found = False

    if live_found:
        return PipelineFindResponse(
            stage='live',
            found=True,
            message='Found in Stage 1 Live Search',
            live=live,
            quick=[],
        )

    quick_hits_raw = store.search.quick_search(query, top_k=max(1, req.topK))
    quick_hits = [SearchResultItem(**h) for h in quick_hits_raw]

    found_quick = len(quick_hits) > 0 and quick_hits[0].score >= 0.55
    return PipelineFindResponse(
        stage='quick',
        found=found_quick,
        message='Stage 1 failed. Stage 2 Quick Search completed.',
        live=live,
        quick=quick_hits,
    )
