from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import itertools
import threading
import json
import requests
from datetime import datetime, time
from typing import Dict, List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ==== Directoare și fișiere ====
BASE_DIR = Path(__file__).parent
VIDEO_FILLER_DIR = BASE_DIR / "data" / "video" / "filler"
AUDIO_FILLER_DIR = BASE_DIR / "data" / "audio" / "filler"
VIDEO_CAMPAIGN_DIR = BASE_DIR / "data" / "video" / "campaigns"
CAMPAIGN_JSON_PATH = BASE_DIR / "data" / "campaigns.json"

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ==== Variabile globale ====
video_files = list(VIDEO_FILLER_DIR.glob("*.mp4"))
current_video_index = 0
current_video_path = None
current_video_type = "filler"  # Track if current video is campaign or filler
last_served_video = None  # Track the last video that was actually served

audio_files = list(AUDIO_FILLER_DIR.glob("*.mp3"))
current_audio_index = 0

# Campaign tracking
campaign_plays_today: Dict[str, int] = {}
campaign_plays_hour: Dict[str, int] = {}
last_reset_day = datetime.now().day
last_reset_hour = datetime.now().hour


class CampaignScheduler:
    def __init__(self):
        self.campaigns = []
        self.load_campaigns()
    
    def load_campaigns(self):
        """Load campaigns from JSON file"""
        try:
            if CAMPAIGN_JSON_PATH.exists():
                with open(CAMPAIGN_JSON_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.campaigns = data.get('campaigns', [])
                logger.info(f"Loaded {len(self.campaigns)} campaigns")
            else:
                logger.warning("No campaigns.json file found")
                self.campaigns = []
        except Exception as e:
            logger.error(f"Error loading campaigns: {e}")
            self.campaigns = []
    
    def is_campaign_scheduled(self, campaign: dict) -> bool:
        """Check if campaign should be played now"""
        now = datetime.now()
        schedule = campaign.get('schedule', {})
        
        # Check date range
        start_date = schedule.get('start_date')
        end_date = schedule.get('end_date')
        
        if start_date:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            if now.date() < start:
                return False
        
        if end_date:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            if now.date() > end:
                return False
        
        # Check day of week
        days_of_week = schedule.get('days_of_week', [])
        if days_of_week:
            current_day = now.strftime('%A')
            if current_day not in days_of_week:
                return False
        
        # Check time ranges
        time_ranges = schedule.get('time_ranges', [])
        if time_ranges:
            current_time = now.time()
            in_time_range = False
            
            for time_range in time_ranges:
                start_time = time.fromisoformat(time_range['from'])
                end_time = time.fromisoformat(time_range['to'])
                
                if start_time <= current_time <= end_time:
                    in_time_range = True
                    break
            
            if not in_time_range:
                return False
        
        return True
    
    def can_play_campaign(self, campaign: dict) -> bool:
        """Check if campaign can be played based on constraints"""
        campaign_id = campaign['id']
        constraints = campaign.get('constraints', {})
        
        # Check hourly limit
        plays_per_hour = constraints.get('plays_per_hour', float('inf'))
        current_hour_plays = campaign_plays_hour.get(campaign_id, 0)
        if current_hour_plays >= plays_per_hour:
            return False
        
        # Check daily limit
        plays_per_day = constraints.get('plays_per_day', float('inf'))
        current_day_plays = campaign_plays_today.get(campaign_id, 0)
        if current_day_plays >= plays_per_day:
            return False
        
        return True
    
    def get_next_campaign_video(self) -> Optional[tuple]:
        """Get next campaign video if available. Returns (path, campaign_info) or None"""
        for campaign in self.campaigns:
            if (self.is_campaign_scheduled(campaign) and 
                self.can_play_campaign(campaign)):
                
                video_file = campaign.get('video_file')
                if video_file:
                    video_path = VIDEO_CAMPAIGN_DIR / video_file
                    if video_path.exists():
                        # Update play counts
                        campaign_id = campaign['id']
                        campaign_plays_hour[campaign_id] = campaign_plays_hour.get(campaign_id, 0) + 1
                        campaign_plays_today[campaign_id] = campaign_plays_today.get(campaign_id, 0) + 1
                        
                        logger.info(f"Playing campaign video: {campaign['name']} ({video_file})")
                        return video_path, campaign
        
        return None


# Initialize scheduler
scheduler = CampaignScheduler()


def reset_hourly_counters():
    """Reset hourly play counters"""
    global campaign_plays_hour, last_reset_hour
    current_hour = datetime.now().hour
    if current_hour != last_reset_hour:
        campaign_plays_hour.clear()
        last_reset_hour = current_hour
        logger.info("Reset hourly campaign counters")


def reset_daily_counters():
    """Reset daily play counters"""
    global campaign_plays_today, last_reset_day
    current_day = datetime.now().day
    if current_day != last_reset_day:
        campaign_plays_today.clear()
        last_reset_day = current_day
        logger.info("Reset daily campaign counters")


# ==== Pagina principală ====
@app.get("/", response_class=HTMLResponse)
def video_player(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ==== Obține următorul video ====
@app.get("/next-video")
def get_next_video():
    global current_video_path, current_video_index, video_files, current_video_type, last_served_video
    
    # Reset counters if needed
    reset_hourly_counters()
    reset_daily_counters()
    
    # Refresh video files list in case new files were added
    video_files = list(VIDEO_FILLER_DIR.glob("*.mp4"))
    
    # Try to get a campaign video first
    campaign_result = scheduler.get_next_campaign_video()
    if campaign_result:
        video_path, campaign_info = campaign_result
        current_video_path = video_path
        current_video_type = "campaign"
        last_served_video = {
            "path": video_path,
            "type": "campaign",
            "campaign_info": campaign_info
        }
        logger.info(f"[CAMPAIGN] {current_video_path.name}")
        return FileResponse(path=current_video_path, media_type="video/mp4")
    
    # Fall back to filler videos
    if not video_files:
        logger.error("No filler video files found")
        return JSONResponse(content={"error": "No filler video files found."}, status_code=404)
    
    # Get next filler video using index cycling
    current_video_path = video_files[current_video_index]
    current_video_type = "filler"
    last_served_video = {
        "path": current_video_path,
        "type": "filler",
        "campaign_info": None
    }
    current_video_index = (current_video_index + 1) % len(video_files)
    
    logger.info(f"[FILLER] {current_video_path.name} (index: {current_video_index-1 if current_video_index > 0 else len(video_files)-1})")
    return FileResponse(path=current_video_path, media_type="video/mp4")


# ==== Obține ID-ul videoclipului curent ====
@app.get("/api/current-video-id")
def get_current_video_id():
    global last_served_video
    
    # Check if we have a last served video
    if not last_served_video or not last_served_video.get("path"):
        # Try to initialize with the first available video
        if video_files:
            fallback_path = video_files[0]
            return {
                "id": fallback_path.stem,
                "type": "filler",
                "filename": fallback_path.name,
                "path": str(fallback_path),
                "status": "fallback - no video loaded yet"
            }
        else:
            return JSONResponse(content={"error": "No video files available."}, status_code=404)
    
    video_path = last_served_video["path"]
    video_type = last_served_video["type"]
    
    response_data = {
        "id": video_path.stem,
        "type": video_type,
        "filename": video_path.name,
        "path": str(video_path)
    }
    
    # Add campaign info if it's a campaign video
    if video_type == "campaign" and last_served_video.get("campaign_info"):
        response_data["campaign_name"] = last_served_video["campaign_info"]["name"]
        response_data["campaign_id"] = last_served_video["campaign_info"]["id"]
    
    return response_data


# ==== Campaign status endpoint ====
@app.get("/api/campaign-status")
def get_campaign_status():
    """Get current campaign status and statistics"""
    scheduler.load_campaigns()  # Reload campaigns
    
    active_campaigns = []
    for campaign in scheduler.campaigns:
        # Determine campaign status
        is_scheduled = scheduler.is_campaign_scheduled(campaign)
        can_play = scheduler.can_play_campaign(campaign)
        
        if is_scheduled and can_play:
            status = "active"
        elif is_scheduled and not can_play:
            status = "scheduled"  # Scheduled but can't play due to limits
        else:
            status = "inactive"
        
        # Get schedule info
        schedule = campaign.get('schedule', {})
        start_date = schedule.get('start_date')
        end_date = schedule.get('end_date')
        
        # Format dates for display
        start_time = None
        end_time = None
        if start_date:
            try:
                start_time = datetime.strptime(start_date, '%Y-%m-%d').isoformat()
            except ValueError:
                start_time = start_date
        
        if end_date:
            try:
                end_time = datetime.strptime(end_date, '%Y-%m-%d').isoformat()
            except ValueError:
                end_time = end_date
        
        # Get time ranges for display
        time_ranges = schedule.get('time_ranges', [])
        time_range_display = []
        for tr in time_ranges:
            time_range_display.append(f"{tr.get('from', 'N/A')} - {tr.get('to', 'N/A')}")
        
        # Check if video file exists
        video_file = campaign.get('video_file', '')
        video_exists = (VIDEO_CAMPAIGN_DIR / video_file).exists() if video_file else False
        
        status_info = {
            "id": campaign.get("id", "unknown"),
            "name": campaign.get("name", "Unnamed Campaign"),
            "status": status,
            "is_scheduled": is_scheduled,
            "can_play": can_play,
            "plays_today": campaign_plays_today.get(campaign.get("id", ""), 0),
            "plays_this_hour": campaign_plays_hour.get(campaign.get("id", ""), 0),
            "constraints": campaign.get("constraints", {}),
            "video_exists": video_exists,
            "video_file": video_file,
            "start_time": start_time,
            "end_time": end_time,
            "time_ranges": time_range_display,
            "days_of_week": schedule.get('days_of_week', []),
            "video_count": 1 if video_exists else 0,
            "current_video": video_file if video_exists else None
        }
        active_campaigns.append(status_info)
    
    return {
        "campaigns": active_campaigns,
        "current_time": datetime.now().isoformat(),
        "total_campaigns": len(scheduler.campaigns),
        "active_count": len([c for c in active_campaigns if c["status"] == "active"]),
        "scheduled_count": len([c for c in active_campaigns if c["status"] == "scheduled"]),
        "inactive_count": len([c for c in active_campaigns if c["status"] == "inactive"]),
        "current_video_info": {
            "path": str(last_served_video["path"]) if last_served_video and last_served_video.get("path") else None,
            "type": last_served_video["type"] if last_served_video else None,
            "filename": last_served_video["path"].name if last_served_video and last_served_video.get("path") else None
        }
    }


# ==== Debug endpoint to check video files ====
@app.get("/api/debug/videos")
def debug_videos():
    """Debug endpoint to check available videos"""
    filler_videos = [str(f) for f in VIDEO_FILLER_DIR.glob("*.mp4")]
    campaign_videos = [str(f) for f in VIDEO_CAMPAIGN_DIR.glob("*.mp4")]
    
    return {
        "filler_videos": filler_videos,
        "campaign_videos": campaign_videos,
        "current_video_index": current_video_index,
        "current_video_path": str(current_video_path) if current_video_path else None,
        "last_served_video": {
            "path": str(last_served_video["path"]) if last_served_video and last_served_video.get("path") else None,
            "type": last_served_video["type"] if last_served_video else None,
            "filename": last_served_video["path"].name if last_served_video and last_served_video.get("path") else None
        } if last_served_video else None,
        "current_video_type": current_video_type,
        "total_filler_videos": len(video_files),
        "video_files_exist": len(video_files) > 0
    }


# ==== Obține următoarea melodie audio ====
@app.get("/audio")
def get_next_audio():
    global audio_files, current_audio_index
    
    # Refresh audio files list
    audio_files = list(AUDIO_FILLER_DIR.glob("*.mp3"))
    
    if not audio_files:
        return JSONResponse(content={"error": "No audio files found."}, status_code=404)
    
    # Get next audio using index cycling
    next_audio = audio_files[current_audio_index]
    current_audio_index = (current_audio_index + 1) % len(audio_files)
    
    return FileResponse(path=next_audio, media_type="audio/mpeg")


# ==== Actualizare campanii și descărcare videoclipuri ====
def download_video_thread(video_url: str, filename: str):
    try:
        logger.info(f"Starting download: {filename}")
        response = requests.get(video_url, stream=True, timeout=60)
        response.raise_for_status()
        VIDEO_CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(VIDEO_CAMPAIGN_DIR / filename, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"[✓] Downloaded: {filename}")
    except Exception as e:
        logger.error(f"[✗] Failed to download {filename}: {e}")


@app.post("/api/update-schedule")
async def update_schedule(new_schedule: dict):
    try:
        # Save the new schedule
        CAMPAIGN_JSON_PATH.write_text(json.dumps(new_schedule, indent=2), encoding='utf-8')
        
        # Reload campaigns in scheduler
        scheduler.load_campaigns()
        
        # Start downloads for new videos
        download_count = 0
        for campaign in new_schedule.get("campaigns", []):
            video_url = campaign.get("video_url")
            video_file = campaign.get("video_file")
            if video_url and video_file:
                # Check if file already exists
                if not (VIDEO_CAMPAIGN_DIR / video_file).exists():
                    threading.Thread(target=download_video_thread, args=(video_url, video_file)).start()
                    download_count += 1
        
        message = f"Schedule updated with {len(scheduler.campaigns)} campaigns"
        if download_count > 0:
            message += f". Started downloading {download_count} videos."
        
        return {"status": "ok", "message": message}
    
    except Exception as e:
        logger.error(f"Error updating schedule: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# ==== Manual campaign reload ====
@app.post("/api/reload-campaigns")
def reload_campaigns():
    """Manually reload campaigns from file"""
    try:
        scheduler.load_campaigns()
        return {
            "status": "ok", 
            "message": f"Reloaded {len(scheduler.campaigns)} campaigns",
            "campaigns": len(scheduler.campaigns)
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# Initialize on startup
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    global video_files, last_served_video
    
    # Ensure directories exist
    VIDEO_FILLER_DIR.mkdir(parents=True, exist_ok=True)
    VIDEO_CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_FILLER_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load video files
    video_files = list(VIDEO_FILLER_DIR.glob("*.mp4"))
    logger.info(f"Found {len(video_files)} filler videos")
    
    # Initialize with first video if available
    if video_files:
        last_served_video = {
            "path": video_files[0],
            "type": "filler",
            "campaign_info": None
        }
        logger.info(f"Initialized with first video: {video_files[0].name}")
    else:
        logger.warning("No filler videos found during startup")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)