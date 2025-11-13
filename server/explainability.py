# server/explainability.py
"""
Small helper to create a fake heatmap overlay for an image.
This is a light-weight visualization only (not real Grad-CAM).
"""

import cv2
import numpy as np

def fake_heatmap(img_bgr):
    h, w = img_bgr.shape[:2]
    # create a random-ish heatmap based on high-frequency content
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(float)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    m = np.abs(lap)
    # normalize
    m = (m - m.min()) / (m.max() - m.min() + 1e-6)
    m = cv2.resize(m, (w, h))
    heat = cv2.applyColorMap((m*255).astype('uint8'), cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(img_bgr, 0.6, heat, 0.4, 0)
    return overlay
