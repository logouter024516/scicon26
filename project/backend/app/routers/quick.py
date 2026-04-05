from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas import SearchResultItem
from app.store import store

router = APIRouter()


class QuickSearchRequest(BaseModel):
    query: str
    topK: int = 5


@router.post('/search', response_model=list[SearchResultItem])
def quick_search(req: QuickSearchRequest) -> list[SearchResultItem]:
    if not req.query.strip():
        return []
    hits = store.search.quick_search(req.query.strip(), top_k=req.topK)
    return [SearchResultItem(**h) for h in hits]
