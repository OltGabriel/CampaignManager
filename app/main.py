from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import itertools
import threading
import json
import requests

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
video_cycle = itertools.cycle(video_files)
current_video_path = None

audio_files = list(AUDIO_FILLER_DIR.glob("*.mp3"))
audio_cycle = itertools.cycle(audio_files)


# ==== Pagina principală ====
@app.get("/", response_class=HTMLResponse)
def video_player(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ==== Obține următorul video ====
@app.get("/next-video")
def get_next_video():
    global current_video_path
    if not video_files:
        return JSONResponse(content={"error": "No video files found."}, status_code=404)
    current_video_path = next(video_cycle)
    print(f"[NEXT] {current_video_path.name}")  # pentru debug
    return FileResponse(path=current_video_path, media_type="video/mp4")


# ==== Obține ID-ul videoclipului curent ====
@app.get("/api/current-video-id")
def get_current_video_id():
    global current_video_path
    if not current_video_path:
        return {"error": "No video is currently playing."}
    return {"id": current_video_path.stem}


# ==== Obține următoarea melodie audio ====
@app.get("/audio")
def get_next_audio():
    global audio_files, audio_cycle
    if not audio_files:
        return JSONResponse(content={"error": "No audio files found."}, status_code=404)
    next_audio = next(audio_cycle)
    return FileResponse(path=next_audio, media_type="audio/mpeg")


# ==== Actualizare campanii și descărcare videoclipuri ====
def download_video_thread(video_url: str, filename: str):
    try:
        response = requests.get(video_url, stream=True, timeout=60)
        response.raise_for_status()
        VIDEO_CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)
        with open(VIDEO_CAMPAIGN_DIR / filename, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"[✓] Downloaded: {filename}")
    except Exception as e:
        print(f"[✗] Failed to download {filename}: {e}")


@app.post("/api/update-schedule")
async def update_schedule(new_schedule: dict):
    try:
        CAMPAIGN_JSON_PATH.write_text(json.dumps(new_schedule, indent=2), encoding='utf-8')
        for campaign in new_schedule.get("campaigns", []):
            video_url = campaign.get("video_url")
            video_file = campaign.get("video_file")
            if video_url and video_file:
                threading.Thread(target=download_video_thread, args=(video_url, video_file)).start()
        return {"status": "ok", "message": "Schedule updated and download started"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
