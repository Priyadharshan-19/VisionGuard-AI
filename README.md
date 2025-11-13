# adv-detect-demo

Demo app for adversarial attack detection (stop sign sticker + cat-with-dog-ears).

## Setup

1. Put your images into:
   - `data/stop_sign/clean/`
   - `data/stop_sign/tampered/`
   - `data/cat/clean/`
   - `data/cat/dog_ears/`

2. (Optional) Create and activate a venv:
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
