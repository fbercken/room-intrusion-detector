FROM python:3.10-slim

WORKDIR /app

#COPY app/ .
#CMD ["python", "main.py"]

WORKDIR /app

# Install system utilities and cv2 prerequisites
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY cameras.json .
COPY app.py .
COPY static/ ./static/
COPY templates/ ./templates/

EXPOSE 8000

CMD ["uvicorn", "app.py:app", "--host", "0.0.0.0", "--port", "8000"]
