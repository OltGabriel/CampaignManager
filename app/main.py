from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from pathlib import Path
import itertools
import threading
import json
import requests

app = FastAPI()

# Directoare media
VIDEO_FILLER_DIR = Path(__file__).parent / "data" / "video" / "filler"
AUDIO_FILLER_DIR = Path(__file__).parent / "data" / "audio" / "filler"
VIDEO_CAMPAIGN_DIR = Path(__file__).parent / "data" / "video" / "campaigns"
CAMPAIGN_JSON_PATH = Path(__file__).parent / "data" / "campaigns.json"

# Templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

@app.get("/", response_class=HTMLResponse)
def video_player(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# ===== VIDEO (filler loop) =====
video_files = list(VIDEO_FILLER_DIR.glob("*.mp4"))
video_cycle = itertools.cycle(video_files)

@app.get("/next-video")
def get_next_video():
    global video_files, video_cycle
    video_files = list(VIDEO_FILLER_DIR.glob("*.mp4"))
    if not video_files:
        return {"error": "No video files found."}
    video_cycle = itertools.cycle(video_files)
    return FileResponse(path=next(video_cycle), media_type="video/mp4")

# ===== AUDIO (filler loop) =====
audio_files = list(AUDIO_FILLER_DIR.glob("*.mp3"))
audio_cycle = itertools.cycle(audio_files)

@app.get("/audio")
def get_next_audio():
    global audio_files, audio_cycle
    audio_files = list(AUDIO_FILLER_DIR.glob("*.mp3"))
    if not audio_files:
        return {"error": "No audio files found."}
    audio_cycle = itertools.cycle(audio_files)
    return FileResponse(path=next(audio_cycle), media_type="audio/mpeg")


# ===== UPDATE CAMPAIGNS =====
def download_video_thread(video_url: str, filename: str):
    try:
        response = requests.get(video_url, stream=True, timeout=60)
        response.raise_for_status()
        with open(VIDEO_CAMPAIGN_DIR / filename, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"[✓] Downloaded: {filename}")
    except Exception as e:
        print(f"[✗] Failed to download {filename}: {e}")

@app.post("/api/update-schedule")
async def update_schedule(new_schedule: dict):
    try:
        # Scrie JSON-ul în fisier
        CAMPAIGN_JSON_PATH.write_text(json.dumps(new_schedule, indent=2), encoding='utf-8')

        # Creează directoarele dacă nu există
        VIDEO_CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)

        # Descarcă fiecare video într-un thread separat
        for campaign in new_schedule.get("campaigns", []):
            video_url = campaign.get("video_url")
            video_file = campaign.get("video_file")
            if video_url and video_file:
                threading.Thread(target=download_video_thread, args=(video_url, video_file)).start()

        return {"status": "ok", "message": "Schedule updated and download started"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
