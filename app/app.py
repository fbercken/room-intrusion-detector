import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
import boto3
from botocore.config import Config

app = FastAPI()

# Mount static files relative to the app directory
app.mount("/static", StaticFiles(directory="static"), name="static")

CONFIG_FILE = "cameras.json"

def load_camera_topology():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

@app.get("/api/tree")
def get_camera_tree():
    return JSONResponse(content=load_camera_topology())

@app.get("/", response_class=HTMLResponse)
def serve_homepage():
    index_path = "templates/index.html"
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h3>Dashboard template missing</h3>", status_code=404)