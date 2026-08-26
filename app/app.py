import os
import json
import time
import cv2
import boto3
from botocore.config import Config
from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse
from kafka import KafkaProducer
from ultralytics import YOLO

app = FastAPI()

# Mount static files and templates setup
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configurations from environment variables
BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC = os.getenv("KAFKA_TOPIC", "/room-stream:room-intrusion-events")
CONF_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))

# S3 Data Fabric Configurations
S3_ENDPOINT = os.getenv("S3_ENDPOINT_URL", "https://s3.hpe-datafabric.local:9000")
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "intrusion-bucket")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "dummy")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "dummy")

CONFIG_FILE = "cameras.json"

def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'})
    )

def load_camera_topology():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

@app.get("/api/tree")
def get_camera_tree():
    """REST API endpoint returning camera hierarchy."""
    return JSONResponse(content=load_camera_topology())

@app.get("/api/replay/{room_name}/{timestamp}")
def get_replay_snapshot(room_name: str, timestamp: int):
    """Fetches historical snapshot from HPE Data Fabric S3 Object Store."""
    object_key = f"intrusions/{room_name}/{timestamp}.jpg"
    try:
        s3 = get_s3_client()
        response = s3.get_object(Bucket=S3_BUCKET, Key=object_key)
        return StreamingResponse(response['Body'], media_type="image/jpeg")
    except Exception:
        raise HTTPException(status_code=404, detail="Replay snapshot not found.")

@app.get("/", response_class=StreamingResponse)
def serve_homepage():
    from fastapi.responses import HTMLResponse
    if os.path.exists("templates/index.html"):
        with open("templates/index.html", "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h3>Dashboard template missing</h3>", status_code=404)