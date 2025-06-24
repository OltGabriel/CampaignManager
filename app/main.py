from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from pathlib import Path
import itertools

app = FastAPI()

# Folder cu videoclipuri
VIDEO_DIR = Path(__file__).parent.parent / "data" / "filler"


# Creează un iterator infinit peste lista de videoclipuri
video_files = list(VIDEO_DIR.glob("*.mp4"))
video_cycle = itertools.cycle(video_files)  # face loop infinit


@app.get("/next-video")
def get_next_video():
    print("Current working directory:", Path.cwd())
    print("Looking for videos in:", VIDEO_DIR)
    print("Exists VIDEO_DIR:", VIDEO_DIR.exists())
    print("Files in VIDEO_DIR:", list(VIDEO_DIR.glob("*.mp4")))
    
    next_video = next(video_cycle)
    print("Next video path:", next_video)
    print("Exists:", next_video.exists())
    return FileResponse(path=next_video, media_type="video/mp4")


# ruta /update POST
# actualizeze JSON si sa descarce video-uri