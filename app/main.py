import os
import time
import json
import cv2
import boto3
from botocore.config import Config
from kafka import KafkaProducer
from ultralytics import YOLO

# Configuration from environment variables
ROOM_NAME = os.getenv("ROOM_NAME", "Unknown-Room")
RTSP_URL = os.getenv("CAMERA_RTSP_URL")
BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
TOPIC = os.getenv("KAFKA_TOPIC", "room-intrusion-events")
CONF_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))

# S3 Data Fabric Configurations
S3_ENDPOINT = os.getenv("S3_ENDPOINT_URL")
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

def initialize_s3_client():
    """Initialize S3-compatible client for HPE Data Fabric Object Store."""
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'})
    )

def initialize_producer():
    while True:
        try:
            producer = KafkaProducer(
                bootstrap_servers=[BOOTSTRAP_SERVERS],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                retries=5
            )
            print("Connected to streaming event backbone.")
            return producer
        except Exception as e:
            print(f"Retrying connection to event broker... Error: {e}")
            time.sleep(5)

def main():
    print(f"Starting video stream monitoring for: {ROOM_NAME}")
    model = YOLO("yolov8n.pt")
    producer = initialize_producer()
    s3_client = initialize_s3_client()
    
    cap = cv2.VideoCapture(RTSP_URL)
    if not cap.isOpened():
        raise RuntimeError(f"Error opening video stream link: {RTSP_URL}")

    frame_id = 0
    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            time.sleep(2)
            cap = cv2.VideoCapture(RTSP_URL)
            continue

        frame_id += 1
        if frame_id % 5 != 0:
            continue

        results = model(frame, verbose=False)
        person_detected = False
        detections_data = []

        for r in results:
            for box in r.boxes:
                if int(box.cls[0]) == 0 and float(box.conf[0]) >= CONF_THRESHOLD:
                    person_detected = True
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    detections_data.append({"confidence": round(float(box.conf[0]), 2), "box": [x1, y1, x2, y2]})

        if person_detected:
            timestamp = int(time.time())
            object_key = f"intrusions/{ROOM_NAME}/{timestamp}.jpg"
            
            # Encode frame to JPEG format in-memory
            success_enc, encoded_image = cv2.imencode('.jpg', frame)
            if success_enc:
                # Upload snapshot directly to S3 Data Fabric bucket
                s3_client.put_object(
                    Bucket=S3_BUCKET,
                    Key=object_key,
                    Body=encoded_image.tobytes(),
                    ContentType='image/jpeg'
                )

            event_payload = {
                "timestamp": timestamp,
                "room": ROOM_NAME,
                "event": "INTRUSION_DETECTED",
                "snapshot_s3_path": f"s3://{S3_BUCKET}/{object_key}",
                "object_count": len(detections_data),
                "details": detections_data
            }
            
            producer.send(TOPIC, value=event_payload)
            producer.flush()
            print(f"ALERT: Intrusion in {ROOM_NAME}! Snapshot sent to S3 data fabric and event published.")

    cap.release()

if __name__ == "__main__":
    main()
