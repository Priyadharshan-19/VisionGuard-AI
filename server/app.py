# server/app.py
"""
Integrated Flask server:
 - demo/frame producer using images in data/ (if config.IP_CAMERA_URL == "demo")
 - IP camera mode: tries cv2.VideoCapture first; if fails, falls back to snapshot polling
 - endpoints:
    /left_stream    -> mjpeg left
    /right_stream -> mjpeg right
    /status       -> latest result JSON
    /captured_frames/<file> -> saved annotated frames
    /ask          -> send question + context to LM Studio and return structured response
 - serves frontend files if present under ../frontend/
"""

import os
import time
import cv2
import threading
import requests
from flask import Flask, Response, jsonify, send_from_directory, request, abort
from flask_cors import CORS
from server import pipelines, config, model_utils, explainability
import numpy as np

# ensure static dir
os.makedirs(config.STATIC_CAPTURE_DIR, exist_ok=True)

app = Flask(__name__, static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend")))
CORS(app)

# shared state
shared = {
    "left_jpeg": None,
    "right_jpeg": None,
    "last_result": {
        "label": "unknown",
        "confidence": 0.0,
        "adv_score": 0.0,
        "adv_flag": False,
        "notes": "no frames yet"
    },
    "running": True
}

def jpeg_bytes_from_bgr(img_bgr, quality=80):
    ret, buf = cv2.imencode('.jpg', img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return buf.tobytes() if ret else None

# --------- frame producers -----------
def frame_producer_demo(loop_delay=1.0):
    data_dir = config.DATA_DIR
    image_paths = []
    for root, _, files in os.walk(data_dir):
        for f in files:
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                image_paths.append(os.path.join(root, f))
    if not image_paths:
        print("No images found in data/ — add your test images.")
        return
    idx = 0
    while shared["running"]:
        path = image_paths[idx % len(image_paths)]
        img = cv2.imread(path)
        if img is None:
            idx += 1
            continue
        try:
            img = cv2.resize(img, (config.FRAME_W, config.FRAME_H))
        except Exception:
            pass
        left_img, right_img, result = pipelines.process_frame(img)
        shared['left_jpeg'] = jpeg_bytes_from_bgr(left_img)
        shared['right_jpeg'] = jpeg_bytes_from_bgr(right_img)
        shared['last_result'] = result
        # save annotated
        cv2.imwrite(os.path.join(config.STATIC_CAPTURE_DIR, "left_latest.jpg"), left_img)
        cv2.imwrite(os.path.join(config.STATIC_CAPTURE_DIR, "right_latest.jpg"), right_img)
        idx += 1
        time.sleep(loop_delay)

def read_snapshot(url, timeout=5):
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code != 200:
            return None
        arr = np.frombuffer(r.content, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None

def frame_producer_ip(loop_delay=0.05):
    url = config.IP_CAMERA_URL
    # try VideoCapture first
    cap = None
    try:
        cap = cv2.VideoCapture(url)
        ok, frame = cap.read()
        if not ok:
            cap.release()
            cap = None
    except Exception:
        cap = None

    if cap is not None:
        print("Using cv2.VideoCapture for IP stream:", url)
        while shared["running"]:
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.2)
                continue
            try:
                frame = cv2.resize(frame, (config.FRAME_W, config.FRAME_H))
            except Exception:
                pass
            left_img, right_img, result = pipelines.process_frame(frame)
            shared['left_jpeg'] = jpeg_bytes_from_bgr(left_img)
            shared['right_jpeg'] = jpeg_bytes_from_bgr(right_img)
            shared['last_result'] = result
            cv2.imwrite(os.path.join(config.STATIC_CAPTURE_DIR, "left_latest.jpg"), left_img)
            cv2.imwrite(os.path.join(config.STATIC_CAPTURE_DIR, "right_latest.jpg"), right_img)
            time.sleep(loop_delay)
        try:
            cap.release()
        except Exception:
            pass
        return

    # fallback: snapshot polling
    print("Falling back to snapshot polling for IP stream:", url)
    while shared["running"]:
        frame = read_snapshot(url)
        if frame is None:
            time.sleep(0.5)
            continue
        try:
            frame = cv2.resize(frame, (config.FRAME_W, config.FRAME_H))
        except Exception:
            pass
        left_img, right_img, result = pipelines.process_frame(frame)
        shared['left_jpeg'] = jpeg_bytes_from_bgr(left_img)
        shared['right_jpeg'] = jpeg_bytes_from_bgr(right_img)
        shared['last_result'] = result
        cv2.imwrite(os.path.join(config.STATIC_CAPTURE_DIR, "left_latest.jpg"), left_img)
        cv2.imwrite(os.path.join(config.STATIC_CAPTURE_DIR, "right_latest.jpg"), right_img)
        time.sleep(0.2)

# --------- mjpeg generator ----------
def generate_mjpeg(side):
    while True:
        data = shared['left_jpeg'] if side == 'left' else shared['right_jpeg']
        if data:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + data + b'\r\n')
        else:
            # tiny 1x1 blank jpeg
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + b'\xff\xd8\xff\xdb' + b'\r\n')
        time.sleep(0.05)

# --------- routes ----------
@app.route('/left_stream')
def left_stream():
    return Response(generate_mjpeg('left'), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/right_stream')
def right_stream():
    return Response(generate_mjpeg('right'), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    return jsonify(shared['last_result'])

@app.route('/captured_frames/<path:filename>')
def captured_frames(filename):
    return send_from_directory(config.STATIC_CAPTURE_DIR, filename)

# LM Studio ask endpoint
@app.route('/ask', methods=['POST'])
def ask_genai():
    data = request.get_json(force=True)
    question = data.get('question', '')
    context = data.get('context', shared.get('last_result', {}))

    if not question:
        return jsonify({"error": "No question provided"}), 400

    # --- DIAGNOSTIC FIX: Hardcode working URL to bypass config error ---
    LM_STUDIO_URL_FIXED = "http://127.0.0.1:1234/v1/chat/completions"
    
    # 1. Define the correct, absolute path to the prompt file
    prompt_file_path = os.path.join(
        config.ROOT, 
        "lm_integration", 
        "prompts", 
        "explain_prompt.txt"
    )
    
    # 2. Safely read the base prompt template
    try:
        with open(prompt_file_path, "r", encoding="utf-8") as f:
            base_prompt_template = f.read()
    except FileNotFoundError:
        # Fallback if the file somehow goes missing
        print(f"[ERROR] Prompt file not found at: {prompt_file_path}")
        base_prompt_template = "You are an assistant specialized in adversarial detection." 
    
    # 3. Build the final prompt using the template and context
    prompt = f"""
{base_prompt_template}

Current detection:
Label: {context.get('label')}
Confidence: {context.get('confidence')}
Adv score: {context.get('adv_score')}
Flagged: {context.get('adv_flag')}

User question: {question}

Please answer in this exact format:
Summary: <short summary>
Risk: <short risk>
Suggestion: <actionable suggestion>
"""

    payload = {
        # Note: We still rely on config for LM_MODEL_NAME, which should be fine
        "model": config.LM_MODEL_NAME if hasattr(config, "LM_MODEL_NAME") else "phi-3-mini-4k-instruct",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant for adversarial detection."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.6,
        "max_tokens": 240
    }

    try:
        # !!! USE HARDCODED URL HERE !!!
        r = requests.post(LM_STUDIO_URL_FIXED, json=payload, timeout=60)
        r.raise_for_status()
        body = r.json()
        # model may return choices[0].message.content
        reply = ""
        try:
            reply = body["choices"][0]["message"]["content"].strip()
        except Exception:
            # fallback to other response shapes
            reply = str(body)
        # attempt parse
        summary, risk, suggestion = "-", "-", "-"
        for line in reply.splitlines():
            if line.lower().startswith("summary:"):
                summary = line.split(":",1)[1].strip()
            elif line.lower().startswith("risk:"):
                risk = line.split(":",1)[1].strip()
            elif line.lower().startswith("suggestion:"):
                suggestion = line.split(":",1)[1].strip()
        return jsonify({"summary": summary or reply, "risk": risk, "suggestion": suggestion})
    except Exception as e:
        print(f"\n!!!!!!!!!!!! Flask Server CRASH Details: {e} !!!!!!!!!!!!\n")
        # Return HTTP 500 error response
        return jsonify({"error": "LLM Connection/Processing Failed: " + str(e)}), 500

# serve frontend static files
@app.route('/')
def index():
    # serve frontend/index.html
    return app.send_static_file('index.html')

@app.route('/<path:filename>')
def frontend_files(filename):
    # allow static assets in frontend folder
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
    safe = os.path.abspath(os.path.join(root, filename))
    if not safe.startswith(root):
        abort(404)
    return send_from_directory(root, filename)

# background thread starter
def start_background_thread():
    if config.IP_CAMERA_URL == "demo":
        t = threading.Thread(target=frame_producer_demo, daemon=True)
    else:
        t = threading.Thread(target=frame_producer_ip, daemon=True)
    t.start()
    return t

if __name__ == '__main__':
    print("Starting VisionGuard integrated server...")
    start_background_thread()
    app.run(host=config.SERVER_HOST, port=config.SERVER_PORT, threaded=True)