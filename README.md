
# Voice QC Checker

Simple web app for testing ElevenLabs voices using predefined language samples (plosives, sibilants, additional sounds).  
Hosted via GitHub + Render.com.

## Deployment

1. Create public GitHub repo: `Voice-QC-Checker`
2. Upload all files from this project.
3. Create new **Web Service** in [Render.com](https://render.com):
   - Runtime: Python 3.11
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port 10000`
   - Add environment variable: `ELEVEN_API_KEY` = your ElevenLabs key

## Usage

- Enter a valid Voice ID
- Choose language
- Click "Generate"
- You will see 3 samples:
  - Plosives
  - Sibilants
  - Additional Sounds

Each with corresponding test sentence and audio.
