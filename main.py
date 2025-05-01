
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os, requests, base64
from text_data import TEST_TEXTS

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_index():
    return FileResponse("static/index.html")

class GenerationRequest(BaseModel):
    voice_id: str
    language: str

@app.post("/generate")
def generate_audio(data: GenerationRequest):
    voice_id = data.voice_id
    language = data.language
    model_id = "eleven_multilingual_v2"
    api_key = os.getenv("ELEVEN_API_KEY")

    texts = TEST_TEXTS.get(language)
    if not texts:
        return {"error": "Language not supported."}

    output = {}
    for key, text in texts.items():
        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json"
            },
            json={
                "text": text,
                "model_id": model_id,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
            }
        )
        if response.ok:
            b64 = base64.b64encode(response.content).decode("utf-8")
            output[key] = b64
            output[key + "_text"] = text
        else:
            output[key] = None
            output[key + "_text"] = "Error generating sample."

    return output
