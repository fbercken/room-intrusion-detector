import os
import json
import cv2
import boto3
from botocore.config import Config
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from ultralytics import YOLO

app = FastAPI()

# Mount static files directory for CSS
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configurations from environment variables
CONF_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))

# S3 Data Fabric Configurations
S3_ENDPOINT = os.getenv("S3_ENDPOINT_URL", "https://s3.hpe-datafabric.local:9000")
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "intrusion-bucket")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "dummy")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "dummy")

CONFIG_FILE = "cameras.json"

# Load YOLOv8 model for intrusion detection
model = YOLO("yolov8n.pt")

def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'})
    )

def load_camera_topology():
    """Loads camera hierarchy from the external JSON configuration file."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def get_camera_source(room_name: str):
    """Recursively searches cameras.json to find the video source URL/path for a room."""
    topology = load_camera_topology()
    def search(node):
        for k, v in node.items():
            if k == room_name and "rtsp_url" in v:
                return v["rtsp_url"]
            if isinstance(v, dict):
                res = search(v)
                if res is not None:
                    return res
        return None
    return search(topology)

def generate_frames(source):
    """Generator capturing video frames, running YOLOv8, and streaming MJPEG."""
    cap = cv2.VideoCapture(source)
    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            # If it's a video file, loop it or break if it's a live stream stream error
            break
        
        # Run YOLOv8 inference for person/intrusion detection
        results = model(frame, conf=CONF_THRESHOLD)
        annotated_frame = results[0].plot()
        
        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        if not ret:
            continue
            
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    cap.release()

@app.get("/api/tree")
def get_camera_tree():
    """REST API endpoint returning camera hierarchy tree."""
    return JSONResponse(content=load_camera_topology())

@app.get("/api/live/{room_name}")
def live_stream(room_name: str):
    """Streams live annotated frames from the selected camera source."""
    source = get_camera_source(room_name)
    if source is None:
        raise HTTPException(status_code=404, detail="Camera source not found in topology.")
    return StreamingResponse(generate_frames(source), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/replay/{room_name}/{timestamp}")
def get_replay_snapshot(room_name: str, timestamp: int):
    """Fetches historical intrusion snapshot from HPE Data Fabric S3 Object Store."""
    object_key = f"intrusions/{room_name}/{timestamp}.jpg"
    try:
        s3 = get_s3_client()
        response = s3.get_object(Bucket=S3_BUCKET, Key=object_key)
        return StreamingResponse(response['Body'], media_type="image/jpeg")
    except Exception:
        raise HTTPException(status_code=404, detail="Replay snapshot not found.")

@app.get("/", response_class=HTMLResponse)
def serve_homepage():
    """Serves the main dashboard UI page."""
    index_path = "templates/index.html"
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h3>Dashboard template missing</h3>", status_code=404)