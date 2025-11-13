# server/pipelines.py
"""
Main processing pipeline for a single frame.
- input: BGR image (numpy)
- output: left_img (annotated baseline), right_img (annotated adv detection view), result dict
"""

import cv2
import numpy as np
from . import model_utils
from . import config
import os

# simple helper: compute a tamper/adversarial score
def compute_adv_score(img_bgr):
    """
    Heuristic:
     - compute Laplacian variance (sharpness) — stickers often produce local high-frequency anomalies
     - compute color patch irregularities (std across small patches)
     - combine into 0..1 score
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    lap_var = np.var(lap)

    # patch color variance
    h, w = gray.shape
    ph, pw = 32, 32
    stds = []
    for y in range(0, h, ph):
        for x in range(0, w, pw):
            patch = img_bgr[y:y+ph, x:x+pw]
            if patch.size == 0:
                continue
            stds.append(np.std(patch))
    color_std = float(np.mean(stds)) if stds else 0.0

    # normalize heuristics with empirical factors
    lap_score = np.tanh(lap_var / 1000.0)
    color_score = np.tanh(color_std / 30.0)
    score = 0.5 * lap_score + 0.5 * color_score
    return float(np.clip(score, 0.0, 1.0)), lap_var, color_std

def annotate_image(img_bgr, text_lines=None, adv=False):
    """Return copy annotated with text and border (red if adv)"""
    out = img_bgr.copy()
    h, w = out.shape[:2]
    # border
    color = (0, 255, 0) if not adv else (0, 0, 255)
    cv2.rectangle(out, (2,2), (w-2, h-2), color, 4)
    # put text
    y0 = 24
    for i, line in enumerate(text_lines or []):
        cv2.putText(out, line, (12, y0 + i*22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2, cv2.LINE_AA)
    return out

def process_frame(img_bgr):
    """
    Main pipeline:
     - run dummy classifier
     - compute adv score
     - build annotated left/right images and result dict
    """
    # classifier
    label, conf = model_utils.dummy_classifier_predict(img_bgr)

    adv_score, lap_var, color_std = compute_adv_score(img_bgr)
    adv_flag = adv_score >= config.ADV_SCORE_THRESHOLD

    # Annotate left (baseline) and right (adv) views
    left_lines = [f"Label: {label}", f"Confidence: {conf:.2f}", f"Adv score: {adv_score:.2f}"]
    right_lines = [f"Adv score: {adv_score:.2f}", f"Flagged: {'YES' if adv_flag else 'NO'}", f"LapVar:{lap_var:.1f}"]

    left_img = annotate_image(img_bgr, left_lines, adv=False)
    right_img = annotate_image(img_bgr, right_lines, adv=adv_flag)

    result = {
        "label": label,
        "confidence": float(conf),
        "adv_score": float(adv_score),
        "adv_flag": bool(adv_flag),
        "notes": f"lap_var={lap_var:.1f}, color_std={color_std:.2f}"
    }
    return left_img, right_img, result
