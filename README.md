# Viral Clip Agent

**A multi-agent pipeline that watches long-form video and finds clips with viral potential — then trims, captions, titles, and thumbnails them automatically.**

The core insight: the best clippers on YouTube aren't using one tool — they're using their own taste and intuition to spot moments. Viral Clip Agent approximates that by deploying **five AI "viewer" agents**, each watching the same content from a different perspective. When multiple agents agree a moment is clip-worthy, it rises to the top. This consensus approach is closer to a focus group of human clippers than a single automated filter.

---

## How It Works

### The 5-Stage Pipeline

```
Video/Audio Upload
       │
       ▼
┌─────────────────────────────────────────────────────┐
│  1. INGEST                                          │
│     Extract audio, probe metadata, prepare source   │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  2. TRANSCRIPTION                                   │
│     Generate timestamped transcript (Whisper API    │
│     or sample transcript for demo mode)              │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  3. CLIP SCOUT (Multi-Agent)                        │
│                                                     │
│  🎯 Hook Hunter    — scores hooks, curiosity gaps,  │
│                       pattern interrupts            │
│  🔥 Emotion Reader  — scores vulnerability, conflict, │
│                       passion, emotional peaks       │
│  💎 Quote Finder   — scores quotable lines,         │
│                       aphorisms, standalone clarity   │
│  📖 Story Analyst  — scores narrative arcs,          │
│                       setup-payoff, story structure   │
│  📈 Trend Spotter  — scores controversy, debates,   │
│                       shareability, comment bait      │
│                                                     │
│  Each agent scores overlapping 30-90s windows.       │
│  Consensus = average of top 3 agent scores.          │
│  Agreement = how many agents scored ≥6.0.             │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  4. EDIT AGENT                                      │
│     • Trim clip to exact timestamps                 │
│     • Audio normalization (loudnorm EBU R128)       │
│     • Burn-in captions (SRT → hardcoded subtitles)  │
│     • Vertical 9:16 crop for Shorts/Reels/TikTok    │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  5. PACKAGING AGENT                                  │
│     • Generate 5 title options per clip             │
│     • Create click-worthy thumbnails (frame + text) │
│     • Generate description with hashtags            │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
              Ranked clip results
              with download links
```

### Scoring System

Each candidate clip window (30s, 45s, 60s, 75s, 90s) is analyzed by all 5 agents. Each agent applies its own weighted scoring across these signals:

| Signal | What it measures |
|--------|-----------------|
| **Hook strength** | Does it open with a pattern interrupt, question, or bold claim? |
| **Curiosity gap** | Does it create an information gap the viewer needs to resolve? |
| **Surprise** | Does it contain unexpected facts, counterintuitive ideas, or plot twists? |
| **Emotional intensity** | Vulnerability, anger, passion, sadness, excitement — measured via keyword + sentiment analysis |
| **Quotability** | Is it a standalone quotable line? Aphorism? Strong declaration? |
| **Standalone clarity** | Does the clip make sense without surrounding context? |
| **Controversy** | Does it take a stance, challenge conventional wisdom, or provoke debate? |

Scores use a **sigmoid curve** so differentiation is meaningful:
- Truly exceptional clips reach 8-10
- Good clips land at 5-7
- Mediocre clips land at 2-5

**Consensus score** = average of the top 3 agent scores.
**Agreement** = how many of the 5 agents scored the clip ≥6.0.

Clips are ranked by consensus score, with agreement as a tiebreaker. Clips where all 5 agents agree (5/5) are flagged with a special badge.

---

## What It Accomplishes

### For Content Creators
- **Finds viral-worthy clips** from hour-long podcasts, streams, or interviews without watching the whole thing
- **Saves 4-8 hours per episode** of manual scrubbing, clipping, and titling
- **Generates ready-to-post packages**: trimmed video, burned captions, title options, thumbnail, description with hashtags
- **Multi-format output**: horizontal (16:9) for YouTube, vertical (9:16) for Shorts/Reels/TikTok

### For the Clipping Community
- **Consensus-based ranking** means the system surfaces clips that multiple "perspectives" agree on, not just one metric
- **Differentiated scoring** — not every clip is a 10/10. The system honestly tells you which clips are mediocre (5/7) vs exceptional (9/10)
- **Agent rationale** — each clip shows which agents scored it and why (e.g., "strong hook, high surprise, quotable, controversial")

### Demo Mode
The built-in demo uses a realistic sample podcast transcript with a mix of:
- Strong hooks and cold opens
- Vulnerable storytelling
- Filler content and tangents (that correctly score low)
- Controversial takes
- Quotable insights
- Emotional peaks
- Practical advice and CTAs

This lets you see the system differentiate between great, good, and mediocre clips without uploading anything.

---

## Architecture

```
viral-clip-agent/
├── app.py                          # Flask backend — serves API + static files
├── pipeline.py                     # Orchestrates the 5-stage pipeline
├── agents/
│   ├── scout_agents.py             # 5 agent personas + scoring engine
│   ├── edit_agent.py               # ffmpeg clip processing (trim, caption, crop)
│   └── packaging_agent.py          # Title, thumbnail, and description generation
├── static/
│   ├── index.html                  # Dashboard UI
│   ├── styles.css                  # Dark industrial theme
│   └── app.js                      # Frontend logic (upload, poll, render results)
├── uploads/                        # Job working directories (created at runtime)
└── requirements.txt
```

### Tech Stack
- **Backend**: Python Flask
- **Video processing**: ffmpeg (trim, normalize, caption burn, vertical crop)
- **Thumbnails**: Pillow (text overlay) or ffmpeg frame extraction
- **Transcription**: OpenAI Whisper API (optional — demo uses sample transcript)
- **Frontend**: Vanilla HTML/CSS/JS (no build step)
- **No external API keys required** for demo mode — scoring uses heuristic analysis

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/agents` | GET | List all 5 agent personas and their scoring weights |
| `/api/upload` | POST | Upload video file, start pipeline (multipart form) |
| `/api/demo` | POST | Run pipeline with sample transcript (no upload needed) |
| `/api/job/<id>` | GET | Poll job status and results |
| `/api/job/<id>/clips/<filename>` | GET | Download processed clip files |
| `/api/job/<id>/thumbnails/<filename>` | GET | Download thumbnail images |

---

## Quick Start

### Prerequisites
- Python 3.8+
- ffmpeg (with libx264, libfreetype for captions)
- pip install flask pillow openai

### Run Locally

```bash
# Install dependencies
pip install flask pillow openai

# Start the backend
python3 app.py

# Open in browser
# The Flask app serves the dashboard at http://localhost:5000
```

### Using the Demo
1. Open http://localhost:5000
2. Click "Run Demo with Sample Podcast"
3. Watch the pipeline process a simulated 5-minute podcast
4. Review ranked clips with scores, thumbnails, titles, and download links

### Processing Real Video
1. Upload an MP4, MOV, MKV, MP3, or WAV file (up to 500MB)
2. The pipeline transcribes (if Whisper API key available) or uses sample transcript
3. 5 agents analyze every 30-90 second window
4. Top clips are trimmed, captioned, and packaged
5. Download clips, thumbnails, and SRT files

### To enable real transcription (optional):
Set the `OPENAI_API_KEY` environment variable. Without it, the system uses the built-in sample transcript for testing.

---

## What Makes This Different

| Feature | Other Clippers | Viral Clip Agent |
|---------|---------------|-----------------|
| Clip discovery | Single algorithm or manual | 5 AI agents with different perspectives |
| Scoring | Binary (good/bad) or single score | Multi-agent consensus with differentiated scoring |
| Transparency | Black box | Each clip shows agent scores + rationale |
| Output | Just the clip | Clip + captions + titles + thumbnail + description + hashtags |
| Formats | Usually one | Horizontal (16:9) + Vertical (9:16) |
| Context | Needs full context | Detects standalone clarity (works without context) |
| Filler detection | No | Identifies and penalizes filler, tangents, and sponsor reads |
| Cost | Subscription or per-clip | Self-hosted, open source |

---

## Building Your Own Agents

The agent system is extensible. Each agent is defined by:
1. A **persona** (name, icon, focus area)
2. **Scoring weights** for each signal
3. The same signals are computed for all agents — they just weight them differently

To add a new agent, add an entry to the `AGENTS` list in `agents/scout_agents.py`:

```python
{
    "name": "Data Detective",
    "icon": "📊",
    "focus": "Statistics, data points, specific numbers and claims",
    "weights": {
        "hook": 1.0,
        "curiosity": 2.5,
        "surprise": 2.0,
        "emotion": 0.5,
        "quotable": 2.0,
        "standalone": 1.5,
    },
},
```

---

## License

MIT — Build something great with it.

---

## Author

**Daniel Paxson**  
Built as a demonstration of multi-agent consensus systems for content analysis.
