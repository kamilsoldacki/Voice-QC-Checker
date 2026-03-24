from flask import Flask, request, jsonify, send_from_directory
from pydub import AudioSegment
import os
import json
import requests
import uuid

app = Flask(__name__)


def _static_dir():
    """Same directory Flask uses for /static/ URLs (not os.getcwd())."""
    return os.path.join(app.root_path, "static")


def _elevenlabs_error_message(response):
    if response is None:
        return "No response"
    try:
        payload = response.json()
    except ValueError:
        text = (response.text or "").strip()
        return text[:800] if text else f"HTTP {response.status_code}"
    detail = payload.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict):
                parts.append(str(item.get("msg", item)))
            else:
                parts.append(str(item))
        return "; ".join(parts) if parts else str(payload)[:800]
    if isinstance(payload, dict) and payload:
        return str(payload)[:800]
    return f"HTTP {response.status_code}"


# How much consecutive lines overlap (ms). Next line starts before the previous ends.
DIALOGUE_LINE_OVERLAP_MS = 320


def _merge_dialogue_segments(segments, overlap_ms=DIALOGUE_LINE_OVERLAP_MS):
    """Join clips with temporal overlap so replies feel quicker / more alive."""
    if not segments:
        return AudioSegment.empty()
    merged = segments[0]
    for seg in segments[1:]:
        if len(merged) < 100 or len(seg) < 100:
            merged = merged + seg
            continue
        overlap = min(overlap_ms, len(merged) // 3, len(seg) // 3)
        if overlap < 60:
            merged = merged + seg
            continue
        position = len(merged) - overlap
        try:
            merged = merged.overlay(seg, position=position, gain_during_overlay=-5)
        except TypeError:
            merged = merged.overlay(seg, position=position)
    return merged


def _elevenlabs_tts(voice_id, api_key, text, model):
    """Call TTS; on 400 retry with text+model only (some models reject voice_settings)."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    params = {"output_format": "mp3_44100_128"}
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    full_body = {
        "text": text,
        "model_id": model,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }
    min_body = {"text": text, "model_id": model}
    r = requests.post(url, headers=headers, params=params, json=full_body, timeout=120)
    if r.status_code == 200:
        return r, None
    if r.status_code == 400:
        r2 = requests.post(url, headers=headers, params=params, json=min_body, timeout=120)
        if r2.status_code == 200:
            return r2, None
        return r2, _elevenlabs_error_message(r2)
    return r, _elevenlabs_error_message(r)


# Wczytanie tekstów z pliku JSON
with open("texts.json", "r", encoding="utf-8") as f:
    TEXTS = json.load(f)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/conversation-tester.html')
def conversation_tester():
    return send_from_directory('static_pages', 'conversation-tester.html')

@app.route('/languages')
def languages():
    langs = sorted(TEXTS.keys())
    return jsonify({"languages": [{"name": lang} for lang in langs]})

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    voice_id = data['voiceId']
    language = data['language']

    if language not in TEXTS:
        return jsonify({"error": "Language not found"}), 400

    samples = TEXTS[language]
    outputs = {}
    for key in ['plosives', 'sibilants', 'additional']:
        text = samples.get(key, "")
        audio_url = generate_sample(voice_id, text)
        outputs[key] = {
            "text": text,
            "audio_url": audio_url
        }

    return jsonify(outputs)

def generate_sample(voice_id, text):
    api_key = os.environ.get("ELEVEN_API_KEY")
    if not api_key:
        raise Exception("Missing ELEVEN_API_KEY in environment variables.")

    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json"
        },
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }
        }
    )
    if response.status_code == 200:
        d = _static_dir()
        os.makedirs(d, exist_ok=True)
        filename = f"{uuid.uuid4()}.mp3"
        output_path = os.path.join(d, filename)
        with open(output_path, "wb") as f:
            f.write(response.content)
        return f"/static/{filename}"
    else:
        return ""

@app.route('/api/conversation', methods=['POST'])
def generate_conversation():
    from openai import OpenAI

    openai_api_key = os.environ.get("OPEN_API_KEY")
    eleven_api_key = os.environ.get("ELEVEN_API_KEY")

    if not openai_api_key or not eleven_api_key:
        return jsonify({"error": "Missing API keys"}), 500

    data = request.get_json()
    voice_id_a = data.get("voiceIdA")
    voice_id_b = data.get("voiceIdB")
    topic = data.get("topic")
    model = data.get("model", "eleven_multilingual_v2")
    length_a = data.get("lengthA", "short")
    length_b = data.get("lengthB", "short")
    language = data.get("language", "ENG")  # default ENG

    if not all([voice_id_a, voice_id_b, topic]):
        return jsonify({"error": "Missing required fields"}), 400

    client = OpenAI(api_key=openai_api_key)

    if model == "eleven_v3":
        system_prompt = (
        f"Generate a realistic, emotionally expressive 1-minute conversation between two people labeled A and B, in {language}.\n\n"
        "Format:\n"
        "- Each line must begin with A: or B:\n"
        "- Most lines (but not all) may start with one expressive audio tag in square brackets (e.g. [laughs], [whispers]).\n"
        "- You may add one more tag within the line if there is a clear emotional or delivery shift.\n"
        "- Do not repeat or stack tags at the beginning – use at most one per line.\n"
        "- Only 40-60% of lines should contain tags. Others should be clean and natural.\n\n"
        "Audio tags guide the vocal performance and emotion.\n"
        "You may use tags like:\n"
        "  [laughs], [starts laughing], [wheezing], [sighs], [whispers],\n"
        "  [sarcastic], [curious], [excited], [crying], [snorts], [mischievously], etc.\n"
        "These represent **tone, attitude, reactions, volume, or delivery**.\n\n"
        "You have access to a wide expressive palette — think of tone (joyful, sad, intense), delivery (whispering, shouting), rhythm (slow, fast), and reactions (sighs, laughs).\n"
        "But be subtle. Use the best tags for context. Avoid forcing or overusing them.\n\n"
        "Each speaker speaks in turns:\n"
        "- A speaks using approximately {length_a} sentences per turn\n"
        "- B responds using approximately {length_b} sentences per turn\n\n"
        "Your goal is to create a cinematic, human-like, performative conversation where audio direction is embedded but not exaggerated.\n"
        "The dialogue should feel alive and emotionally nuanced, using audio tags as gentle performance cues — not special effects."
    )
    else:
        system_prompt = (
            f"Generate a short, natural, 1-minute conversation between two people labeled A and B, in {language}.\n"
            f"A speaks using {length_a} sentences.\n"
            f"B speaks using {length_b} sentences.\n"
            "Label each line clearly as A: or B:. Keep it realistic and human-like."
        )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Topic: {topic}"},
        ]
    )

    lines = response.choices[0].message.content.strip().split("\n")
    dialogue = []
    speech_errors = []

    for line in lines:
        if not line.strip():
            continue
        normalized = line.strip().replace("\uff1a", ":")
        if normalized.startswith("A:"):
            speaker = "A"
            voice_id = voice_id_a
            text = normalized[2:].strip()
        elif normalized.startswith("B:"):
            speaker = "B"
            voice_id = voice_id_b
            text = normalized[2:].strip()
        else:
            continue

        if not text:
            dialogue.append({
                "speaker": speaker,
                "text": text,
                "audio_url": ""
            })
            continue

        tts_response, tts_err = _elevenlabs_tts(voice_id, eleven_api_key, text, model)

        if tts_response.status_code == 200:
            d = _static_dir()
            os.makedirs(d, exist_ok=True)
            filename = f"{uuid.uuid4()}.mp3"
            filepath = os.path.join(d, filename)
            with open(filepath, "wb") as f:
                f.write(tts_response.content)
            audio_url = f"/static/{filename}"
        else:
            audio_url = ""
            speech_errors.append({
                "speaker": speaker,
                "status": tts_response.status_code,
                "message": tts_err or _elevenlabs_error_message(tts_response),
                "text_preview": text[:160]
            })

        dialogue.append({
            "speaker": speaker,
            "text": text,
            "audio_url": audio_url
        })

    segments = []
    static_base = _static_dir()
    for line in dialogue:
        url = line.get("audio_url") or ""
        if not url:
            continue
        fname = os.path.basename(url.split("?", 1)[0])
        if not fname or fname in (".", ".."):
            continue
        path = os.path.join(static_base, fname)
        if os.path.exists(path):
            segments.append(AudioSegment.from_mp3(path))

    combined = _merge_dialogue_segments(segments)

    combined_audio_url = ""
    if len(combined) > 0:
        os.makedirs(static_base, exist_ok=True)
        combined_filename = f"{uuid.uuid4()}_combined.mp3"
        combined_filepath = os.path.join(static_base, combined_filename)
        combined.export(combined_filepath, format="mp3")
        combined_audio_url = f"/static/{combined_filename}"

    return jsonify({
        "dialogue": dialogue,
        "combined_audio_url": combined_audio_url,
        "speech_errors": speech_errors,
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
