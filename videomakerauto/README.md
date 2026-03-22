# AI Video Maker Auto

Automated pipeline to create videos from an idea: enter a topic → AI writes script → generates voiceover → outputs MP4 video.

**Usage:** Pull repo → run `run.bat` (Windows) or `run.sh` (Mac/Linux) → enter API keys (first time) → enter topic → done. No manual installation.

---

## Prerequisite

- **Python 3.8+** only. [Download](https://www.python.org/downloads/) if needed.  
- OpenAI and ElevenLabs accounts (for API keys).

Dependencies install automatically when you run the script.

---

## How to use

### Step 1: Pull the repo

```bash
git clone https://github.com/ydangishere/dev-projects.git
cd dev-projects/videomakerauto
```

(Or `git pull` if you already have dev-projects)

### Step 2: Run run.bat or run.sh

**Windows:** Double-click `run.bat`

**Mac/Linux:**
```bash
chmod +x run.sh
./run.sh
```

On first run: dependencies install automatically (~1–2 min). Then you're prompted for API keys.

### Step 3: Enter API keys (first run only)

On first run, the script will prompt:

1. **OPENAI_API_KEY:** Paste key from [platform.openai.com](https://platform.openai.com/) → API keys
2. **ELEVENLABS_API_KEY:** Paste key from [elevenlabs.io](https://elevenlabs.io/) → Profile → API Key
3. **ELEVENLABS_VOICE_ID:** Press Enter for default (Rachel), or paste another Voice ID from [voice library](https://elevenlabs.io/voice-library)

Keys are saved to `.env` (local only, not committed to git).

### Step 4: Enter video topic

When prompted, type your topic (e.g. `how to make money with TikTok`). Press Enter for default "make money with AI".

### Step 5: Wait for the pipeline

The script runs:

1. **Generating script...** – GPT writes content
2. **Generating voice...** – ElevenLabs generates voiceover
3. **Generating scenes...** – MoviePy assembles video

Done. Video is in `output/` folder.

---

## Subsequent runs

Just double-click `run.bat` (or `./run.sh`) → enter topic → Enter. API keys are stored in `.env`, no need to re-enter.

---

## Alternative ways to run

### Use setup then call main.py

```powershell
.\setup.ps1
python main.py "your video topic"
```

### Call main.py directly (when .env exists)

```powershell
python main.py "how to make money with TikTok"
python main.py   # use default topic
```

**Option:** `--no-cache` – disable cache, call APIs every time

---

## Project structure

```
videomakerauto/
├── run.bat          # One-click run (Windows)
├── run.sh           # One-click run (Mac/Linux)
├── run.py           # Interactive script
├── main.py          # Main pipeline
├── setup.ps1        # Manual setup
├── .env.example     # .env template
├── src/
│   ├── script_generator.py
│   ├── voice_generator.py
│   ├── video_generator.py
│   └── cache.py
├── output/          # Video output
└── cache/           # Cache for script + voice
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| OPENAI_API_KEY / ELEVENLABS_API_KEY not found | Run `run.bat` again and enter keys when prompted. Or create `.env` from `.env.example` and fill in keys. |
| Rate limit / Quota exceeded | API quota exhausted. Wait or upgrade your plan. |
| pip install failed | Run `python -m pip install -r requirements.txt` manually. |
| ImageMagick | May be missing on Windows. Pipeline falls back to Pillow. |

---

## Estimated cost

- **OpenAI (GPT-4o-mini):** ~$0.01–0.05 per video
- **ElevenLabs:** Per character (free tier available)

Cache reduces API calls when reusing similar topics.
