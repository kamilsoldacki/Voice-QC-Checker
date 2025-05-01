from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import requests
import os
from dotenv import load_dotenv
from text_data import TEST_TEXTS

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/", StaticFiles(directory="static", html=True), name="static")

ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")

class GenerateRequest(BaseModel):
    voice_id: str
    language: str

@app.get("/voice-info/{voice_id}")
def get_voice_info(voice_id: str):
    url = f"https://api.elevenlabs.io/v1/voices/{voice_id}"
    headers = {"xi-api-key": ELEVEN_API_KEY}
    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return {"error": str(e)}

@app.post("/generate")
def generate_audio(req: GenerateRequest):
    headers = {
        "xi-api-key": ELEVEN_API_KEY,
        "Content-Type": "application/json"
    }

    language = req.language
    voice_id = req.voice_id
    if language not in TEST_TEXTS:
        return {"error": "Language not supported"}

    texts = TEST_TEXTS[language]
    audio_urls = {}

    for key, input_text in texts.items():
        payload = {
            "text": input_text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
                "speed": 1.0
            },
            "text_normalization": True
        }

        try:
            response = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream",
                json=payload,
                headers=headers
            )
            if response.status_code == 200:
                audio_urls[key] = response.content
            else:
                audio_urls[key] = None
        except Exception:
            audio_urls[key] = None

    return audio_urls
