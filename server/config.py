# server/config.py
import os

# Demo or IP camera URL
# Put "demo" to iterate images in ../data/ (demo mode)
# Example IP webcam URLs:
#   - IP Webcam (Android): "http://192.168.1.12:8080/video"
#   - snapshot: "http://192.168.1.12:8080/shot.jpg"
IP_CAMERA_URL = "http://10.19.166.128:8080/video"
# Frame size used for processing
FRAME_W = 640
FRAME_H = 480

# Thresholds
ADV_SCORE_THRESHOLD = 0.35

# Flask server config
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000

# Paths
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(ROOT, "data")
STATIC_CAPTURE_DIR = os.path.join(os.path.dirname(__file__), "static", "captured_frames")


# LLM Configuration for local connection (Port 1234 confirmed working)
LLM_API_URL = "http://127.0.0.1:1234/v1/chat/completions"
LM_MODEL_NAME = "phi-3-mini-4k-instruct"