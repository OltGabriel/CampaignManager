# --- Config validation and loading ---
def validate_config(config: dict) -> bool:
    """Validate the loaded configuration"""
    required_fields = ["stream_type", "device_name", "location_id"]
    for field in required_fields:
        if field not in config:
            logger.error(f"Missing required config field: {field}")
            return False
    return True

def load_config():
    """Load configuration from config.json if it exists"""
    global config
    if config is not None and config != {}:
        return config
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
            logger.info("Loaded configuration from config.json")
            if not validate_config(config):
                logger.error("Invalid configuration. Some required fields are missing.")
                config = {}
        except Exception as e:
            logger.error(f"Failed to load config.json: {e}")
            config = {}
    else:
        logger.warning("No config.json found; using defaults")
        config = {}
    return config
# === Device config and API key helpers (moved from api.py) ===
import hashlib
import time
from fastapi import Header
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging
import json


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode('utf-8')).hexdigest()


def save_device_config(cfg):
    # Remove 'mode' if present, always use 'stream_type'
    if 'mode' in cfg:
        cfg['stream_type'] = cfg.pop('mode')
    with open(DEVICE_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def require_api_key(x_api_key: str = Header(...)):
    config = load_config()
    stored_hash = config.get('api_key_hash')
    if not stored_hash:
        return False
    return hash_api_key(x_api_key) == stored_hash
config: dict = {}

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
CONFIG_PATH = BASE_DIR / "config.json"
DEVICE_CONFIG_PATH = CONFIG_PATH
HEARTBEAT_PATH = BASE_DIR / "data" / "heartbeat.json"

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