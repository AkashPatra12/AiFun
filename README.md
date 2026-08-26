# AiFun

Auto Reel/Shorts Generator — turns long-form video into short-form vertical
clips (highlight detection, reframe to 9:16, captions, export).

Monorepo: `backend/` (Python pipeline) + `frontend/` (React + TypeScript).

## Layout

- `backend/` — the video-processing pipeline
  - `src/aifun/` — pipeline stages (`ingest`, `transcribe`, `analysis`, `editing`, `render`, `export`) + `pipeline.py`/`cli.py`
  - `config/`, `assets/`, `data/`, `tests/`
- `frontend/` — React + TypeScript app (Vite)
  - `src/components/`, `src/pages/`, `src/api/`
- `docs/` — architecture notes

See [docs/architecture.md](docs/architecture.md) for how the pieces fit together.

Run backend: `aifun process <input_path>` (after `pip install -e backend`).
Run frontend: `npm install && npm run dev` (in `frontend/`).
