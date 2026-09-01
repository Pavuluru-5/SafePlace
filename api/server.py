"""
SafePlace FastAPI Web Server
Mounts API endpoints and static frontend UI.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from contextlib import asynccontextmanager

from api.routes import router
import config
from data.dataset_builder import seed_offline_database
from core.database import OfflineDatabase


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure offline DB is seeded on startup
    db = OfflineDatabase()
    if len(db.get_all_pois()) == 0:
        seed_offline_database(db)
    yield


app = FastAPI(
    title="SafePlace — Offline AI Safety Copilot",
    description="Offline-First AI Safety Copilot API and Decision Support System",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(router)

# Mount Static UI directory
ui_path = Path(__file__).resolve().parent.parent / "ui"
ui_path.mkdir(parents=True, exist_ok=True)
(ui_path / "css").mkdir(parents=True, exist_ok=True)
(ui_path / "js").mkdir(parents=True, exist_ok=True)

app.mount("/", StaticFiles(directory=str(ui_path), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.server:app", host=config.SERVER_HOST, port=config.SERVER_PORT, reload=True)
