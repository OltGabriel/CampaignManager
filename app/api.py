from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from datetime import datetime
from typing import Dict
import json
import hashlib
import time
from fastapi import Header
from pathlib import Path

from core import (
    BASE_DIR,
    VIDEO_CAMPAIGN_DIR,
    campaign_plays_today,
    campaign_plays_hour,
    last_served_video,
    logger,
    CAMPAIGN_JSON_PATH,
    SCHEDULE_JSON_PATH,
    CONFIG_PATH,
    DEVICE_CONFIG_PATH,
    HEARTBEAT_PATH,
    hash_api_key,
    load_config,
    require_api_key
)
from services import ScheduleManager, VideoService

def setup_routes(app, schedule_manager: ScheduleManager, video_service: VideoService):
    # === Device Configured Status Endpoint ===
    @app.get("/api/device/configured")
    def device_configured():
        config = load_config()
        required = {"device_name", "location_id", "stream_type"}
        is_configured = all(k in config and config[k] for k in required)
        stream_type = config.get("stream_type")
        return {"configured": is_configured, "stream_type": stream_type}



    # === Device Initialization Endpoint ===
    @app.post("/api/device/init")
    async def device_init(request: Request):
        data = await request.json()
        stream_type = data.get('stream_type')  # 'audio' or 'video'
        api_key = data.get('api_key')
        device_name = data.get('device_name', 'Unknown')
        if stream_type not in ('audio', 'video'):
            return JSONResponse(status_code=400, content={"error": "stream_type must be 'audio' or 'video'"})
        if not api_key:
            return JSONResponse(status_code=400, content={"error": "API key required"})
        # Hash and store API key
        config = load_config()
        config['stream_type'] = stream_type
        config['device_name'] = device_name
        config['api_key_hash'] = hash_api_key(api_key)
        load_config(config)
        return {"status": "ok", "message": f"Device initialized as {stream_type}", "device_name": device_name}

    # === Heartbeat Endpoint ===
    @app.post("/api/device/heartbeat")
    async def device_heartbeat(request: Request, x_api_key: str = Header(...)):
        if not require_api_key(x_api_key):
            return JSONResponse(status_code=401, content={"error": "Invalid API key"})
        config = load_config()
        device_name = config.get('device_name', 'Unknown')
        now = int(time.time())
        # Save heartbeat info
        heartbeat_info = {"device_name": device_name, "last_seen": now}
        with open(HEARTBEAT_PATH, 'w', encoding='utf-8') as f:
            json.dump(heartbeat_info, f, indent=2)
        return {"status": "ok", "last_seen": now}
    """Setup all API routes"""

    # ==== Update la Campanii ====
    @app.post("/api/update-campaigns")
    async def update_campaigns(request: Request):
        """Upload a new campaigns.json (overwrite)"""
        try:
            data = await request.json()
            # TODO LOG THE NEW CAMPAIGN DATA
            with open(CAMPAIGN_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            # Reload campaigns and (optionally) schedule
            schedule_manager.load_campaigns()
            schedule_manager.load_schedule()  # for safety, reload schedule (can be skipped if not needed)
            return {"status": "ok", "message": "campaigns.json updated and reloaded"}
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})
    
    # ==== Update la Schedule ====
    @app.post("/api/update-schedule")
    async def update_schedule(request: Request):
        """Upload a new schedule.json (overwrite)"""
        try:
            data = await request.json()
            # TODO LOG THE NEW SCHEDULE DATA
            with open(SCHEDULE_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            schedule_manager.load_schedule()
            return {"status": "ok", "message": "schedule.json updated and reloaded"}
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})

    # ==== Pagina principală ====
    @app.get("/video", response_class=HTMLResponse)
    def video_player(request: Request):
        return FileResponse(str(BASE_DIR / "templates" / "video.html"))
    @app.get("/audio", response_class=HTMLResponse)
    def video_player(request: Request):
        return FileResponse(str(BASE_DIR / "templates" / "audio.html"))
    @app.get("/setup", response_class=HTMLResponse)
    def video_player(request: Request):
        return FileResponse(str(BASE_DIR / "templates" / "setup.html"))
    
    @app.get("/")
    def smart_redirect():
        """Redirect based on config.json stream_type"""
        # ensure the config is loaded``
        current_config  = {}
        try:
            current_config  = load_config()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return JSONResponse(status_code=500, content={"error": "Configuration error"})
        stream_type = current_config.get("stream_type")
        if stream_type == "audio":
            return RedirectResponse(url="/audio")
        elif stream_type == "video":
            return RedirectResponse(url="/video")
        else:
            return RedirectResponse(url="/setup")
        
    # === Setup Device ===
    @app.post("/api/device/setup")
    async def device_setup(request: Request):
        try:
            data = await request.json()

            # Validare minimală
            required_keys = {"device_name", "location_id", "stream_type"}
            if not required_keys.issubset(data.keys()):
                return JSONResponse(status_code=400, content={"error": "Missing required fields"})

            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return {"status": "ok", "message": "Config saved"}
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})

    # ==== Obține următorul video ====
    @app.get("/next-video")
    def get_next_video():
        video_path, video_type = video_service.get_next_video()
        
        if video_type == 'error':
            return JSONResponse(content={"error": "No scheduled content and no placeholder available."}, status_code=404)
        
        if video_type == 'placeholder':
            return FileResponse(path=video_path, media_type="image/png")
        elif video_type == 'campaign':
            return FileResponse(path=video_path, media_type="video/mp4")
        elif video_type == 'filler':
            return FileResponse(path=video_path, media_type="video/mp4")
        
        return JSONResponse(content={"error": "Unknown video type"}, status_code=500)

    # ==== Obține ID-ul videoclipului curent ====
    @app.get("/api/current-video-id")
    def get_current_video_id():
        video_info = video_service.get_current_video_info()
        
        if not video_info:
            return JSONResponse(content={"error": "No content loaded yet."}, status_code=404)
        
        return video_info


    @app.get("/api/schedule-status")
    def get_schedule_status():
        schedule_manager.load_schedule()
        schedule_manager.load_campaigns()

        current_time = datetime.now()
        is_valid_today = schedule_manager.is_schedule_for_today()

        current_scheduled = schedule_manager.get_current_scheduled_item()
        current_item_info = None
        if current_scheduled:
            scheduled_item, campaign_info = current_scheduled
            current_item_info = {
                "id": scheduled_item.get('id'),
                "type": scheduled_item.get('type'),
                "at": scheduled_item.get('at'),
                "duration": scheduled_item.get('duration'),
                "name": campaign_info.get('name') if campaign_info else scheduled_item.get('id')
            }

        playlist_items = schedule_manager.get_all_playlist_items()

        # NEW: Time since start in seconds
        time_since_start = None
        if schedule_manager.start_time:
            delta = datetime.now() - schedule_manager.start_time
            time_since_start = int(delta.total_seconds())

        return {
            "schedule_date": schedule_manager.schedule.get('date', 'N/A'),
            "is_valid_for_today": is_valid_today,
            "current_time": current_time.strftime('%H:%M:%S'),
            "time_since_start_seconds": time_since_start,
            "current_scheduled_item": current_item_info,
            "playlist": playlist_items,
            "total_playlist_items": len(playlist_items),
            "timezone": schedule_manager.schedule.get('timezone', 'Europe/Bucharest'),
            "next_scheduled_time": schedule_manager.get_next_scheduled_item_time().isoformat() if schedule_manager.get_next_scheduled_item_time() else None,
            "last_served_content": {
                "path": str(last_served_video["path"]) if last_served_video and last_served_video.get("path") else None,
                "type": last_served_video["type"] if last_served_video else None,
                "filename": last_served_video["path"].name if last_served_video and last_served_video.get("path") and hasattr(last_served_video["path"], 'name') else None,
                "scheduled": last_served_video.get("info", {}).get("scheduled", False) if last_served_video else False
            } if last_served_video else None
        }


    # ==== Campaign status endpoint ====
    @app.get("/api/campaign-status")
    def get_campaign_status():
        """Get current campaign status and statistics"""
        schedule_manager.load_campaigns()
        
        campaigns_info = []
        for campaign_id, campaign in schedule_manager.campaigns.items():
            # Check if video file exists
            video_file = campaign.get('video_file', '')
            video_exists = (VIDEO_CAMPAIGN_DIR / video_file).exists() if video_file else False
            
            campaign_info = {
                "id": campaign_id,
                "name": campaign.get("name", "Unnamed Campaign"),
                "plays_today": campaign_plays_today.get(campaign_id, 0),
                "plays_this_hour": campaign_plays_hour.get(campaign_id, 0),
                "video_exists": video_exists,
                "video_file": video_file
            }
            campaigns_info.append(campaign_info)
        
        return {
            "campaigns": campaigns_info,
            "current_time": datetime.now().isoformat(),
            "total_campaigns": len(schedule_manager.campaigns)
        }

    # ==== Manual reload endpoints ====
    @app.post("/api/reload-schedule")
    def reload_schedule():
        """Manually reload schedule from file"""
        try:
            schedule_manager.load_schedule()
            return {
                "status": "ok", 
                "message": f"Reloaded schedule for {schedule_manager.schedule.get('date', 'unknown date')}",
                "items": len(schedule_manager.schedule.get('playlist', []))
            }
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})

    @app.post("/api/reload-campaigns")
    def reload_campaigns():
        """Manually reload campaigns from file"""
        try:
            schedule_manager.load_campaigns()
            return {
                "status": "ok", 
                "message": f"Reloaded {len(schedule_manager.campaigns)} campaigns",
                "campaigns": len(schedule_manager.campaigns)
            }
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})