# server/model_utils.py
"""
Simple model utilities / stubs.
You can replace these with real PyTorch or TF classifier loaders later.
For the demo we use simple heuristics (color/texture) to detect tampering.
"""

import cv2
import numpy as np
import os

def dummy_classifier_predict(img_bgr):
    """
    Dummy classifier that returns (label, confidence).
    We use the average green channel vs red as a contrived signal:
    - if red channel strongly dominant -> "stop sign"
    - else -> "cat"
    """
    img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    r, g, b = img[:,:,0], img[:,:,1], img[:,:,2]
    r_mean, g_mean = r.mean(), g.mean()
    if r_mean > g_mean + 10:
        return "stop sign", float(min(1.0, (r_mean - g_mean) / 100.0 + 0.5))
    else:
        return "cat", float(min(1.0, (g_mean - r_mean) / 100.0 + 0.5))

# Placeholder for loading real classifier (if you later add models/)
def load_classifier(path):
    if not os.path.exists(path):
        return None
    # implement model load here
    return None
