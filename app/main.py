from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from pathlib import Path
import itertools

app = FastAPI()

print("LOADED MAIN")


# Folder cu videoclipuri
VIDEO_DIR = Path(__file__).parent / "data" / "filler"


# locatie HTML
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

@app.get("/", response_class=HTMLResponse)
def video_player(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# loop infinit
video_files = list(VIDEO_DIR.glob("*.mp4"))
video_cycle = itertools.cycle(video_files)  


@app.get("/next-video")
def get_next_video():
    global video_files, video_cycle
    video_files = list(VIDEO_DIR.glob("*.mp4"))
    
    if not video_files:
        return {"error": "No video files found."}
    
    video_cycle = itertools.cycle(video_files)
    next_video = next(video_cycle)
    return FileResponse(path=next_video, media_type="video/mp4")

# ruta /update POST
# actualizeze JSON si sa descarce video-uri