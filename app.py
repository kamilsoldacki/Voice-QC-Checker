
from flask import Flask, request, jsonify, send_from_directory
import os
import pandas as pd
import requests
import uuid

app = Flask(__name__)
df = pd.read_excel('texts.xlsx', sheet_name='test texts')

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/languages')
def languages():
    langs = df['language'].dropna().unique()
    return jsonify({"languages": [{"name": lang} for lang in langs]})

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    voice_id = data['voiceId']
    language = data['language']

    row = df[df['language'] == language].iloc[0]
    outputs = {}
    categories = {
        'plosives': 'plosives results:',
        'sibilants': 'sibilants results:',
        'additional': 'additional sounds results:'
    }

    for key, column in categories.items():
        text = row[column]
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
        with open(output_path, "wb") as f:
            f.write(response.content)
        return "/" + output_path
    else:
        return ""

if __name__ == '__main__':
    os.makedirs("static", exist_ok=True)
    app.run(host='0.0.0.0', port=5000)
