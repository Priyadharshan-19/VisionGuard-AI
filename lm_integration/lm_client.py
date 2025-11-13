# lm_integration/lm_client.py
import requests
import json
from server.config import LM_STUDIO_URL

def query_lm(prompt_text):
    """
    Sends a chat-style request to LM Studio (Phi-3-mini-4k-instruct)
    and returns the generated response.
    """
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": "phi-3-mini-4k-instruct",
        "messages": [
            {"role": "system", "content": "You are VisionGuard AI, an expert assistant in adversarial attack detection and image forensics."},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.6,
        "max_tokens": 500
    }

    try:
        response = requests.post(LM_STUDIO_URL, headers=headers, data=json.dumps(payload), timeout=30)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[LM ERROR] Failed to query model: {e}")
        return "⚠️ Unable to connect to LM Studio or process the query."


def build_prompt(user_question, context):
    """
    Builds a rich prompt combining detection context and user's question.
    """
    base_prompt = open("lm_integration/prompts/explain_prompt.txt", "r", encoding="utf-8").read()

    detection_info = f"""
    Detection Summary:
    - Label: {context.get('label', 'Unknown')}
    - Confidence: {context.get('confidence', 0):.2f}
    - Adversarial Score: {context.get('adv_score', 0):.2f}
    - Adversarial Flag: {"YES" if context.get('adv_flag') else "NO"}
    """

    full_prompt = f"{base_prompt}\n\n{detection_info}\n\nUser Question: {user_question}\n"
    return full_prompt


def get_llm_analysis(question, context):
    """
    Builds prompt, queries LM Studio, and returns structured response (summary, risk, suggestion).
    """
    prompt = build_prompt(question, context)
    raw_output = query_lm(prompt)

    # Simple parsing: we expect model to output summary, risk, and suggestion sections
    summary = extract_section(raw_output, "summary")
    risk = extract_section(raw_output, "risk")
    suggestion = extract_section(raw_output, "suggestion")

    return {
        "summary": summary or raw_output,
        "risk": risk or "Not specified.",
        "suggestion": suggestion or "No specific suggestion found."
    }


def extract_section(text, key):
    """
    Extracts a specific section like 'summary:', 'risk:', or 'suggestion:' from the LLM text.
    """
    key_lower = key.lower()
    lines = text.splitlines()
    capture = []
    recording = False

    for line in lines:
        lower = line.strip().lower()
        if lower.startswith(key_lower + ":"):
            recording = True
            capture.append(line.split(":", 1)[1].strip())
        elif recording:
            if any(k in lower for k in ["summary:", "risk:", "suggestion:"]):
                break
            capture.append(line.strip())

    return " ".join(capture).strip()
