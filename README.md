# 🏎 F1 AI Race Engineer

An AI-powered Formula 1 race analysis assistant. Ask natural language 
questions about any race from 2018–2024 and get data-grounded answers 
with live charts — lap times, tyre strategy, driver comparisons.

<!-- ADD A DEMO GIF HERE -->
<!-- Record your screen: ask "What was the tyre strategy at Monza 2024?" -->
<!-- Save as docs/demo.gif and uncomment the line below -->
<!-- ![Demo](docs/demo.gif) -->

## What it does

- Answers F1 questions using **real telemetry data** from FastF1
- Streams responses token-by-token via Server-Sent Events
- Renders **interactive charts** — tyre strategy timelines, lap time 
  comparisons, driver progression charts
- Uses a full **RAG pipeline** with local embeddings + FAISS vector search
- Runs an **MCP (Model Context Protocol)** tool-use loop so the LLM 
  autonomously decides which data to fetch

## Performance

- Vector retrieval: **<10ms** per query across 50,000+ indexed chunks
- Embedding: **~5ms** per query (local CPU, no API call)
- Full response: typically **3–6 seconds** end-to-end on free Groq tier
- Ingest speed: **~2 minutes** per race season on first run

## Tech stack

| Layer | Technology |
|---|---|
| LLM | Groq — LLaMA 3.3 70B (free tier) |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 (local, free) |
| Vector search | FAISS (Facebook AI Similarity Search) |
| Data | FastF1 — real F1 telemetry 2018–2024 |
| Agent protocol | MCP (Model Context Protocol) |
| Backend | Python, Flask, SSE streaming |
| Frontend | React, Vite, Recharts |

## Quickstart

### 1. Clone and install

```bash
git clone <your-repo-url>
cd f1-race-engineer
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
```

### 2. Set up environment

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and add your GROQ_API_KEY
# Get a free key at: https://console.groq.com
```

### 3. Ingest race data (one-time setup)

```bash
# Ingest the 2024 season (~2 min, builds local FAISS indices)
python backend/scripts/ingest.py --years 2024

# Or ingest specific races to start faster
python backend/scripts/ingest.py --years 2024 --races Monza Monaco Silverstone

# Preview what would be ingested without running
python backend/scripts/ingest.py --years 2024 --dry-run
```

### 4. Start the app

```bash
# Terminal 1 — backend
cd backend && python -m app.server

# Terminal 2 — frontend dev server
cd frontend && npm run dev
```

Open http://localhost:5173

## Example questions

- *"What was Verstappen's tyre strategy at the 2024 British Grand Prix?"*
- *"Compare Leclerc and Norris lap times at Monza 2024"*
- *"Why did Hamilton lose the 2023 Singapore GP?"*
- *"Who had the fastest pit stop at Monaco 2022?"*

## Architecture

```
Question
   │
   ▼
MCP Client (Python)
   │  Groq LLaMA 3.3 70B decides which tools to call
   ▼
MCP Server (stdio)
   │  Calls FastF1 tools: list_races, get_results, get_stints, search
   ▼
FAISS Retriever
   │  local all-MiniLM-L6-v2 embeddings → top-8 chunks
   ▼
LLM Final Answer (streamed via SSE)
   │
   ▼
React Frontend
   │  Renders markdown + Recharts visualizations
```

## Project structure

```
├── backend/
│   ├── app/                Flask server + API routes
│   ├── config/             Central config (env vars)
│   ├── mcp_server/         MCP server + F1 data tools
│   ├── scripts/
│   │   └── ingest.py       Bulk data ingest + FAISS index builder
│   ├── src/
│   │   ├── data_loader/    FastF1 session loading
│   │   ├── data_processor/ Stint-based RAG chunking
│   │   ├── llm_interface/  Groq streaming completions
│   │   ├── mcp_client/     MCP client + tool-use loop
│   │   └── retrieval/      FAISS vector index management
│   └── data/
│       ├── cache/          FastF1 local cache
│       ├── faiss/          Persisted FAISS indices
│       └── processed/      Processed chunk JSON files
├── frontend/               React + Vite frontend
│   └── src/components/
│       └── charts/         LapTimeChart, TyreStrategyChart, DriverComparisonChart
└── data/                   (legacy root data, optional)
```

## Supported data

- **Years:** 2018 – 2024
- **Session types:** Race (R), Qualifying (Q), Sprint (S), FP1/FP2/FP3
- **Data source:** FastF1 (official F1 timing data via ergast + F1 live timing)
