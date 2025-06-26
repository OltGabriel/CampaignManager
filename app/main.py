from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from core import (
    BASE_DIR,
    ensure_directories,
    initialize_video_files,
    logger
)
from services import ScheduleManager, VideoService
from api import setup_routes

# Initialize FastAPI app
app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize templates
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Initialize services
schedule_manager = ScheduleManager()
video_service = VideoService(schedule_manager)

# Setup API routes
setup_routes(app, schedule_manager, video_service)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    # Ensure directories exist
    ensure_directories()
    
    # Load video files
    initialize_video_files()
    
    # Load initial schedule and campaigns
    schedule_manager.load_campaigns()
    schedule_manager.load_schedule()
    
    logger.info("Application initialized successfully")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)