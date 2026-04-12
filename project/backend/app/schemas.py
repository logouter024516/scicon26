from pydantic import BaseModel


class HealthResponse(BaseModel):
    ok: bool
    message: str


class SummaryResponse(BaseModel):
    captureStatus: str
    totalClips: int
    addedItems: int


class ClipItem(BaseModel):
    clipId: str
    eventAt: str
    cameraId: str
    clipFile: str = ''
    thumbFile: str = ''


class CaptureStateResponse(BaseModel):
    running: bool
    cameraIndex: int
    cameraId: str = ''
    cameraSource: str = ''


class SearchResultItem(BaseModel):
    clipId: str
    score: float
    detail: str
    eventAt: str = ''
    cameraId: str = ''
    clipFile: str = ''
    thumbFile: str = ''


class LiveSearchResponse(BaseModel):
    found: bool
    score: float
    detail: str
    bboxNorm: list[float] | None = None


class PipelineFindResponse(BaseModel):
    stage: str
    found: bool
    message: str
    live: LiveSearchResponse
    quick: list[SearchResultItem]


class RegisteredItem(BaseModel):
    name: str
    thumbFile: str = ''
    createdAt: str = ''
