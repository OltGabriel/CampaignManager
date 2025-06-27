from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from datetime import datetime
from typing import Dict

from core import (
    BASE_DIR,
    VIDEO_CAMPAIGN_DIR,
    campaign_plays_today,
    campaign_plays_hour,
    last_served_video,
    logger
)
from services import ScheduleManager, VideoService


def setup_routes(app, schedule_manager: ScheduleManager, video_service: VideoService):
    """Setup all API routes"""
    
    # ==== Pagina principală ====
    @app.get("/", response_class=HTMLResponse)
    def video_player(request: Request):
        return FileResponse(str(BASE_DIR / "templates" / "index.html"))

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