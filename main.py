
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os, requests, base64
from text_data import TEST_TEXTS

app = FastAPI()

# Middleware for CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static folder
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve index.html at root
@app.get("/")
def read_index():
    return FileResponse("static/index.html")

# Request schema
class GenerationRequest(BaseModel):
    voice_id: str
    language: str

# Endpoint to generate samples
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
                "text_normalization": True,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "speed": 1.0,
                    "use_speaker_boost": True
                }
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

# Endpoint to fetch voice metadata with debug logging
@app.get("/voice-info/{voice_id}")
def get_voice_info(voice_id: str):
    try:
        api_key = os.getenv("ELEVEN_API_KEY")
        if not api_key:
            print("❌ ELEVEN_API_KEY is missing!")
            return {"error": "API key missing"}

        url = f"https://api.elevenlabs.io/v1/voices/{voice_id}"
        print(f"Fetching voice info from: {url}")
        response = requests.get(url, headers={"xi-api-key": api_key})

        if response.ok:
            data = response.json()
            print(f"✅ Received: {data}")
            return {"language": data.get("labels", {}).get("language", "")}
        else:
            print(f"❌ Request failed: {response.status_code}, {response.text}")
            return {"error": f"Request failed with status {response.status_code}"}
    except Exception as e:
        print(f"❌ Exception in /voice-info: {e}")
        return {"error": "Internal server error"}
