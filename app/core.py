from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==== Directoare și fișiere ====
BASE_DIR = Path(__file__).parent
VIDEO_FILLER_DIR = BASE_DIR / "data" / "video" / "filler"
AUDIO_FILLER_DIR = BASE_DIR / "data" / "audio" / "filler"
VIDEO_CAMPAIGN_DIR = BASE_DIR / "data" / "video" / "campaigns"
AUDIO_CAMPAIGN_DIR = BASE_DIR / "data" / "audio" / "campaigns"
CAMPAIGN_JSON_PATH = BASE_DIR / "data" / "campaigns.json"
SCHEDULE_JSON_PATH = BASE_DIR / "data" / "schedule.json"
PLACEHOLDER_IMAGE_PATH = BASE_DIR / "data" / "placeholder.png"

# ==== Variabile globale ====
video_files = []
current_video_index = 0
current_video_path = None
current_video_type = "placeholder"
last_served_video = None

audio_files = []
current_audio_index = 0

# Campaign tracking
campaign_plays_today: Dict[str, int] = {}
campaign_plays_hour: Dict[str, int] = {}
last_reset_day = datetime.now().day
last_reset_hour = datetime.now().hour


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


def ensure_directories():
    """Ensure all required directories exist"""
    VIDEO_FILLER_DIR.mkdir(parents=True, exist_ok=True)
    VIDEO_CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_FILLER_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)


def initialize_video_files():
    """Initialize video files list"""
    global video_files
    video_files = list(VIDEO_FILLER_DIR.glob("*.mp4"))
    logger.info(f"Found {len(video_files)} filler videos")
    return video_files