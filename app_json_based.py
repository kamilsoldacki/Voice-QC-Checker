
from flask import Flask, request, jsonify, send_from_directory
import os
import json
import requests
import uuid

app = Flask(__name__)

# Wczytanie tekstów z pliku JSON
with open("texts.json", "r", encoding="utf-8") as f:
    TEXTS = json.load(f)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

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
        output_path = f"static/{uuid.uuid4()}.mp3"
        os.makedirs("static", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)
        return "/" + output_path
    else:
        return ""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
