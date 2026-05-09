from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.capture import router as capture_router
from app.routers.dashboard import router as dashboard_router
from app.routers.files import router as files_router
from app.routers.health import router as health_router
from app.routers.live import router as live_router
from app.routers.phone import router as phone_router
from app.routers.pipeline import router as pipeline_router
from app.routers.quick import router as quick_router
from app.routers.register import router as register_router

app = FastAPI(title="MissingFind API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(capture_router, prefix="/api/v1/capture", tags=["capture"])
app.include_router(files_router, prefix="/api/v1/files", tags=["files"])
app.include_router(live_router, prefix="/api/v1/live", tags=["live"])
app.include_router(phone_router, prefix="/api/v1/phone", tags=["phone"])
app.include_router(pipeline_router, prefix="/api/v1/pipeline", tags=["pipeline"])
app.include_router(quick_router, prefix="/api/v1/quick", tags=["quick"])
app.include_router(register_router, prefix="/api/v1/register", tags=["register"])
