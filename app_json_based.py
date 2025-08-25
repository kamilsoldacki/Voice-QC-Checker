from flask import Flask, request, jsonify, send_from_directory
from pydub import AudioSegment
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
        output_path = f"static/{uuid.uuid4()}.mp3"
        os.makedirs("static", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)
        return "/" + output_path
    else:
        return ""

@app.route('/api/conversation', methods=['POST'])
def generate_conversation():
    from openai import OpenAI
    import base64

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

    for line in lines:
        if not line.strip():
            continue
        if line.startswith("A:"):
            speaker = "A"
            voice_id = voice_id_a
            text = line[2:].strip()
        elif line.startswith("B:"):
            speaker = "B"
            voice_id = voice_id_b
            text = line[2:].strip()
        else:
            continue

        tts_response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": eleven_api_key,
                "Content-Type": "application/json"
            },
            json={
                "text": text,
                "model_id": model,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True
                }
            }
        )

        if tts_response.status_code == 200:
            filename = f"{uuid.uuid4()}.mp3"
            filepath = os.path.join("static", filename)
            os.makedirs("static", exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(tts_response.content)
            audio_url = f"/static/{filename}"
        else:
            audio_url = ""

        dialogue.append({
            "speaker": speaker,
            "text": text,
            "audio_url": audio_url
        })

    combined = AudioSegment.empty()
    for line in dialogue:
        path = line["audio_url"].lstrip("/")
        if os.path.exists(path):
            segment = AudioSegment.from_mp3(path)
            combined += segment

    combined_filename = f"{uuid.uuid4()}_combined.mp3"
    combined_filepath = os.path.join("static", combined_filename)
    combined.export(combined_filepath, format="mp3")

    return jsonify({
        "dialogue": dialogue,
        "combined_audio_url": f"/static/{combined_filename}"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
