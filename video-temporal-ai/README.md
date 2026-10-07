# 🎬 Video Temporal AI

**A hackathon system that watches videos and answers temporal questions with guaranteed timestamps.**

> Every answer includes a `[HH:MM:SS]` timestamp. No timestamp = no points. ⏱️

---

## 📌 What It Does

Upload any video and ask questions like:
- *"Which person entered the restricted area after the delivery truck arrived?"*
- *"How many times did the machine stop unexpectedly?"*
- *"What happened right before the safety alarm?"*
- *"Find every object that sat untouched for more than 2 minutes."*

The system answers with **precise timestamps**, **event ordering**, and **confidence scores**.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────┐
│              Streamlit Web UI (app.py)                │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│                 CORE PIPELINE                        │
│                                                      │
│  1. VideoProcessor  → frame extraction + timestamps  │
│  2. ObjectTracker   → YOLOv8 + ByteTrack (re-ID)    │
│  3. EventIndexer    → unified timestamped timeline   │
│  4. GeminiAnalyzer  → VLM video QA (File API)        │
│  5. TemporalEngine  → order/count/duration/causal    │
│  6. AnswerFormatter → enforces timestamp rule        │
└──────────────────────────────────────────────────────┘
```

---

## 🛠️ Technologies Used

| Component | Technology |
|-----------|-----------|
| Vision-Language Model | **Google Gemini 1.5 Flash / Pro** (File API) |
| Object Detection | **YOLOv8n** (ultralytics) |
| Object Tracking + Re-ID | **ByteTrack** (built into ultralytics) |
| Video Processing | **OpenCV** |
| Web UI | **Streamlit** |
| REST API (optional) | **FastAPI** |
| Language | **Python 3.10+** |

---

## ⚡ Quick Start

### 1. Clone & Enter Directory
```bash
git clone <your-repo-url>
cd video-temporal-ai
```

### 2. Create Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure API Key
```bash
# Copy the template
cp .env.example .env

# Open .env and replace "api-key" with your actual Gemini API key
# Get a free key at: https://ai.google.dev
```

Your `.env` should look like:
```
GEMINI_API_KEY=AIzaSy...your_real_key_here
GEMINI_MODEL=gemini-1.5-flash
```

### 5. Run the App
```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 📖 How to Use

1. **Upload Video** — Click "Upload Video" and select an MP4/MOV/AVI file
2. **Click "Analyze Video"** — The pipeline runs:
   - YOLOv8 detects and tracks all objects (people, trucks, etc.)
   - Scene changes are detected
   - Gemini analyzes the full video and builds an event timeline
3. **View Event Timeline** — See every detected event with its timestamp
4. **Ask Questions** — Type any temporal question or pick from examples
5. **Get Timestamped Answers** — Every answer includes `[HH:MM:SS]` timestamps

---

## 🔄 Data Pipeline

```
Input Video
    ↓
[VideoProcessor] — Extract frames at N fps, map each to exact timestamp
    ↓
[ObjectTracker] — YOLOv8 detects objects; ByteTrack assigns persistent IDs
    ↓                (handles occlusion & re-entry with same ID)
[EventIndexer] — Build timeline: enters, exits, zone crossings, stationary
    ↓
[GeminiAnalyzer] — Upload video to File API → triage pass (Flash model)
    ↓               → extract all events with timestamps as structured JSON
[EventIndexer.merge] — Merge YOLO events + scene changes + Gemini events
    ↓
[TemporalEngine] — Answer question using rule-based reasoning + Gemini QA
    ↓               (classifies as order/count/duration/causal/conditional)
[AnswerFormatter] — Enforce timestamp rule; merge Gemini + rule-based answers
    ↓
Output: { answer, timestamps[], confidence, supporting_events[] }
```

---

## 🧠 Core Reasoning

### Temporal Query Types Supported

| Query Type | Example | How It Works |
|-----------|---------|-------------|
| **Order** | "What happened first?" | Sort event timeline, return first/last |
| **Count** | "How many times did X occur?" | Count matching events, list each timestamp |
| **Duration** | "How long did X stay?" | Compute `last_seen - first_seen` per track |
| **Causal** | "What happened before the alarm?" | Find nearest event before reference event |
| **Conditional** | "Who entered after the truck?" | Filter events after reference timestamp |
| **Stationary** | "Objects untouched > 2 minutes" | Detect low-movement tracks over threshold |

### Object Re-Identification
ByteTrack assigns each object a **persistent track ID** that survives:
- Partial occlusion (object partly hidden)
- Full disappearance and reappearance
- Camera movement

This means "the same person who entered at the beginning" is correctly tracked even if they leave and return.

---

## 📊 Sample Input & Output

**Input:** Office surveillance video (3 minutes)  
**Question:** *"Which person entered the restricted area after the delivery truck arrived?"*

**Output:**
```json
{
  "question": "Which person entered the restricted area after the delivery truck arrived?",
  "answer": "Person-3 (visible in the right side of frame) entered the restricted area at [02:14] — approximately 47 seconds after the delivery truck arrived at [01:27].",
  "timestamps": ["01:27", "02:14"],
  "timestamp_confidence": "HIGH",
  "has_timestamp": true,
  "supporting_events": [
    {
      "event_type": "object_enters_frame",
      "timestamp_str": "00:01:27.000",
      "display_name": "Truck-1",
      "label": "truck"
    },
    {
      "event_type": "zone_crossing",
      "timestamp_str": "00:02:14.000",
      "display_name": "Person-3",
      "zone": "restricted_area"
    }
  ],
  "score_estimate": 1.0
}
```

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

Tests cover:
- Query type classification
- Timestamp parsing and formatting
- Count / duration / causal / order query handlers
- Zone crossing detection
- Event indexer queries (before/after, window, type filter)
- Answer formatter timestamp enforcement rule

---

## 🎯 Scope

### ✅ Minimum Viable Solution (Implemented)
- Gemini 1.5 video Q&A with timestamps via File API
- YOLOv8 + ByteTrack object detection and re-identification
- Temporal event indexing (5 query types)
- Streamlit web UI with event timeline + Q&A
- Enforced timestamp on every answer (hackathon rule)
- Demo questions for all query types
- Full test suite

### 🎯 Stretch Goals (Also Implemented)
- Zone-crossing detection with configurable regions
- Stationary object detection with duration threshold
- Two-stage analysis (triage + deep-dive)
- FastAPI REST endpoints for programmatic access
- Answer confidence scoring and score estimation
- JSON export of answers

---

## 📁 Project Structure

```
video-temporal-ai/
├── app.py                     # Streamlit UI
├── requirements.txt
├── .env.example               # Config template
├── README.md
├── core/
│   ├── video_processor.py     # Frame extraction + timestamps
│   ├── object_tracker.py      # YOLOv8 + ByteTrack
│   ├── event_indexer.py       # Unified event timeline
│   ├── gemini_analyzer.py     # Gemini File API + VQA
│   ├── temporal_engine.py     # Temporal reasoning
│   └── answer_formatter.py    # Timestamp enforcement
├── api/
│   └── routes.py              # FastAPI REST API
├── demo/
│   └── sample_questions.json  # Pre-built Q&A examples
└── tests/
    ├── test_temporal_engine.py
    └── test_event_indexer.py
```

---

## 🔑 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | `api-key` | Your Google Gemini API key |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Model for triage + QA |
| `SAMPLE_FPS` | `1` | Frames per second for tracking |
| `YOLO_MODEL` | `yolov8n.pt` | YOLO model size |
| `YOLO_CONF` | `0.35` | Detection confidence threshold |

---

## 📜 Licenses & Credits

- [Google Gemini API](https://ai.google.dev) — Video understanding
- [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics) — Object detection (AGPL-3.0)
- [ByteTrack](https://github.com/ifzhang/ByteTrack) — Multi-object tracking
- [OpenCV](https://opencv.org) — Video processing
- [Streamlit](https://streamlit.io) — UI framework
